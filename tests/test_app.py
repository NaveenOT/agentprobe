import os

from fastapi.testclient import TestClient


def test_app_starts_without_mongodb() -> None:
    os.environ["AGENTPROBE_TEMPLATE_BACKEND"] = "local"
    from agentprobe.config import get_settings

    get_settings.cache_clear()
    from agentprobe.main import app

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["storage"] == "memory"
    assert isinstance(response.json()["groq_configured"], bool)
