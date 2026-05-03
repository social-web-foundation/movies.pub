from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_home_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
