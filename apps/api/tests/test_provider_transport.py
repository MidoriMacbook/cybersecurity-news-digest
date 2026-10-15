"""Local transport exercises; these are not real external model runs."""

import json

import httpx
import pytest
from app.providers.editorial import apply_ai_editorial
from app.schemas.models import DigestRequest
from app.services.pipeline import process
from test_pipeline import CONTROL, article


@pytest.mark.parametrize("failure", ["401", "403", "500", "network", "timeout", "json"])
def test_configured_transport_failure_preserves_grounded_fallback(monkeypatch, failure):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret-not-output")
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("LLM_MODEL", "configured-test-model")
    seen = []

    def respond(request):
        seen.append(request)
        if failure == "network":
            raise httpx.ConnectError("private network detail", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private timeout detail", request=request)
        if failure == "json":
            return httpx.Response(200, content=b"not JSON: private provider detail")
        return httpx.Response(int(failure), json={"error": "private provider detail"})

    original = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs)
    )
    data = DigestRequest(control_time=CONTROL, articles=[article()], use_ai=True)
    local = process(data)
    result = apply_ai_editorial(data, local.model_copy(deep=True))
    assert result.mode == "fallback"
    assert result.llm_attempts == len(seen) == 2
    assert result.digest_text == local.digest_text
    assert result.post_text == local.post_text
    assert all(check.passed for check in result.checks)
    assert result.token_usage.total is None
    for request in seen:
        assert str(request.url) == "https://provider.example/v1/chat/completions"
        assert json.loads(request.content)["model"] == "configured-test-model"
    output = result.model_dump_json()
    assert "fixture-secret-not-output" not in output
    assert "private" not in output
