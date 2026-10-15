import re
from datetime import datetime

from app.domain.rules import AD, CYBER, INJECTION, parse_date, safe_sentences, valid_url
from app.schemas.models import Article, Journal
from app.services.extraction import fragments


def qualify(
    article: Article, start: datetime, end: datetime, now: str, used_ids: set[str]
) -> Journal:
    row = Journal(
        **{
            key: getattr(article, key)
            for key in ["id", "title", "source", "source_type", "url", "published_at"]
        },
        status="accepted",
        missing_fields=[k for k, v in article.model_dump().items() if not v and k != "read_error"],
        processed_at=now,
    )
    if article.read_error:
        row.status = "source_unavailable"
        row.exclusion_reason = "Источник пропущен: ошибка чтения"
        row.errors.append(article.read_error)
        return row
    if row.missing_fields:
        row.warnings.append("Поля отсутствуют: " + ", ".join(row.missing_fields))
    date = parse_date(article.published_at)
    if date is None:
        invalid = False
        if article.published_at:
            try:
                invalid = datetime.fromisoformat(article.published_at).tzinfo is not None
            except ValueError:
                invalid = True
        row.status = "invalid_date" if invalid else "excluded_unknown_date"
        row.exclusion_reason = (
            "Некорректная дата" if invalid else "Дата отсутствует или не содержит часового пояса"
        )
        return row
    row.period_check = start < date <= end
    if not row.period_check:
        row.status, row.exclusion_reason = (
            "excluded_outside_period",
            "Дата вне периода (начало, конец]",
        )
    elif not article.text or len(article.text.strip()) < 60:
        row.status, row.exclusion_reason = (
            "insufficient_text",
            "Недостаточно полного текста для подтверждения фактов",
        )
    elif not article.id or not article.title or not article.source or not valid_url(article.url):
        row.status, row.exclusion_reason = (
            "validation_failed",
            "Нет идентификатора, заголовка, источника или безопасной ссылки",
        )
    elif article.id in used_ids:
        row.status, row.exclusion_reason = (
            "validation_failed",
            "Повтор идентификатора входной записи",
        )
    else:
        used_ids.add(article.id)
        if INJECTION.search(article.text):
            row.warnings.append("Посторонняя инструкция обнаружена и исключена из извлечения")
        row.relevance = bool(CYBER.search(" ".join(safe_sentences(article.text))))
        explicit_date = re.search(
            r"(?:произош\w*|начал\w*|дата события)\s+(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})",
            article.text,
            re.IGNORECASE,
        )
        old_event = False
        if explicit_date:
            try:
                date_value = datetime.strptime(
                    explicit_date[1], "%Y-%m-%d" if "-" in explicit_date[1] else "%d.%m.%Y"
                ).date()
                old_event = date_value < start.date()
            except ValueError:
                pass
        updated = bool(
            re.search(
                r"обновлен|новые факты|выпущен|исправлен|опубликован\w* нов\w* (?:отч[её]т|сведен)|нов\w* масштаб",
                article.text,
                re.IGNORECASE,
            )
        )
        if len(re.findall(r"[А-Яа-яЁё]", " ".join(safe_sentences(article.text)))) < 30:
            row.status, row.exclusion_reason = (
                "validation_failed",
                "Недостаточно фактического текста на русском; спекулятивный перевод отключён",
            )
        elif old_event and not updated:
            row.status, row.exclusion_reason = (
                "excluded_outside_period",
                "Старое событие без явно указанных новых существенных фактов",
            )
        elif not row.relevance or AD.search(article.text):
            row.status, row.exclusion_reason = (
                "excluded_irrelevant",
                "Реклама или нет подтверждаемого содержания по ИБ",
            )
        elif re.search(
            r"(?:ранее|в прошлом|в 20\d\d году)", article.text, re.IGNORECASE
        ) and not re.search(
            r"обновлен|новые факты|сегодня|выпущен|исправлен", article.text, re.IGNORECASE
        ):
            row.status, row.exclusion_reason = (
                "validation_failed",
                "Старое событие без новых существенных фактов",
            )
        elif not fragments(article):
            row.status, row.exclusion_reason = (
                "insufficient_text",
                "Нет компактных проверяемых предложений или законченных частей",
            )
        else:
            row.fact_check = True
    return row
