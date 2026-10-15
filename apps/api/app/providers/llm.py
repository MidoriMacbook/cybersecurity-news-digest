import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.models import Article, Evidence, Result
from app.services.composition import email_html
from app.services.validation import validate_result

LLM_DEADLINE_SECONDS = 12.0
LLM_MAX_RESPONSE_BYTES = 1_000_000


class ExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fragments: list[Evidence] = Field(max_length=100)


class ExtractionProvider(Protocol):
    def extract(
        self, articles: list[Article]
    ) -> tuple[ExtractionOutput | None, list[dict[str, str | int | bool]], int]: ...


class OpenAICompatibleProvider:
    def __init__(self) -> None:
        self.key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4.1-mini")
        self.deadline_seconds = LLM_DEADLINE_SECONDS

    def request_json(self, payload: dict):
        async def bounded():
            async with (
                httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client,
                client.stream(
                    "POST",
                    self.base_url + "/chat/completions",
                    headers={"Authorization": "Bearer " + self.key},
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > LLM_MAX_RESPONSE_BYTES:
                        raise ValueError("Provider response exceeded body limit")
                return json.loads(body)

        async def deadline():
            return await asyncio.wait_for(
                bounded(), timeout=min(LLM_DEADLINE_SECONDS, self.deadline_seconds)
            )

        return asyncio.run(deadline())

    def extract(
        self, articles: list[Article]
    ) -> tuple[ExtractionOutput | None, list[dict[str, str | int | bool]], int]:
        prompt = json.loads(
            (Path(__file__).resolve().parents[1] / "prompts/extraction_v1.json").read_text(
                encoding="utf-8"
            )
        )
        attempts: list[dict[str, str | int | bool]] = []
        tokens = 0
        sources = {a.id: a for a in articles}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt["system"] + "\n" + prompt["rules"]},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"untrusted_articles": [a.model_dump() for a in articles]},
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction_v1",
                    "strict": True,
                    "schema": ExtractionOutput.model_json_schema(),
                },
            },
            "max_completion_tokens": 2000,
        }
        for attempt in range(2):
            try:
                data = self.request_json(payload)
                if not isinstance(data, dict) or not isinstance(data.get("usage", {}), dict):
                    raise TypeError("Malformed provider response envelope")
                tokens += int(data.get("usage", {}).get("total_tokens", 0))
                output = ExtractionOutput.model_validate_json(
                    data["choices"][0]["message"]["content"]
                )
                if not output.fragments or any(
                    e.source_id not in sources
                    or e.url != sources[e.source_id].url
                    or e.fragment not in (sources[e.source_id].text or "")
                    for e in output.fragments
                ):
                    raise ValueError("Ungrounded extraction")
                attempts.append(
                    {
                        "attempt": attempt + 1,
                        "stage": "extraction_v1",
                        "valid": True,
                        "status": "verified",
                        "tokens": tokens,
                    }
                )
                return output, attempts, tokens
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, TimeoutError):
                attempts.append(
                    {
                        "attempt": attempt + 1,
                        "stage": "extraction_v1",
                        "valid": False,
                        "status": "provider_or_grounding_error",
                        "tokens": tokens,
                    }
                )
        return None, attempts, tokens


def apply_ai_verification(result: Result) -> Result:
    provider = OpenAICompatibleProvider()
    if not provider.key:
        result.warnings.append(
            "ИИ запрошен, но LLM_API_KEY не задан: применён локальный экстрактивный режим."
        )
        return refresh(result)
    # AI is an additional extraction check. Its prose never replaces grounded source fragments.
    selected_ids = {sid for event in result.events for sid in event.source_ids}
    selected = [
        a.model_copy(
            update={
                "text": "\n".join(
                    dict.fromkeys(
                        e.fragment
                        for event in result.events
                        for e in event.evidence
                        if e.source_id == a.id
                    )
                )
            }
        )
        for a in result.sources
        if a.id in selected_ids
    ]
    if not selected:
        result.warnings.append("Нет выбранных источников для проверки ИИ; модель не вызывалась.")
        return refresh(result)
    output, attempts, tokens = provider.extract(selected)
    result.metrics.model_calls = len(attempts)
    result.metrics.model_attempts = attempts
    result.metrics.tokens_used = tokens
    if output:
        result.metrics.mode = "api"
        result.model_name = provider.model
        result.model_version = "provider-configured"
        result.warnings.append(
            f"ИИ проверил {len(output.fragments)} дословных фрагментов; итог сохранён экстрактивно, без свободного дополнения фактов."
        )
    else:
        result.warnings.append(
            "Ответ ИИ не прошёл схему/проверку источников за 2 попытки: сохранён локальный результат."
        )
    for row in result.journal:
        row.model_name = result.model_name
        if row.id in selected_ids:
            row.model_attempts = attempts
    return refresh(result)


def refresh(result: Result) -> Result:
    result.email_preview_html = email_html(
        result.digest_text,
        datetime.fromisoformat(result.control_time),
        result.warnings,
        result.event_count,
    )
    result.checks = validate_result(result)
    return result
