"""Regressions motivated by real AI failures; transports here are simulated."""

import json

import httpx
import pytest
from app.main import create_app
from app.providers.editorial import apply_ai_editorial
from app.providers.llm import OpenAICompatibleProvider
from app.providers.storage import Storage
from app.schemas.models import DigestRequest
from app.services.pipeline import process
from fastapi.testclient import TestClient
from test_contest_pipeline import transport
from test_pipeline import CONTROL, article


@pytest.mark.parametrize("failure", ["http", "timeout", "grounding"])
def test_failed_attempt_has_safe_diagnostic_category(monkeypatch, failure):
    monkeypatch.setenv("LLM_API_KEY", "fixture-private-key")

    def call(self, payload):
        if failure == "http":
            response = httpx.Response(
                429,
                request=httpx.Request("POST", "https://provider.example/v1"),
                json={"error": "fixture-private-key private provider detail"},
            )
            response.raise_for_status()
        if failure == "timeout":
            raise httpx.ReadTimeout("fixture-private-key private timeout detail")
        return transport(payload, corruption="number")

    monkeypatch.setattr(OpenAICompatibleProvider, "request_json", call)
    data = DigestRequest(control_time=CONTROL, articles=[article()], use_ai=True)
    result = apply_ai_editorial(data, process(data))
    failed = [row for row in result.metrics.model_attempts if not row["valid"]]
    assert failed
    expected = {
        "http": "http_error",
        "timeout": "deadline_exceeded",
        "grounding": "grounding_error",
    }
    assert all(row.get("error_category") == expected[failure] for row in failed)
    if failure == "grounding":
        assert all(row.get("error_reason") == "numbers_dates_changed" for row in failed)
    if failure == "http":
        assert all(row["http_status"] == 429 for row in failed)
    assert "fixture-private-key" not in result.model_dump_json()
    assert "private provider detail" not in result.model_dump_json()


def test_rewrite_retry_receives_safe_feedback_without_rejected_prose(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-private-key")
    rewrites = []

    def call(self, payload):
        if payload["response_format"]["json_schema"]["name"] == "rewrite_v3":
            rewrites.append(json.loads(json.dumps(payload)))
            if len(rewrites) == 1:
                return transport(payload, corruption="number")
            assert len(payload["messages"]) == 3
            feedback = payload["messages"][-1]["content"]
            assert "grounding_error" in feedback
            assert "дословно совпадать" in feedback
            assert "999" not in feedback
        return transport(payload)

    monkeypatch.setattr(OpenAICompatibleProvider, "request_json", call)
    data = DigestRequest(control_time=CONTROL, articles=[article()], use_ai=True)
    result = apply_ai_editorial(data, process(data))
    assert result.mode == "ai"
    assert len(rewrites) == 2
    assert len(rewrites[0]["messages"]) == 2
    assert result.llm_attempts == 4


def test_transient_fallback_can_retry_and_keeps_saved_result_and_idempotency(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-private-key")
    calls = []
    broken = True

    def call(self, payload):
        calls.append(payload)
        if broken:
            raise httpx.ConnectError("temporary outage")
        return transport(payload)

    monkeypatch.setattr(OpenAICompatibleProvider, "request_json", call)
    api = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'retry.db'}")))
    body = DigestRequest(control_time=CONTROL, articles=[article()], use_ai=True).model_dump()
    headers = {"Idempotency-Key": "first-attempt"}
    failed = api.post("/api/v1/digest", json=body, headers=headers).json()
    assert failed["mode"] == "fallback"
    broken = False
    succeeded = api.post("/api/v1/digest", json=body).json()
    assert succeeded["mode"] == "ai"
    assert succeeded["digest_id"] != failed["digest_id"]
    assert len(calls) == 5
    repeated = api.post("/api/v1/digest", json=body).json()
    assert repeated == succeeded
    assert len(calls) == 5
    assert api.get(f"/api/v1/digest/{failed['digest_id']}").json() == failed
    assert api.post("/api/v1/digest", json=body, headers=headers).json() == failed
    assert len(calls) == 5


def test_legacy_fallback_does_not_shadow_successful_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-private-key")
    data = DigestRequest(control_time=CONTROL, articles=[article()], use_ai=True)
    storage = Storage(f"sqlite:///{tmp_path / 'legacy.db'}")
    legacy = process(data)
    legacy.mode = "fallback"
    legacy.llm_attempts = 2
    storage.save(data, legacy, None)
    monkeypatch.setattr(
        OpenAICompatibleProvider, "request_json", lambda self, payload: transport(payload)
    )
    api = TestClient(create_app(storage))
    result = api.post("/api/v1/digest", json=data.model_dump()).json()
    assert result["mode"] == "ai"
    assert result["digest_id"] != legacy.digest_id
    assert api.get(f"/api/v1/digest/{legacy.digest_id}").json() == legacy.model_dump(mode="json")
    assert api.post("/api/v1/digest", json=data.model_dump()).json() == result


def test_in_flight_same_key_calls_return_the_first_committed_outcome(tmp_path):
    storage = Storage(f"sqlite:///{tmp_path / 'in-flight.db'}")
    data = DigestRequest(control_time=CONTROL, articles=[article()], use_ai=True)
    # Both requests can miss before either of their model calls completes.
    assert storage.find(data, "same-request") is None
    assert storage.find(data, "same-request") is None
    first = process(data).model_copy(update={"digest_id": "fallback-first", "mode": "fallback"})
    second = process(data).model_copy(update={"digest_id": "fallback-second", "mode": "fallback"})
    committed = storage.save(data, first, "same-request")
    concurrent = storage.save(data, second, "same-request")
    assert concurrent == committed
    assert storage.find(data, "same-request") == concurrent
