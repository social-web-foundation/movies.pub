from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
import httpx

class ActivityJSONResponse(JSONResponse):
    media_type = "application/activity+json"

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
    r = await app.state.wikidata.get(
        "/wiki/Special:EntityData/" + qid + ".json"
    )
    if r.status_code == 404:
        raise HTTPException(404)
    r.raise_for_status()
    if "json" not in r.headers.get("content-type", ""):
        raise HTTPException(502, "Upstream returned non-JSON")
    try:
        json = r.json()
    except ValueError:
        raise HTTPException(502, "Upstream returned invalid JSON")
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