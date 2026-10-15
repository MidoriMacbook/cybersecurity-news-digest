"""A bounded AI editorial pass with deterministic fallback and an audit trail."""

import json
from pathlib import Path

import httpx

from app.providers.llm import OpenAICompatibleProvider, refresh
from app.schemas.models import DigestRequest, EditorialPlan, Result
from app.services.extraction import fragments
from app.services.pipeline import process


def apply_ai_editorial(request: DigestRequest, local: Result) -> Result:
    provider = OpenAICompatibleProvider()
    if not provider.key:
        local.warnings.append("ИИ запрошен, но ключ не настроен: выполнена локальная обработка.")
        return refresh(local)
    eligible_indices = {i for i, row in enumerate(local.journal) if row.event_id}
    eligible = [a for i, a in enumerate(local.sources) if i in eligible_indices]
    if not eligible:
        local.warnings.append("Нет допустимых материалов для этапа ИИ; модель не вызывалась.")
        return refresh(local)
    prompt = json.loads(
        (Path(__file__).resolve().parents[1] / "prompts/editorial_v2.json").read_text(
            encoding="utf-8"
        )
    )
    content = json.dumps(
        {
            "eligible_articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "source": a.source,
                    "source_type": a.source_type,
                    "published_at": a.published_at,
                    "safe_fragments": [e.model_dump() for e in fragments(a)],
                }
                for a in eligible
            ]
        },
        ensure_ascii=False,
    )
    if len(content.encode("utf-8")) > 180_000:
        local.warnings.append(
            "Объём материалов превысил лимит ИИ 180 КБ: сохранена локальная обработка."
        )
        return refresh(local)
    payload = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": prompt["system"] + "\n" + prompt["rules"]},
            {"role": "user", "content": content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "editorial_v2",
                "strict": True,
                "schema": EditorialPlan.model_json_schema(),
            },
        },
        "max_completion_tokens": 8000,
    }
    attempts: list[dict[str, str | int | bool]] = []
    tokens = 0
    usage_available = True
    for attempt in range(2):
        try:
            data = provider.request_json(payload)
            if not isinstance(data, dict) or not isinstance(data.get("usage", {}), dict):
                raise TypeError("Invalid response envelope")
            tokens += int(data.get("usage", {}).get("total_tokens", 0))
            usage_available = usage_available and "total_tokens" in data.get("usage", {})
            plan = EditorialPlan.model_validate_json(data["choices"][0]["message"]["content"])
            result = process(request, editorial_plan=plan)
            if not all(c.passed for c in result.checks):
                raise ValueError("Editorial output failed independent checks")
            attempts.append(
                {
                    "attempt": attempt + 1,
                    "stage": "editorial_v2",
                    "valid": True,
                    "status": "verified",
                    "tokens": tokens,
                }
            )
            result.metrics.mode = "api"
            result.metrics.model_calls = len(attempts)
            result.metrics.tokens_used = tokens
            result.metrics.token_usage_available = usage_available
            result.metrics.model_attempts = attempts
            result.model_name = provider.model
            result.model_version = str(data.get("model") or "provider-configured")
            result.prompt_version = "editorial-v2"
            result.warnings.append(
                "ИИ оценил тему, объединил публикации, определил порядок и выбрал ведущие фрагменты текста. Факты и ссылки проверены по входным материалам; оценки ИИ не являются независимой проверкой новостей."
            )
            for i, row in enumerate(result.journal):
                row.model_name = provider.model
                row.prompt_version = "editorial-v2"
                if i in eligible_indices:
                    row.model_attempts = attempts
            return refresh(result)
        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            StopIteration,
            TimeoutError,
        ):
            attempts.append(
                {
                    "attempt": attempt + 1,
                    "stage": "editorial_v2",
                    "valid": False,
                    "status": "provider_or_grounding_error",
                    "tokens": tokens,
                }
            )
    local.metrics.model_calls = len(attempts)
    local.metrics.tokens_used = tokens
    local.metrics.token_usage_available = False
    local.metrics.model_attempts = attempts
    local.warnings.append(
        "Редакционный ответ ИИ не прошёл проверку за 2 попытки: сохранён локальный выпуск."
    )
    for i, row in enumerate(local.journal):
        if i in eligible_indices:
            row.model_attempts = attempts
    return refresh(local)
