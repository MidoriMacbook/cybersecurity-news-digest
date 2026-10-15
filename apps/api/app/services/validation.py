from datetime import datetime, timedelta

from app.schemas.models import Check, DigestRequest, Result
from app.services.composition import email_html, render


def validate_result(result: Result) -> list[Check]:
    from app.services.pipeline import process

    try:
        end = datetime.fromisoformat(result.control_time)
        start = datetime.fromisoformat(result.period_start)
        period_ok = (
            end.tzinfo is not None
            and end.utcoffset() == timedelta(hours=3)
            and start.utcoffset() == timedelta(hours=3)
            and end - start == timedelta(hours=24)
            and result.period_end == result.control_time
            and result.timezone == "Europe/Moscow"
        )
        regenerated = process(
            DigestRequest(control_time=result.control_time, articles=result.sources, event_limit=5),
            check=False,
            editorial_plan=result.editorial_plan,
        )
        facts_ok = [event.model_dump() for event in result.events] == [
            event.model_dump() for event in regenerated.events[: result.event_count]
        ] and (bool(result.events) or not regenerated.events)
        digest = render(result.events, start, end, sources=result.sources)
        post = render(result.events, start, end, short=True, sources=result.sources)
        formats_ok = (
            result.digest_text == digest
            and result.post_text == post
            and result.email_preview_html
            == email_html(digest, end, result.warnings, result.event_count)
            and result.email_subject
            == f"Кибердайджест: {result.event_count} событий - {end:%d.%m.%Y}"
        )
    except (ValueError, TypeError, StopIteration):
        period_ok = facts_ok = formats_ok = False
    return [
        Check(
            name="Количество событий",
            passed=result.event_count == len(result.events) <= 5,
            details=str(len(result.events)),
        ),
        Check(
            name="Лимит дайджеста",
            passed=len(result.digest_text_without_urls()) <= 4000,
            details=str(len(result.digest_text_without_urls())),
        ),
        Check(
            name="Лимит поста",
            passed=len(result.post_text_without_urls()) <= 2000,
            details=str(len(result.post_text_without_urls())),
        ),
        Check(
            name="Подтверждающие цитаты",
            passed=facts_ok,
            details="Повторное извлечение из входных материалов: факты, числа, оговорки и ссылки",
        ),
        Check(
            name="Согласованные форматы",
            passed=formats_ok,
            details="Текст обоих форматов и HTML письма проверен по цитатам выбранных событий",
        ),
        Check(
            name="Период",
            passed=period_ok,
            details="Строго (начало, конец], 24 часа, явный часовой пояс",
        ),
    ]
