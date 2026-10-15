import hashlib
import re
from datetime import datetime, timedelta
from typing import Literal

from app.domain.rules import PRELIMINARY, event_key, parse_date, safe_sentences
from app.schemas.models import Article, Event, Journal, RankingFactors
from app.services.extraction import fragments, named_entities, structured_facts

RANKING_WEIGHTS = {
    "impact": 4,
    "scale": 2,
    "urgency": 2,
    "audience_relevance": 2,
    "source_quality": 1,
    "recency": 1,
    "confirmation": 1,
    "new_facts": 1,
    "completeness": 1,
}


def ranking_score(factors: RankingFactors) -> int:
    return sum(value * RANKING_WEIGHTS[name] for name, value in factors.model_dump().items())


def active_exploitation(text: str) -> bool:
    return any(
        re.search(r"эксплуат|actively exploited", sentence, re.IGNORECASE)
        and not re.search(
            r"отсутств|не эксплуат|не зафикс|не обнаруж|не подтверж|сведений.+нет|неизвест|возможн",
            sentence,
            re.IGNORECASE,
        )
        for sentence in safe_sentences(text)
    )


def group_events(pairs: list[tuple[Article, Journal]]) -> dict[str, list[tuple[Article, Journal]]]:
    groups: dict[str, list[tuple[Article, Journal]]] = {}
    for article, row in pairs:
        if row.status != "accepted":
            continue
        key = event_key(article.title or "", article.text or "")
        if not key.startswith("CVE-"):
            first = safe_sentences(article.text or "")[0]
            first_signature = re.sub(r"\b\d+(?:[.,]\d+)?\b", "<number>", first.casefold())
            entities = named_entities(article.text or "")
            key = (
                key
                + "|"
                + (
                    "+".join(sorted(entities))
                    if entities
                    else hashlib.sha256(first_signature.encode()).hexdigest()[:16]
                )
            )
            for candidate, existing in groups.items():
                if (
                    not candidate.startswith("CVE-")
                    and first == safe_sentences(existing[0][0].text or "")[0]
                    and set(entities) == set(named_entities(existing[0][0].text or ""))
                ):
                    key = candidate
                    break
        groups.setdefault(key, []).append((article, row))
    return groups


def source_quality(article: Article) -> int:
    return 3 if article.source_type in {"official", "vendor", "regulator"} else 1


