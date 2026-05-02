from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
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
        headers={"User-Agent": "movies.pub/0.1 (https://movies.pub)"},
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

@app.get("/movie/{qid}")
async def get_movie(qid: str) -> JSONResponse:
    if not qid.startswith("Q") or not qid[1:].isdigit():
        raise HTTPException(status_code=400, detail="Invalid Wikidata Q-id")
    try:
        json = await fetch_movie(qid, app.state.wikidata)
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid Wikidata Q-id")
    if not "entities" in json or not qid in json["entities"]:
        raise HTTPException(status_code=500, detail="Unexpected Wikidata format")
    film = json["entities"][qid]
    # TODO: pick a better default name
    name = film["labels"]["en"]["value"]
    # TODO: grab all names in nameMap
    return ActivityJSONResponse({
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"https://movies.pub/movie/{qid}",
        "type": "Video",
        "name": name
    })