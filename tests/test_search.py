from fastapi.testclient import TestClient

from main import app

def test_search_returns_collection():
    with TestClient(app) as client:
        response = client.get("/search/movie?q=Star%20Wars")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/activity+json")
        body = response.json()
        assert body["type"] == "Collection"
        assert body["id"] == "https://movies.pub/search/movie?q=Star%20Wars&lng=en"
        assert body["totalItems"] > 0
        assert type(body["items"]) == list
        for item in body["items"]:
          assert item["type"] == "Video"
          assert "id" in item
          assert "nameMap" in item


def test_search_duplicate_request():
    with TestClient(app) as client:
        response = client.get("/search/movie?q=Godfather")
        assert response.status_code == 200
        response = client.get("/search/movie?q=Godfather")
        assert response.status_code == 200

def test_search_cors_allows_any_origin():
    with TestClient(app) as client:
        response = client.get(
            "/search/movie?q=Star%20Wars",
            headers={"Origin": "https://example.com"},
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"


def test_search_cors_preflight():
    with TestClient(app) as client:
        response = client.options(
            "/search/movie",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"
