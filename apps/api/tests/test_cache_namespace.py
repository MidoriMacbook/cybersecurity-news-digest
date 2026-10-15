from app.config import execution_fingerprint
from app.main import create_app
from app.providers.llm import OpenAICompatibleProvider
from app.providers.storage import Storage
from app.schemas.models import DigestRequest
from editorial_transport import response_for
from fastapi.testclient import TestClient
from test_pipeline import CONTROL, article


def test_cache_namespace_tracks_key_presence_model_endpoint_and_engine(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    request = DigestRequest(control_time=CONTROL, articles=[article()], use_ai=True)
    original = execution_fingerprint(request)
    api = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'cache.db'}")))
    first = api.post("/api/v1/digest", json=request.model_dump()).json()
    assert first["metrics"]["model_calls"] == 0
    calls = []

    def editorial(self, payload):
        calls.append(payload)
        evidence = {
            "fragment": article().text.split(". ")[0] + ".",
            "source_id": "a",
            "url": article().url,
        }
        plan = {
            "decisions": [{"source_id": "a", "relevant": True, "evidence": evidence}],
            "groups": [
                {"source_ids": ["a"], "lead": evidence, "priority": 0, "ranking_evidence": evidence}
            ],
        }
        return response_for(payload, plan, {"total_tokens": 11})

    monkeypatch.setattr(OpenAICompatibleProvider, "request_json", editorial)
    monkeypatch.setenv("LLM_API_KEY", "super-secret")
    second = api.post("/api/v1/digest", json=request.model_dump()).json()
    assert second["digest_id"] != first["digest_id"]
    assert second["metrics"]["mode"] == "api" and len(calls) == 3
    repeated = api.post("/api/v1/digest", json=request.model_dump()).json()
    assert len(calls) == 3
    assert repeated["started_at"] == second["started_at"]
    assert repeated["completed_at"] == second["completed_at"]
    configured = execution_fingerprint(request)
    assert original != configured
    monkeypatch.setenv("LLM_MODEL", "new-model")
    assert execution_fingerprint(request) != configured
    model_fingerprint = execution_fingerprint(request)
    monkeypatch.setenv("LLM_BASE_URL", "https://other.example/v1")
    assert execution_fingerprint(request) != model_fingerprint
    endpoint_fingerprint = execution_fingerprint(request)
    monkeypatch.setenv("LLM_BASE_URL", "https://user:secret@other.example/v1?token=secret")
    assert execution_fingerprint(request) == endpoint_fingerprint
    monkeypatch.setattr("app.config.ENGINE_VERSION", "new-version")
    assert execution_fingerprint(request) != endpoint_fingerprint
    assert "super-secret" not in str(second)
