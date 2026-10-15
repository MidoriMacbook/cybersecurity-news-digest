import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import ENGINE_VERSION, PROMPT_VERSION, execution_fingerprint
from app.domain.rules import is_demo_url
from app.schemas.models import DigestRequest, EditorialPlan, Event, Metrics, Result
from app.services.composition import email_html, render, without_urls
from app.services.editorial import apply_editorial_copy, editorial_groups
from app.services.events import extract_event, group_events, rank_events
from app.services.normalization import normalize
from app.services.qualification import qualify


def process(
    request: DigestRequest, check: bool = True, editorial_plan: EditorialPlan | None = None
) -> Result:
    started = time.monotonic()
    now = datetime.now(UTC).isoformat()
    end = datetime.fromisoformat(request.control_time).astimezone(ZoneInfo(request.timezone))
    start = end - timedelta(hours=24)
    normalized = [normalize(article) for article in request.articles]
    used_ids: set[str] = set()
    journal = [qualify(article, start, end, now, used_ids) for article in normalized]
    pairs = list(zip(normalized, journal, strict=True))
    groups = editorial_groups(editorial_plan, pairs) if editorial_plan else group_events(pairs)
    extracted = [extract_event(key, group, end) for key, group in groups.items()]
    events = (
        [apply_editorial_copy(event, editorial_plan) for event in extracted]
        if editorial_plan
        else rank_events(extracted)
    )
    warnings = ["Информационный дайджест; не является официальной рекомендацией."]
    if any(is_demo_url(a.url) for a in normalized):
        warnings.append(
            "Синтетическая демонстрация: example.org — учебные ссылки, не реальные новости."
        )
    selected: list[Event] = []
    for event in events:
        if len(selected) >= request.event_limit:
            break
        candidate = selected + [event]
        if (
            len(without_urls(render(candidate, start, end, sources=normalized))) <= 4000
            and len(without_urls(render(candidate, start, end, short=True, sources=normalized)))
            <= 2000
        ):
            selected.append(event)
        else:
            warnings.append(
                "Группа "
                + event.event_id
                + " не помещается в лимиты без потери цитат, чисел и оговорок."
            )
    chosen = {e.event_id for e in selected}
    for row in journal:
        if row.event_id in chosen:
            if row.status != "grouped_duplicate":
                row.status = "included_in_digest"
            row.inclusion_reason = next(
                e.selection_reason for e in selected if e.event_id == row.event_id
            )
        elif row.event_id:
            row.exclusion_reason = "Не выбрана: лимит событий или длины; группа остаётся в журнале"
    if len(selected) < request.event_limit:
        warnings.append(
            f"Выбрано {len(selected)} из максимум {request.event_limit}: остальные материалы не прошли проверки или лимиты форматов."
        )
    text = render(selected, start, end, sources=normalized)
    result = Result(
        digest_id="digest-" + execution_fingerprint(request)[:24],
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        control_time=end.isoformat(),
        timezone=request.timezone,
        events=selected,
        event_count=len(selected),
        digest_text=text,
        email_subject=f"Кибердайджест: {len(selected)} событий - {end:%d.%m.%Y}",
        email_preview_html=email_html(text, end, warnings, len(selected)),
        post_text=render(selected, start, end, short=True, sources=normalized),
        warnings=warnings,
        sources=normalized,
        journal=journal,
        checks=[],
        metrics=Metrics(
            input_count=len(normalized),
            relevant_count=sum(j.relevance for j in journal),
            excluded_count=sum(not j.inclusion_reason for j in journal),
            event_groups=len(events),
            selected_count=len(selected),
            duration_ms=int((time.monotonic() - started) * 1000),
        ),
        model_name="extractive-local",
        model_version=ENGINE_VERSION,
        prompt_version=PROMPT_VERSION,
        created_at=now,
        editorial_plan=editorial_plan,
    )
    if check:
        result.checks = validate_result(result)
    return result


def validate_result(result: Result):
    from app.services.validation import validate_result as validate

    return validate(result)
