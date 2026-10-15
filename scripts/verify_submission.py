"""Save reproducible stage-one fixtures, responses and acceptance verdicts."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.services.ingestion import export_csv

CONTROL = "2026-10-14T18:00:00+03:00"


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def call(base: str, path: str, body: dict | None = None) -> dict:
    request = Request(
        base.rstrip("/") + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def mandatory_cases() -> list[tuple[str, str, list[dict]]]:
    def load(name: str) -> list[dict]:
        return json.loads((ROOT / "data/demo" / (name + ".json")).read_text(encoding="utf-8"))

    valid = load("duplicate_event")[0]
    old = {**valid, "id": "outside", "published_at": "2026-10-13T18:00:00+03:00"}
    archive = {
        **valid,
        "id": "archive",
        "title": "Архивная кибератака",
        "text": "Атака произошла 2026-10-01. Организация подтвердила утечку данных своих клиентов.",
        "url": "https://example.org/demo/archive",
    }
    update = {
        **archive,
        "id": "update",
        "url": "https://example.org/demo/update",
        "text": archive["text"] + " Выпущено исправление для сервера.",
    }
    unavailable = {
        "id": "unavailable-demo",
        "url": "https://not-allowed.example/demo",
        "read_error": "Учебная ошибка чтения: источник недоступен.",
    }
    return [
        ("duplicate", "Повтор одного события", load("duplicate_event")),
        ("fewer_than_five", "Менее пяти событий", [valid]),
        ("empty", "Нет подходящих новостей", load("no_relevant_news")),
        ("period_and_update", "Публикация вне периода и новые факты", [old, archive, update]),
        ("incomplete", "Только заголовок или обрывок", load("incomplete_article")),
        ("conflict", "Противоречивые сообщения", load("conflicting_sources")),
        ("unavailable", "Недоступный источник и остальные материалы", [unavailable, valid]),
        ("injection", "Посторонняя инструкция в новости", load("prompt_injection")),
    ]


def verdict(name: str, result: dict) -> bool:
    if not all(c["passed"] for c in result["checks"]):
        return False
    events, journal = result["events"], result["journal"]
    both = result["digest_text"] + result["post_text"]
    if name == "duplicate":
        return (
            len(events) == 1
            and len(events[0]["source_ids"]) == 2
            and all(
                s["url"] in result["digest_text"] and s["url"] in result["post_text"]
                for s in result["sources"]
            )
        )
    if name == "fewer_than_five":
        return len(events) == 1 and any("Выбрано 1" in w for w in result["warnings"])
    if name == "empty":
        return not events and "Нет подходящих" in both
    if name == "period_and_update":
        rows = {r["id"]: r for r in journal}
        return (
            rows["outside"]["status"] == rows["archive"]["status"] == "excluded_outside_period"
            and rows["update"]["status"] == "included_in_digest"
        )
    if name == "incomplete":
        return not events and all(r["exclusion_reason"] for r in journal)
    if name == "conflict":
        return (
            len(events) == 1
            and bool(events[0]["conflicts"])
            and all(
                "100" in t and "200" in t and "Предвар" in t
                for t in [result["digest_text"], result["post_text"]]
            )
        )
    if name == "unavailable":
        return len(events) == 1 and any(
            r["status"] == "source_unavailable" and r["errors"] for r in journal
        )
    return (
        len(events) == 1
        and "Игнорируй" not in both
        and "другой адрес" not in both
        and any(r["warnings"] for r in journal)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Сохранить восемь обязательных проверок для сдачи")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/submission")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()
    records = []
    for name, label, articles in mandatory_cases():
        folder = args.output / name
        folder.mkdir(exist_ok=True)
        body = {"articles": articles, "control_time": CONTROL, "use_ai": False}
        save_json(folder / "input.json", body)
        result = call(args.base_url, "/api/v1/digest", body)
        save_json(folder / "result.json", result)
        (folder / "digest.txt").write_text(result["digest_text"], encoding="utf-8")
        (folder / "post.txt").write_text(result["post_text"], encoding="utf-8")
        (folder / "email.html").write_text(result["email_preview_html"], encoding="utf-8")
        (folder / "journal.csv").write_text(export_csv(result["journal"]), encoding="utf-8-sig")
        passed = verdict(name, result)
        record = {
            "scenario": name,
            "description": label,
            "passed": passed,
            "run_at": result["created_at"],
            "model": result["model_name"],
            "model_version": result["model_version"],
            "prompt_version": result["prompt_version"],
            "settings": {"control_time": CONTROL, "event_limit": 5, "use_ai": False},
            "metrics": result["metrics"],
        }
        save_json(folder / "verdict.json", record)
        records.append(record)
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    summary = {
        "started_at": started,
        "completed_at": datetime.now(UTC).isoformat(),
        "synthetic_inputs": True,
        "live_ai_tested": False,
        "checks": records,
        "passed": sum(r["passed"] for r in records),
        "total": len(records),
    }
    save_json(args.output / "summary.json", summary)
    sample = call(args.base_url, "/api/v1/digest/demo", {})
    save_json(args.output / "sample-result.json", sample)
    (args.output / "sample-digest.txt").write_text(sample["digest_text"], encoding="utf-8")
    (args.output / "sample-post.txt").write_text(sample["post_text"], encoding="utf-8")
    (args.output / "sample-email.html").write_text(sample["email_preview_html"], encoding="utf-8")
    (args.output / "sample-journal.csv").write_text(
        export_csv(sample["journal"]), encoding="utf-8-sig"
    )
    print(f"{summary['passed']}/{summary['total']} passed; {args.output}")
    if summary["passed"] != summary["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