def extract_event(key: str, group: list[tuple[Article, Journal]], control_time: datetime) -> Event:
    evidence = [e for article, _ in group for e in fragments(article)]
    primary = max(group, key=lambda pair: source_quality(pair[0]))[0]
    quantities: dict[tuple[str, str], dict[str, set[str]]] = {}
    for article, _ in group:
        for sentence in safe_sentences(article.text or ""):
            role = (
                "affected"
                if re.search(r"затронул|пострадал|утечк", sentence, re.IGNORECASE)
                else "customer_base"
                if re.search(r"обслужива", sentence, re.IGNORECASE)
                else "reported"
            )
            for value, metric in re.findall(
                r"(?<![-\w])(\d+(?:[.,]\d+)?)\s+(сервер|запис|пользоват|клиент|устройств|млн|тыс)\w*",
                sentence,
                re.IGNORECASE,
            ):
                quantities.setdefault((role, metric.casefold()), {}).setdefault(
                    article.id or "", set()
                ).add(value)
    polarity = set()
    for article, _ in group:
        text_version = article.text or ""
        if re.search(
            r"(?:утечк\w*|атак\w*|взлом\w*)\s+(?:не было|не подтвержден|не обнаружен)|(?:отрицает|опроверг)\w*\s+(?:утечк|атак|взлом)",
            text_version,
            re.IGNORECASE,
        ):
            polarity.add("denied")
        elif re.search(
            r"подтверд\w*\s+(?:утечк|атак|взлом)|(?:утечк\w*|атак\w*|взлом\w*)\s+(?:подтвержден|затронул)",
            text_version,
            re.IGNORECASE,
        ):
            polarity.add("confirmed")
    conflict = (
        any(
            len(by_source) > 1
            and len({tuple(sorted(values)) for values in by_source.values()}) > 1
            and all(len(values) == 1 for values in by_source.values())
            for by_source in quantities.values()
        )
        or len(polarity) > 1
    )
    text = " ".join(e.fragment for e in evidence)
    preliminary = bool(PRELIMINARY.search(text))
    factors = RankingFactors(
        impact=3
        if active_exploitation(text)
        or re.search(
            r"вымогател|приостанов|зашифрован|похищ|собирали пароли|утечк\w*.+затронул",
            text,
            re.IGNORECASE,
        )
        else 1,
        scale=2 if any(role == "affected" for role, _ in quantities) else 0,
        urgency=3
        if active_exploitation(text) or re.search(r"исправлен|исправление", text, re.IGNORECASE)
        else 1,
        audience_relevance=3,
        source_quality=source_quality(primary),
        recency=3
        if any(
            date is not None and control_time - date <= timedelta(hours=6)
            for date in [parse_date(a.published_at) for a, _ in group]
        )
        else 1,
        confirmation=0,
        new_facts=3
        if re.search(r"выпущен|исправлен|новые факты|новый отч[её]т", text, re.IGNORECASE)
        else 1,
        completeness=5
        if all(
            all(v for k, v in a.model_dump().items() if k not in {"read_error", "original_record"})
            for a, _ in group
        )
        else 3,
    )
    confidence: Literal["high", "medium", "low"] = "low" if preliminary or conflict else "medium"
    facts = structured_facts(evidence)
    event = Event(
        event_id="event-" + hashlib.sha256(key.encode()).hexdigest()[:12],
        title=(
            "Предварительные сведения: " + key
            if key.startswith("CVE-")
            else "Предварительное сообщение по ИБ"
        )
        if preliminary
        else fragments(primary)[0].fragment
        if len(fragments(primary)[0].fragment) <= 200
        else "Сообщение по информационной безопасности",
        summary=" ".join(list(dict.fromkeys(e.fragment for e in evidence))[:3]),
        consequences=str(facts["consequences"]),
        affected_entities=list(facts["affected_entities"]),
        affected_systems=list(facts["affected_systems"]),
        numbers=list(facts["numbers"]),
        event_date=facts["event_date"],
        reported_by=list(dict.fromkeys(a.source or "" for a, _ in group)),
        confidence=confidence,
        is_preliminary=preliminary,
        conflicts=["Противоречие: источники расходятся; обе версии сохранены."] if conflict else [],
        source_ids=[a.id or "" for a, _ in group],
        primary_source_id=primary.id,
        selection_reason=f"Баллы: влияние {factors.impact}, масштаб {factors.scale}, срочность {factors.urgency}, аудитория {factors.audience_relevance}, источник {factors.source_quality}.",
        ranking_factors=factors,
        evidence=evidence,
    )
    for i, (_, row) in enumerate(group):
        row.event_id = event.event_id
        row.status = "grouped_duplicate" if i else "accepted"
    event.selection_reason = (
        f"Порядок: взвешенная оценка {ranking_score(factors)}; влияние ×4, масштаб ×2, срочность ×2, аудитория ×2, остальные факторы ×1; при равенстве по ID. Свежесть {factors.recency}, влияние {factors.impact}, срочность {factors.urgency}, новые факты {factors.new_facts}, полнота {factors.completeness}, источник {factors.source_quality}, аудитория {factors.audience_relevance}, масштаб {factors.scale}. Независимость подтверждений не установлена (0)."
        + (" Масштаб последствий в доступных источниках не указан." if not factors.scale else "")
    )
    return event


def rank_events(events: list[Event]) -> list[Event]:
    return sorted(events, key=lambda e: (-ranking_score(e.ranking_factors), e.event_id))
