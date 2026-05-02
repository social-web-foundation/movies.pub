from fastapi.testclient import TestClient

from main import app

def test_movie_returns_video():
    with TestClient(app) as client:
        response = client.get("/movie/Q107105860")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/activity+json")
        body = response.json()
        assert body["type"] == "Video"
        assert body["id"] == "https://movies.pub/movie/Q107105860"
        assert body["name"] == "Project Hail Mary"

def test_movie_returns_video_on_warm_cache():
    with TestClient(app) as client:
        response = client.get("/movie/Q487181")
        assert response.status_code == 200
        response = client.get("/movie/Q487181")
        assert response.status_code == 200

def test_movie_head():
    with TestClient(app) as client:
        response = client.head("/movie/Q1306890")
        assert response.status_code == 200
        assert response.content == b""