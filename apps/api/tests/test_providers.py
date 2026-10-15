import json
import socket

import httpx
import pytest
from app.providers.llm import OpenAICompatibleProvider, apply_ai_verification
from app.providers.sources import fetch
from app.schemas.models import DigestRequest
from app.services.pipeline import process
from app.services.validation import validate_result
from test_pipeline import CONTROL, article


def test_ai_switch_invokes_provider_and_records_calls(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-secret-do-not-export")
    calls = []

    def post(client, url, **kwargs):
        calls.append(kwargs)
        assert kwargs["json"]["response_format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "fragments": [
                                        {
                                            "fragment": article().text.split(". ")[0] + ".",
                                            "source_id": "a",
                                            "url": article().url,
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ],
                "usage": {"total_tokens": 33},
            },
        )

    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "request_json",
        lambda self, payload: post(None, self.base_url, json=payload).json(),
    )
    result = apply_ai_verification(
        process(DigestRequest(control_time=CONTROL, articles=[article()], use_ai=True))
    )
    assert len(calls) == result.metrics.model_calls == 1
    assert result.metrics.tokens_used == 33
    assert result.metrics.mode == "api"
    assert "test-secret-do-not-export" not in result.model_dump_json()
    assert all(check.passed for check in validate_result(result))
    assert "ИИ проверил" in result.email_preview_html


def test_ai_fabricated_quote_retry_bounded(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret")

    def post(client, url, **kwargs):
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "fragments": [
                                        {
                                            "fragment": "Fabricated",
                                            "source_id": "a",
                                            "url": article().url,
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "request_json",
        lambda self, payload: post(None, self.base_url, json=payload).json(),
    )
    result = apply_ai_verification(
        process(DigestRequest(control_time=CONTROL, articles=[article()]))
    )
    assert result.metrics.model_calls == 2
    assert all(not a["valid"] for a in result.metrics.model_attempts)
    assert result.metrics.mode == "mock"
    assert "Fabricated" not in result.model_dump_json()
    assert all(check.passed for check in validate_result(result))
    assert "Ответ ИИ" in result.email_preview_html


def test_dns_pinning_and_redirect_rejected(monkeypatch):
    monkeypatch.setenv("SOURCE_ALLOWED_HOSTS", "example.com")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    seen = []

    def stream(client, method, url, **kwargs):
        seen.append((url, kwargs))

        class Context:
            def __enter__(self):
                return httpx.Response(
                    302,
                    headers={"location": "http://127.0.0.1/"},
                    request=httpx.Request("GET", url),
                )

            def __exit__(self, *args):
                return False

        return Context()

    monkeypatch.setattr(httpx.Client, "stream", stream)
    with pytest.raises(ValueError, match="Перенаправления"):
        fetch("https://example.com/news")
    assert seen[0][0] == "https://93.184.216.34:443/news"
    assert seen[0][1]["headers"]["Host"] == "example.com"
    assert seen[0][1]["extensions"]["sni_hostname"] == b"example.com"


def test_unknown_key_ai_fallback(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    result = apply_ai_verification(
        process(DigestRequest(control_time=CONTROL, articles=[article()]))
    )
    assert result.metrics.model_calls == 0
    assert any("LLM_API_KEY" in warning for warning in result.warnings)
    assert all(check.passed for check in validate_result(result))
    assert "LLM_API_KEY" in result.email_preview_html
