import asyncio

import httpx
import pytest
from app.main import create_app
from app.providers.llm import OpenAICompatibleProvider
from app.providers.storage import Storage


def test_llm_total_deadline_cancels_slow_drip(monkeypatch):
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                await asyncio.sleep(0.02)
                yield b" "

    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=SlowStream()))
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs)
    )
    monkeypatch.setattr("app.providers.llm.LLM_DEADLINE_SECONDS", 0.05)
    with pytest.raises(TimeoutError):
        OpenAICompatibleProvider().request_json({})


def test_llm_body_limit(monkeypatch):
    class LargeStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * 1_000_001

    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=LargeStream()))
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs)
    )
    with pytest.raises(ValueError, match="body limit"):
        OpenAICompatibleProvider().request_json({})


def test_upload_total_deadline(tmp_path, monkeypatch):
    app = create_app(Storage(f"sqlite:///{tmp_path / 'deadline.db'}"))
    monkeypatch.setattr("app.main.UPLOAD_DEADLINE_SECONDS", 0.03)

    async def body():
        await asyncio.sleep(0.1)
        yield b"{}"

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as api:
            return await api.post(
                "/api/v1/digest", content=body(), headers={"Content-Type": "application/json"}
            )

    assert asyncio.run(request()).status_code == 408
