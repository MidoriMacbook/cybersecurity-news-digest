"""Validate model decisions against independently eligible source material."""

import json
import re

from app.schemas.models import Article, EditorialPlan, Event, Evidence, Journal
from app.services.events import group_events
from app.services.extraction import fragments, named_entities


def editorial_groups(
    plan: EditorialPlan, pairs: list[tuple[Article, Journal]]
) -> dict[str, list[tuple[Article, Journal]]]:
    eligible = {a.id: (a, row) for a, row in pairs if row.status == "accepted" and a.id is not None}
    decisions = {d.source_id: d for d in plan.decisions}
    if len(decisions) != len(plan.decisions) or set(decisions) != set(eligible):
        raise ValueError("Editorial decisions must cover every eligible ID exactly once")

    def grounded(evidence: Evidence, ids: list[str]) -> None:
        if evidence.source_id not in ids or evidence.source_id not in eligible:
            raise ValueError("Unknown evidence ID")
        article = eligible[evidence.source_id][0]
        if evidence not in fragments(article):
            raise ValueError("Evidence must be an independently extracted safe sentence")

    for decision in plan.decisions:
        grounded(decision.evidence, [decision.source_id])
    relevant = {sid for sid, decision in decisions.items() if decision.relevant}
    flattened = [sid for group in plan.groups for sid in group.source_ids]
    if len(flattened) != len(set(flattened)) or set(flattened) != relevant:
        raise ValueError("Groups must partition relevant IDs without losing sources")
    source_group = {sid: i for i, group in enumerate(plan.groups) for sid in group.source_ids}
    for known_group in group_events(pairs).values():
        membership = [a.id in relevant for a, _ in known_group]
        if any(membership) and not all(membership):
            raise ValueError("Known event sources must share one relevance decision")
        assigned = {source_group[a.id] for a, _ in known_group if a.id in relevant}
        if len(assigned) > 1:
            raise ValueError("Known reprints must remain in the same event group")
    groups = {}
    for group in sorted(plan.groups, key=lambda g: (g.priority, tuple(g.source_ids))):
        grounded(group.lead, group.source_ids)
        grounded(group.ranking_evidence, group.source_ids)
        articles = [eligible[sid][0] for sid in group.source_ids]
        signatures = [
            {
                c.upper()
                for c in re.findall(
                    r"CVE-\d{4}-\d+", (a.title or "") + " " + (a.text or ""), re.IGNORECASE
                )
            }
            for a in articles
        ]
        if any(signatures) and any(s != signatures[0] for s in signatures):
            raise ValueError("Different CVEs cannot be merged by the model")
        entities = [set(named_entities(a.text or "")) for a in articles]
        if any(entities) and any(e and e != entities[0] for e in entities):
            raise ValueError("Distinct named entities require separate event groups")
        key = "editorial:" + json.dumps(sorted(group.source_ids), ensure_ascii=False)
        groups[key] = [eligible[sid] for sid in group.source_ids]
    for sid, (_, row) in eligible.items():
        if not decisions[sid].relevant:
            row.status = "excluded_irrelevant"
            row.relevance = False
            row.exclusion_reason = (
                "Оценка ИИ: вне темы для аудитории ИБ; фрагмент: "
                + decisions[sid].evidence.fragment
            )
    return groups


def apply_editorial_copy(event: Event, plan: EditorialPlan) -> Event:
    group = next(g for g in plan.groups if set(g.source_ids) == set(event.source_ids))
    # Model chooses the lead; all independently extracted facts and caveats stay.
    event.evidence = [group.lead] + [e for e in event.evidence if e != group.lead]
    event.summary = " ".join(dict.fromkeys(e.fragment for e in event.evidence))
    if not event.is_preliminary:
        event.title = group.lead.fragment if len(group.lead.fragment) <= 200 else event.title
    event.selection_reason = (
        "Оценка ИИ: позиция "
        + str(group.priority + 1)
        + "; основание из источника "
        + group.ranking_evidence.source_id
        + ": «"
        + group.ranking_evidence.fragment
        + "». "
        + event.selection_reason
    )
    return event
