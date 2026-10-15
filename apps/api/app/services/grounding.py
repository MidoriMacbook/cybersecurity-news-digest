"""Conservative mechanical gates around a separate probabilistic semantic check."""

import re
from datetime import datetime

from app.domain.rules import INJECTION, PRELIMINARY
from app.schemas.models import GroundedSentence, Result, RewrittenCopy, SemanticVerification

NEGATION = re.compile(r"\bне\b|\bнет\b|отрица|опроверг|отсутств", re.IGNORECASE)
NUMBERS = re.compile(r"\d+(?:[.,]\d+)?")
WORDS = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё-]*")
STOP = {
    "для",
    "при",
    "что",
    "это",
    "как",
    "из",
    "на",
    "по",
    "во",
    "за",
    "об",
    "со",
    "от",
    "и",
    "а",
    "в",
    "с",
    "к",
    "о",
    "у",
}


def vocabulary(text: str) -> set[str]:
    # Morphological prefixes allow inflection and word order changes; novel vocabulary
    # deliberately falls back rather than relying solely on a model's assurance.
    return {word.casefold()[:5] for word in WORDS.findall(text) if word.casefold() not in STOP}


def sentence_rows(copy: RewrittenCopy) -> list[tuple[str, GroundedSentence]]:
    return [
        (f"{event.event_id}:{channel}:{index}", sentence)
        for event in copy.events
        for channel in ("digest", "post")
        for index, sentence in enumerate(getattr(event, channel))
    ]


def verify_copy(result: Result, copy: RewrittenCopy) -> None:
    if [item.event_id for item in copy.events] != [event.event_id for event in result.events]:
        raise ValueError("Rewrite must cover the selected event order exactly once")
    for event, rewritten in zip(result.events, copy.events, strict=True):
        allowed = {item.model_dump_json() for item in event.evidence}
        for channel in ("digest", "post"):
            sentences = getattr(rewritten, channel)
            used = set()
            output = " ".join(sentence.text for sentence in sentences)
            for sentence in sentences:
                if INJECTION.search(sentence.text) or re.search(r"https?://|[<>]", sentence.text):
                    raise ValueError("Prose may not contain instructions, links or markup")
                quoted = {item.model_dump_json() for item in sentence.evidence}
                if len(quoted) != len(sentence.evidence) or not quoted <= allowed:
                    raise ValueError("Unknown ID, source URL or supporting fragment")
                used |= quoted
                source = " ".join(item.fragment for item in sentence.evidence)
                if set(NUMBERS.findall(sentence.text)) != set(NUMBERS.findall(source)):
                    raise ValueError("Numbers and dates must be preserved")
                if not vocabulary(sentence.text) <= vocabulary(source):
                    raise ValueError("Unsupported entity, action or vocabulary")
                if (
                    NEGATION.search(source) or PRELIMINARY.search(source)
                ) and sentence.text != source:
                    raise ValueError("Uncertainty and negation must remain verbatim")
                if not vocabulary(source) <= vocabulary(sentence.text):
                    raise ValueError("A source fact, role or consequence was omitted")
            if used != allowed:
                raise ValueError("A fact or caveat was omitted")
            for evidence in event.evidence:
                if (
                    NEGATION.search(evidence.fragment) or PRELIMINARY.search(evidence.fragment)
                ) and evidence.fragment not in output:
                    raise ValueError("A qualification was removed")
    if len(render_copy(result, copy, False).replace("\r", "")) > 12000:
        raise ValueError("Rewrite exceeded response bound")


def verify_semantics(copy: RewrittenCopy, verification: SemanticVerification) -> None:
    expected = dict(sentence_rows(copy))
    verdicts = {row.sentence_id: row for row in verification.sentences}
    if len(verdicts) != len(verification.sentences) or set(verdicts) != set(expected):
        raise ValueError("Semantic check must cover each sentence exactly once")
    for sid, verdict in verdicts.items():
        if not verdict.entailed or verdict.evidence != expected[sid].evidence:
            raise ValueError("Semantic verifier rejected or misattributed a sentence")


def render_copy(result: Result, copy: RewrittenCopy, short: bool) -> str:
    start, end = (
        datetime.fromisoformat(result.period_start),
        datetime.fromisoformat(result.control_time),
    )
    header = f"Кибердайджест · {start:%d.%m.%Y %H:%M} - {end:%d.%m.%Y %H:%M} MSK\nКонтрольное время: {end:%d.%m.%Y %H:%M} MSK\nСобытий: {len(copy.events)}.\n\n"
    blocks = []
    for index, (event, rewritten) in enumerate(zip(result.events, copy.events, strict=True), 1):
        lines = [f"{index}. {event.title}"]
        if event.is_preliminary:
            lines.append("Предварительная информация.")
        lines.extend(event.conflicts)
        for sentence in rewritten.post if short else rewritten.digest:
            attribution = ", ".join(dict.fromkeys(item.source_id for item in sentence.evidence))
            lines.append(f"[{attribution}] {sentence.text}")
        for sid in event.source_ids:
            url = next(item.url for item in event.evidence if item.source_id == sid)
            lines.append(f"[{sid}] {url}")
        if not short:
            lines.append("Обоснование выбора и подтверждающие фрагменты доступны в журнале.")
        blocks.append("\n".join(lines))
    return header + "\n\n".join(blocks)
