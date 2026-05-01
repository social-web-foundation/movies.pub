from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_livez_returns_no_content():
    response = client.get("/livez")
    assert response.status_code == 204
    assert response.content == b""
