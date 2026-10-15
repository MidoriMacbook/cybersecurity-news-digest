from datetime import datetime

import httpx
import pytest
from app.providers.sources import fetch
from app.schemas.models import DigestRequest
from app.services.pipeline import process, validate_result
from test_pipeline import CONTROL, article


def test_non_numeric_conflict_and_html_escaping():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    title="Сообщение об утечке",
                    text="Учебная организация «Кедр» подтвердила утечку данных. Расследование инцидента информационной безопасности продолжается.",
                ),
                article(
                    id="b",
                    title="Сообщение об утечке",
                    text="Учебная организация «Кедр» опровергла утечку данных. Проверка информационной безопасности не выявила происшествий.",
                ),
            ],
        )
    )
    assert result.events[0].conflicts
    assert "опровергла" in result.post_text and "подтвердила" in result.post_text
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[article(title="<script>alert(1)</script> CVE-2026-12345")],
        )
    )
    assert "<script>" not in result.email_preview_html
    assert "alert(1)" not in result.email_preview_html


def test_fabricated_metadata_caveats_and_period_rejected():
    result = process(DigestRequest(control_time=CONTROL, articles=[article()]))
    result.events[0].consequences = "Пострадали миллионы"
    assert not all(c.passed for c in validate_result(result))
    result = process(DigestRequest(control_time=CONTROL, articles=[article()]))
    result.period_start = datetime.fromisoformat(result.period_end).isoformat()
    assert not all(c.passed for c in validate_result(result))


def test_source_body_limit(monkeypatch):
    monkeypatch.setenv("SOURCE_ALLOWED_HOSTS", "example.com")
    monkeypatch.setattr("app.providers.sources.public_addresses", lambda host: ["93.184.216.34"])

    def stream(client, method, url, **kwargs):
        class Context:
            def __enter__(self):
                return httpx.Response(
                    200,
                    content=b"x" * 1_000_001,
                    headers={"content-type": "text/html"},
                    request=httpx.Request("GET", url),
                )

            def __exit__(self, *args):
                return False

        return Context()

    monkeypatch.setattr(httpx.Client, "stream", stream)
    with pytest.raises(ValueError, match="лимит"):
        fetch("https://example.com/news")
