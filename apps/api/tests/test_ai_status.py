"""Only committed model executions may confirm the public AI status."""

import json

from app.main import create_app
from app.providers.llm import OpenAICompatibleProvider
from app.providers.storage import Storage
from app.schemas.models import DigestRequest
from app.services.pipeline import process
from fastapi.testclient import TestClient
from test_contest_pipeline import transport
from test_pipeline import CONTROL, article


def saved_run(storage, ident, mode, completed, attempts=3):
    request = DigestRequest(control_time=CONTROL, articles=[article(id=ident)], use_ai=True)
    result = process(request).model_copy(
        update={
            "digest_id": ident,
            "mode": mode,
            "llm_attempts": attempts,
            "model_name": "fixture-model" if mode == "ai" else "extractive-local",
            "prompt_version": "editorial-v3" if mode == "ai" else "pipeline-v1",
            "completed_at": completed,
        }
    )
    return request, storage.save(request, result, None)


def test_configured_health_without_execution_does_not_confirm_ai(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'empty.db'}")))
    assert client.get("/health").json()["execution_status"] == {
        "last_ai_run": None,
        "last_successful_ai_run": None,
    }


def test_real_adapter_result_updates_safe_status_and_survives_new_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    monkeypatch.setenv("LLM_MODEL", "fixture-model")
    monkeypatch.setattr(
        OpenAICompatibleProvider, "request_json", lambda self, payload: transport(payload)
    )
    url = f"sqlite:///{tmp_path / 'persist.db'}"
    client = TestClient(create_app(Storage(url)))
    result = client.post(
        "/api/v1/digest",
        json={"control_time": CONTROL, "articles": [article().model_dump()], "use_ai": True},
    ).json()
    assert result["mode"] == "ai"
    status = TestClient(create_app(Storage(url))).get("/health").json()["execution_status"]
    row = status["last_successful_ai_run"]
    assert row == status["last_ai_run"]
    assert row["completed_at"] == result["completed_at"]
    assert set(row) == {
        "mode",
        "model_name",
        "prompt_version",
        "completed_at",
        "application_version",
    }
    assert "fixture-secret" not in json.dumps(status)
    assert "example.org" not in json.dumps(status)


def test_fallback_keeps_last_success_and_cached_mock_do_not_reorder_status(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    url = f"sqlite:///{tmp_path / 'history.db'}"
    storage = Storage(url)
    request, success = saved_run(storage, "success", "ai", "2026-10-15T14:00:00+00:00")
    saved_run(storage, "failed", "fallback", "2026-10-15T14:01:00+00:00")
    storage.save(request, success, "replay")
    saved_run(storage, "demo", "mock", "2026-10-15T14:02:00+00:00", 0)
    status = TestClient(create_app(storage)).get("/health").json()["execution_status"]
    assert status["last_ai_run"]["mode"] == "fallback"
    assert status["last_successful_ai_run"]["completed_at"] == "2026-10-15T14:00:00+00:00"


def test_late_finishing_save_cannot_replace_a_newer_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    storage = Storage(f"sqlite:///{tmp_path / 'order.db'}")
    saved_run(storage, "new", "ai", "2026-10-15T14:02:00+00:00")
    saved_run(storage, "old", "ai", "2026-10-15T14:01:00+00:00")
    status = TestClient(create_app(storage)).get("/health").json()["execution_status"]
    assert status["last_ai_run"]["completed_at"] == "2026-10-15T14:02:00+00:00"
    assert status["last_successful_ai_run"]["completed_at"] == "2026-10-15T14:02:00+00:00"


def test_configuration_change_and_no_model_call_cannot_confirm_current_ai(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    monkeypatch.setenv("LLM_MODEL", "fixture-model")
    storage = Storage(f"sqlite:///{tmp_path / 'config.db'}")
    saved_run(storage, "success", "ai", "2026-10-15T14:00:00+00:00")
    monkeypatch.setenv("LLM_MODEL", "different-model")
    saved_run(storage, "no-calls", "ai", "2026-10-15T14:02:00+00:00", 0)
    status = TestClient(create_app(storage)).get("/health").json()["execution_status"]
    assert status == {"last_ai_run": None, "last_successful_ai_run": None}


def test_replayed_key_does_not_publish_an_outcome_hidden_by_idempotency(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    storage = Storage(f"sqlite:///{tmp_path / 'key.db'}")
    request = DigestRequest(control_time=CONTROL, articles=[article()], use_ai=True)
    first = process(request).model_copy(
        update={
            "digest_id": "first",
            "mode": "fallback",
            "llm_attempts": 2,
            "completed_at": "2026-10-15T14:00:00+00:00",
        }
    )
    hidden = first.model_copy(
        update={"digest_id": "hidden", "mode": "ai", "completed_at": "2026-10-15T14:01:00+00:00"}
    )
    storage.save(request, first, "bound")
    assert storage.save(request, hidden, "bound").digest_id == "first"
    status = TestClient(create_app(storage)).get("/health").json()["execution_status"]
    assert status["last_ai_run"]["completed_at"] == "2026-10-15T14:00:00+00:00"
    assert status["last_successful_ai_run"] is None


def test_public_status_cannot_discover_saved_materials(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    storage = Storage(f"sqlite:///{tmp_path / 'privacy.db'}")
    saved_run(storage, "unlisted-result-id", "ai", "2026-10-15T14:00:00+00:00")
    status = TestClient(create_app(storage)).get("/health").json()["execution_status"]
    assert "unlisted-result-id" not in json.dumps(status)
    assert "digest_id" not in status["last_ai_run"]
