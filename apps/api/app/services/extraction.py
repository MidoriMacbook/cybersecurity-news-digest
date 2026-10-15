import re
from datetime import date
from typing import TypedDict

from app.domain.rules import PRELIMINARY, safe_sentences
from app.schemas.models import Article, Evidence

CONSEQUENCE = re.compile(
    r"приостанов|останов|недоступ|потер|ущерб|похищ|утек|утечк|раскрыт|зашифрован|собирали пароли|затрону",
    re.IGNORECASE,
)
SYSTEM = re.compile(
    r"\b(?:сервер\w*|шлюз\w*|VPN|RDP|Windows|Linux|браузер\w*|программн\w* пакет\w*|информационн\w* систем\w*)\b",
    re.IGNORECASE,
)
QUALIFIER = re.compile(
    r"подтверд|опроверг|отрица|не эксплуат|не зафикс|не обнаруж|не выяв|"
    r"(?:сведени|данн)[\s\S]{0,100}(?:отсутств|не подтверж|не установ|нет)",
    re.IGNORECASE,
)


class Facts(TypedDict):
    consequences: str
    affected_entities: list[str]
    affected_systems: list[str]
    numbers: list[str]
    event_date: str | None


def fragments(article: Article) -> list[Evidence]:
    assert article.text and article.id and article.url
    sentences = safe_sentences(article.text)
    candidates: list[str] = []
    for sentence in sentences:
        # Long background does not disqualify the whole publication. Complete clauses remain verbatim.
        if PRELIMINARY.search(sentence) and len(sentence) > 1600:
            return []
        clauses = [sentence]
        for clause in clauses:
            if len(clause) <= 1600:
                candidates.append(clause)
    chosen = [
        s
        for i, s in enumerate(candidates)
        if i < 2
        or PRELIMINARY.search(s)
        or QUALIFIER.search(s)
        or CONSEQUENCE.search(s)
        or re.search(r"\d", s)
    ]
    return [
        Evidence(fragment=s, source_id=article.id, url=article.url) for s in dict.fromkeys(chosen)
    ]


def structured_facts(evidence: list[Evidence]) -> Facts:
    text = " ".join(e.fragment for e in evidence)
    consequences = list(
        dict.fromkeys(e.fragment for e in evidence if CONSEQUENCE.search(e.fragment))
    )
    # Named entities require an explicit designation, rather than inferring an organisation from publisher.
    entities, systems = affected_roles(evidence)
    numbers = list(
        dict.fromkeys(
            re.findall(
                r"\b\d+(?:[.,]\d+)?(?:\s+(?:млн|тыс|сервер\w*|запис\w*|пользоват\w*))?",
                re.sub(r"CVE-\d{4}-\d+", "", text),
                re.IGNORECASE,
            )
        )
    )
    dates = re.findall(
        r"(?:дата события\s*[:—-]?\s*|(?:атака|инцидент|утечка|взлом|событие)\s+"
        r"(?:произош\w*|начал\w*|зафиксирован\w*|случил\w*)\s+(?:в\s+)?)(\d{4}-\d{2}-\d{2})\b",
        text,
        re.IGNORECASE,
    )
    valid_dates = []
    for value in dates:
        try:
            valid_dates.append(date.fromisoformat(value).isoformat())
        except ValueError:
            pass
    return {
        "consequences": " ".join(consequences)
        if consequences
        else "Последствия не подтверждены выбранными фрагментами.",
        "affected_entities": list(dict.fromkeys(entities)),
        "affected_systems": systems,
        "numbers": numbers,
        "event_date": valid_dates[0] if len(set(valid_dates)) == 1 else None,
    }


def affected_roles(evidence: list[Evidence]) -> tuple[list[str], list[str]]:
    """Require an impact relation; a mention or a reporting role is insufficient."""
    entities: list[str] = []
    systems: list[str] = []
    for item in evidence:
        for clause in re.split(r"[;.!?]\s*", item.fragment):
            if re.search(
                r"не\s+(?:затрон|пострад|уязвим|атакован|скомпрометирован|подтвержд)|"
                r"предполож|неподтвержд|отрица|опроверг|возможн|предварител",
                clause,
                re.IGNORECASE,
            ):
                continue
            for match in SYSTEM.finditer(clause):
                before, after = clause[: match.start()], clause[match.end() :]
                if re.search(
                    r"(?:уязвим\w*(?:\s+CVE-\d{4}-\d+)?\s+в|атакован\w*|взломан\w*|затронут\w*|скомпрометирован\w*)\s*$",
                    before,
                    re.IGNORECASE,
                ) or re.match(
                    r".{0,40}?(?:приостанов|зашифрован|недоступ|взломан|затронут|скомпрометирован)",
                    after,
                    re.IGNORECASE,
                ):
                    systems.append(match.group())
            for entity in named_entities(clause):
                name = re.escape(entity)
                if re.search(
                    name + r"[»\"]?\s+(?:пострадал|подверг|атакован|взломан|скомпрометирован)",
                    clause,
                    re.IGNORECASE,
                ) or re.search(
                    r"(?:атака на|утечк\w*|взлом\w*|компрометаци\w*)[^.;]{0,35}" + name,
                    clause,
                    re.IGNORECASE,
                ):
                    entities.append(entity)
    return list(dict.fromkeys(entities)), list(dict.fromkeys(systems))


def named_entities(text: str) -> list[str]:
    quoted = re.findall(
        r'(?:компани\w*|организаци\w*|банк\w*)\s+[«"]([^»"]+)[»"]', text, re.IGNORECASE
    )
    explicit = re.findall(r"(?i:компани\w*|организаци\w*|банк\w*)\s+([A-ZА-ЯЁ][\w.-]*)", text)
    return list(dict.fromkeys(quoted + explicit))
