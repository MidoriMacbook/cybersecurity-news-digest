from app.main import create_app
from app.providers.storage import Storage
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from test_pipeline import CONTROL, article


def test_storage_error_returns_safe_retryable_response(tmp_path, monkeypatch):
    storage = Storage(f"sqlite:///{tmp_path / 'failure.db'}")

    def unavailable(*args, **kwargs):
        raise SQLAlchemyError("private-connection-string")

    monkeypatch.setattr(storage, "find", unavailable)
    client = TestClient(create_app(storage), raise_server_exceptions=False)
    response = client.post(
        "/api/v1/digest", json={"control_time": CONTROL, "articles": [article().model_dump()]}
    )
    assert response.status_code == 503
    assert "private-connection-string" not in response.text
    assert "хранилище" in response.json()["detail"].lower()
