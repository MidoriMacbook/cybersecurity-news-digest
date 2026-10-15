import html
import re
from datetime import datetime

from app.domain.rules import PRELIMINARY, parse_date
from app.schemas.models import Article, Event
from app.services.extraction import CONSEQUENCE, QUALIFIER, named_entities


def without_urls(text: str) -> str:
    return re.sub(r"https?://\S+", "", text)


def render(
    events: list[Event],
    start: datetime,
    end: datetime,
    short: bool = False,
    sources: list[Article] | None = None,
) -> str:
    header = f"Кибердайджест · {start:%d.%m.%Y %H:%M} - {end:%d.%m.%Y %H:%M} MSK\nКонтрольное время: {end:%d.%m.%Y %H:%M} MSK\n"
    if not events:
        return header + "Нет подходящих подтверждаемых новостей за выбранный период."
    header += f"Событий: {len(events)}. Число определено отбором, объединением и лимитами; причины доступны в журнале.\n\n"
    blocks = []
    for i, event in enumerate(events, 1):
        registry: dict[str, Article] = {}
        for candidate_source in sources or []:
            published_date = parse_date(candidate_source.published_at)
            if (
                candidate_source.id
                and candidate_source.title
                and candidate_source.source
                and candidate_source.text
                and len(candidate_source.text.strip()) >= 60
                and published_date is not None
                and start < published_date <= end
                and not candidate_source.read_error
                and any(
                    e.source_id == candidate_source.id
                    and e.url == candidate_source.url
                    and e.fragment in (candidate_source.text or "")
                    for e in event.evidence
                )
                and all(
                    e.fragment in candidate_source.text
                    for e in event.evidence
                    if e.source_id == candidate_source.id
                )
            ):
                registry.setdefault(candidate_source.id, candidate_source)
        lines = [f"{i}. {event.title}"]
        if event.is_preliminary:
            lines.append("Предварительная информация.")
        lines.extend(event.conflicts)
        seen: set[str] = set()
        for j, evidence in enumerate(event.evidence):
            # Post removes background, but keeps numeric assertions, conflicts and qualifiers.
            include = (
                not short
                or j == 0
                or PRELIMINARY.search(evidence.fragment)
                or QUALIFIER.search(evidence.fragment)
                or CONSEQUENCE.search(evidence.fragment)
                or bool(named_entities(evidence.fragment))
                or re.search(r"\d", evidence.fragment)
                or bool(event.conflicts)
            )
            if include and evidence.fragment not in seen:
                # The title already contains the lead fact. Keep the quote in evidence,
                # but avoid repeating the same sentence in the public text.
                if evidence.fragment != event.title:
                    if event.conflicts:
                        source = registry.get(evidence.source_id)
                        attribution = source.source if source and not short else evidence.source_id
                        lines.append(f"[{attribution}] {evidence.fragment}")
                    else:
                        lines.append(evidence.fragment)
                seen.add(evidence.fragment)
        if not short:
            if not any(CONSEQUENCE.search(e.fragment) for e in event.evidence):
                lines.append("Последствия: сведения о последствиях в источниках отсутствуют.")
            else:
                lines.append("Последствия приведены выше; обоснование выбора доступно в журнале.")
        for sid in event.source_ids:
            source = registry.get(sid)
            source_url = next(e.url for e in event.evidence if e.source_id == sid)
            if source and not short:
                published = datetime.fromisoformat(source.published_at or "").astimezone(end.tzinfo)
                lines.append(
                    f"{source.source} · {published:%d.%m.%Y %H:%M} MSK · ID: {sid}\n{source_url}"
                )
            else:
                lines.append(f"[{sid}] {source_url}")
        blocks.append("\n".join(lines))
    return header + "\n\n".join(blocks)


def email_html(
    text: str, end: datetime, warnings: list[str] | None = None, event_count: int = 0
) -> str:
    subject = f"Кибердайджест: {event_count} событий - {end:%d.%m.%Y}"
    safe_text = html.escape(text)
    safe_text = re.sub(
        r"https?://[^\s<]+",
        lambda match: '<a href="' + match[0] + '">' + match[0] + "</a>",
        safe_text,
    )
    notes = "".join("<li>" + html.escape(warning) + "</li>" for warning in warnings or [])
    return f"<!doctype html><html lang='ru'><meta charset='utf-8'><body><h1>{html.escape(subject)}</h1><p>Контрольное время: {html.escape(end.isoformat())}</p><p>Событий: {event_count}</p><pre style='white-space:pre-wrap'>{safe_text}</pre><ul>{notes}</ul></body></html>"
