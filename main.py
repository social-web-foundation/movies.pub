from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from cachetools import TTLCache
from asyncio import Lock
from urllib.parse import quote
import logging
from pathlib import Path

INDEX = Path(__file__).parent / "index.html"

log = logging.getLogger(__name__)

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

_search_cache: TTLCache[tuple, list[dict]] = TTLCache[tuple, list[dict]](maxsize=10_000, ttl=300)
_search_locks: dict[tuple, Lock] = {}

async def fetch_search_results(q: str, lng: str, wd) -> list[dict]:
    if (q, lng) in _search_cache:
        return _search_cache[(q, lng)]
    lock = _search_locks.setdefault((q, lng), Lock())
    async with lock:  # collapse concurrent misses for same qid
        if (q, lng) in _search_cache:
            return _search_cache[(q, lng)]
        r = await wd.get(
            "/w/rest.php/v1/search/page",
            params={
                "q": f'inlabel:"{q}" haswbstatement:P31=Q11424',
                "limit": 20,
            },
        )

        r.raise_for_status()

        json = r.json()

        pages = json.get("pages", [])

        qids = list(map(lambda page: page.get("title", None), pages))
        qids = list(filter(lambda qid: qid is not None and len(qid) > 1 and qid[0] == "Q" and qid[1:].isdigit(), qids))

        if not qids:
            _search_cache[(q, lng)] = []
            return []

        ids_fragment = ", ".join(f"\"{qid}\"" for qid in qids)
        movie_details_graphql_query = f"""
            query movie_details {{
            itemsById(ids: [{ids_fragment}]) {{

                    qid: id
                    en_label: label(languageCode: "en")
                    lng_label: label(languageCode: "{lng}")

                    title: statements(propertyId: "P1476") {{
                        value {{
                            ... on MonolingualTextValue {{
                                language
                                text
                            }}
                        }}
                    }}

                    director: statements(propertyId: "P57") {{
                        value {{
                            ... on ItemValue {{
                                en_director: label(languageCode: "en")
                                lng_director: label(languageCode: "{lng}")
                            }}
                        }}
                    }}

                    release: statements(propertyId: "P577") {{
                        value {{
                            ... on TimeValue {{
                                time
                            }}
                        }}
                    }}
                }}
            }}
        """

        r = await wd.post(
            "/w/api.php",
            params={
                "action": "wbgraphql",
                "format": "json",
                "formatversion": "2",
            },
            json={
                "query": movie_details_graphql_query,
            },
        )

        r.raise_for_status()
        data = r.json()['data']
        entities = data.get("itemsById", [])

        items = []

        for entity in entities:

            qid = entity.get("qid", None)

            nameMap = {}
            if "en_label" in entity and entity["en_label"] is not None:
                nameMap["en"] = entity["en_label"]
            if "lng_label" in entity and entity["lng_label"] is not None:
                nameMap[lng] = entity["lng_label"]
            if entity["en_label"] is None and entity["lng_label"] is None:
                continue

            # Since release(s) can have multiple values, only parse the oldest one
            # TODO: we can't get country release info from WB GraphQL right now, but
            #       when it will be possibly we should prefer release date+country
            release_date = None
            if "release" in entity and entity["release"] is not None and len(entity["release"]) > 0:
                sorted_releases = sorted(entity["release"], key=lambda r: r["value"]["time"])
                release_date = sorted_releases[0]["value"]["time"].split("T")[0][1:] # Get date and remove "+" prefix (no movies BCE)

            directors = []
            if "director" in entity and entity["director"] is not None and len(entity["director"]) > 0:
                for director_entry in entity["director"]:
                    director_name = director_entry["value"].get(f"lng_director", None) or director_entry["value"].get("en_director", None)
                    directors.append(director_name)

            items.append({
                "type": "Video",
                "id": f"https://movies.pub/movie/{qid}",
                "directors": directors,
                "release_date": release_date,
                "nameMap": nameMap
            })

        _search_cache[(q, lng)] = items

        return items

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)

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

@app.api_route("/search/movie", methods=["GET", "HEAD"])
async def search_movie(request: Request, q: str, lng: str = 'en') -> Response:

    try:
        items = await fetch_search_results(q, lng, app.state.wikidata)
    except Exception as e:
        log.exception("search_movie failed: q=%r lng=%r", q, lng)
        raise HTTPException(status_code=500, detail="Unknown upstream error")

    if request.method == "HEAD":
        return Response(status_code=200, media_type="application/activity+json")
    else:
        return ActivityJSONResponse({
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"https://movies.pub/search/movie?q={quote(q, safe="")}&lng={quote(lng, safe="")}",
            "type": "Collection",
            "summary": f"Search for movies with title {q} in language {lng}",
            "totalItems": len(items),
            "items": items
        })

@app.api_route("/", methods=["GET", "HEAD"])
def home(request: Request) -> Response:
    if request.method == "HEAD":
        return Response(status_code=200, media_type="text/html")
    else:
        return FileResponse(INDEX, media_type="text/html")
