from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
import httpx
from cachetools import TTLCache
from asyncio import Lock

class ActivityJSONResponse(JSONResponse):
    media_type = "application/activity+json"

_movie_cache: TTLCache[str, dict] = TTLCache[str, dict](maxsize=10_000, ttl=3600)
_locks: dict[str, Lock] = {}

async def fetch_movie(qid: str, wd) -> dict:
    if qid in _movie_cache:
        return _movie_cache[qid]
    lock = _locks.setdefault(qid, Lock())
    async with lock:  # collapse concurrent misses for same qid
        if qid in _movie_cache:
            return _movie_cache[qid]
        r = await wd.get(f"/wiki/Special:EntityData/{qid}.json")
        r.raise_for_status()
        data = r.json()
        _movie_cache[qid] = data
        return data

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.wikidata = httpx.AsyncClient(
        base_url="https://www.wikidata.org",
        headers={
            "User-Agent": "movies.pub/0.1 (https://movies.pub; evanp@socialweb.foundation)"
        },
        timeout=10.0,
    )
    try:
        yield
    finally:
        await app.state.wikidata.aclose()

app = FastAPI(title="movies.pub", lifespan=lifespan)

@app.get("/livez", status_code=status.HTTP_204_NO_CONTENT)
def livez() -> None:
    return None

@app.api_route("/movie/{qid}", methods=["GET", "HEAD"])
async def get_movie(qid: str, request: Request) -> Response:
    if not qid.startswith("Q") or not qid[1:].isdigit():
        raise HTTPException(status_code=400, detail="Invalid Wikidata Q-id")
    try:
        json = await fetch_movie(qid, app.state.wikidata)
    except httpx.HTTPStatusError as e:
        upstream = e.response.status_code
        if upstream == 404:
            raise HTTPException(status_code=404, detail=f"Movie {qid} not found")
        if upstream == 429:
            raise HTTPException(status_code=503, detail="Upstream rate limited")
        raise HTTPException(status_code=502, detail=f"Upstream error {upstream}")
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail="Upstream timeout")
    except httpx.RequestError as e:
        # connection errors, DNS, TLS, etc.
        raise HTTPException(status_code=502, detail=f"Upstream unreachable: {e!r}")
    except ValueError as e:
        raise HTTPException(status_code=502, detail="Upstream returned invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unknown upstream error")
    if not "entities" in json or not qid in json["entities"]:
        raise HTTPException(status_code=500, detail="Unexpected Wikidata format")
    film = json["entities"][qid]
    # TODO: pick a better default name
    name = film["labels"]["en"]["value"]
    # TODO: grab all names in nameMap

    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/activity+json")
    else:
        return ActivityJSONResponse({
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"https://movies.pub/movie/{qid}",
            "type": "Video",
            "name": name
        })
