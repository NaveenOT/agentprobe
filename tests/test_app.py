from agentprobe.main import app
from fastapi.testclient import TestClient


def test_app_starts_without_mongodb() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["storage"] == "memory"
    assert isinstance(response.json()["groq_configured"], bool)
