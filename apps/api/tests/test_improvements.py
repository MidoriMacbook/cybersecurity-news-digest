import json

import pytest
from app.providers.llm import OpenAICompatibleProvider
from app.schemas.models import DigestRequest
from app.services.pipeline import process
from test_pipeline import CONTROL, article


def test_five_compact_events_keep_named_dated_sources():
    articles = [
        article(
            id=str(i),
            title=f"CVE-2026-{12000 + i}",
            text=f"Поставщик подтвердил уязвимость CVE-2026-{12000 + i}. Выпущено исправление для сервера.",
            url=f"https://example.org/{i}",
        )
        for i in range(5)
    ]
    result = process(DigestRequest(control_time=CONTROL, articles=articles))
    assert result.event_count == 5
    assert "Поставщик · 14.10.2026 12:00 MSK · ID: 0" in result.digest_text
    assert "Последствия" in result.digest_text
    assert "Баллы" not in result.digest_text
    assert "—" not in result.digest_text
    assert all(c.passed for c in result.checks)


def test_demo_scenarios_and_unknown_name(tmp_path):
    from app.main import create_app
    from app.providers.storage import Storage
    from fastapi.testclient import TestClient

    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'demo.db'}")))
    response = client.get("/api/v1/demo?scenario=conflicting_sources")
    assert response.status_code == 200
    assert response.json()["scenario"] == "conflicting_sources"
    assert len(response.json()["articles"]) == 2
    assert client.get("/api/v1/demo?scenario=../../README").status_code == 422


def test_unavailable_source_survives_into_exported_journal(tmp_path):
    from app.main import create_app
    from app.providers.storage import Storage
    from fastapi.testclient import TestClient

    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'unavailable.db'}")))
    data = client.get("/api/v1/demo?scenario=unavailable_sources").json()
    response = client.post(
        "/api/v1/digest", json={"articles": data["articles"], "control_time": data["control_time"]}
    )
    result = response.json()
    assert result["event_count"] == 1
    skipped = next(j for j in result["journal"] if j["id"] == "unavailable-demo")
    assert skipped["status"] == "source_unavailable"
    assert skipped["errors"]
    assert all(c["passed"] for c in result["checks"])


def test_denied_exploitation_and_customer_base_do_not_inflate_ranking():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="Поставщик подтвердил уязвимость CVE-2026-12345. Сведения об эксплуатации отсутствуют. Компания обслуживает 900 клиентов по действующим договорам."
                )
            ],
        )
    )
    factors = result.events[0].ranking_factors
    assert factors.impact == 1
    assert factors.urgency == 1
    assert factors.scale == 0


def test_actual_operational_harm_ranks_above_patch_without_exploitation():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(),
                article(
                    id="attack",
                    title="Атака вымогателей",
                    url="https://example.org/attack",
                    text="Компания «Кедр» сообщила об атаке вымогателей. Работа информационной системы временно приостановлена.",
                ),
            ],
        )
    )
    assert result.events[0].source_ids == ["attack"]


def test_ai_cannot_split_known_reprints(tmp_path, monkeypatch):
    from app.main import create_app
    from app.providers.storage import Storage
    from fastapi.testclient import TestClient

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    articles = [article(), article(id="b", url="https://example.org/b")]
    plan = plan_for(articles)
    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "request_json",
        lambda self, payload: {"choices": [{"message": {"content": json.dumps(plan)}}]},
    )
    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'split.db'}")))
    data = api_ai(client, articles).json()
    assert data["event_count"] == 1
    assert data["editorial_plan"] is None


def test_ai_cannot_remove_only_one_conflicting_source(tmp_path, monkeypatch):
    from app.main import create_app
    from app.providers.storage import Storage
    from fastapi.testclient import TestClient

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    articles = [
        article(
            text="Предварительно уязвимость CVE-2026-12345 затронула 100 серверов. Проверка продолжается."
        ),
        article(
            id="b",
            url="https://example.org/b",
            text="Уязвимость CVE-2026-12345 затронула 200 серверов. Регулятор проверяет инцидент.",
        ),
    ]
    plan = plan_for(articles)
    plan["decisions"][1]["relevant"] = False
    plan["groups"] = [g for g in plan["groups"] if g["source_ids"] == ["a"]]
    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "request_json",
        lambda self, payload: {"choices": [{"message": {"content": json.dumps(plan)}}]},
    )
    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'conflicting-plan.db'}")))
    data = api_ai(client, articles).json()
    assert data["editorial_plan"] is None
    assert data["events"][0]["conflicts"]
    assert "200" in data["digest_text"] and "100" in data["post_text"]


def test_late_confirmation_and_denial_remain_in_both_formats():
    prefix = "Компания сообщила об инциденте информационной безопасности. Проверка обстоятельств продолжается."
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(title="Проверка атаки", text=prefix + " Поставщик подтвердил атаку."),
                article(
                    id="b",
                    url="https://example.org/b",
                    title="Проверка атаки",
                    text=prefix + " Поставщик опроверг атаку.",
                ),
            ],
        )
    )
    assert result.events[0].conflicts
    for text in [result.digest_text, result.post_text]:
        assert "подтвердил атаку" in text and "опроверг атаку" in text


def test_failed_duplicate_id_cannot_change_source_attribution():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(),
                article(
                    title="Другой материал",
                    source="Другой источник",
                    url="https://example.org/other",
                    read_error="Недоступен",
                    published_at="2026-10-14T16:00:00+03:00",
                ),
            ],
        )
    )
    assert "Другой источник" not in result.digest_text
    assert "Поставщик · 14.10.2026 12:00 MSK" in result.digest_text


@pytest.mark.parametrize(
    "denial", ["Уязвимость не эксплуатируется.", "Сведения об эксплуатации отсутствуют."]
)
def test_exploitation_denial_is_preserved_in_post_and_ranking(denial):
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[article(text="Поставщик подтвердил уязвимость CVE-2026-12345. " + denial)],
        )
    )
    assert result.events[0].ranking_factors.impact == 1
    assert result.events[0].ranking_factors.urgency == 1
    assert denial in result.post_text


def test_source_url_punctuation_is_never_rewritten():
    result = process(
        DigestRequest(control_time=CONTROL, articles=[article(url="https://example.org/а—б")])
    )
    assert "https://example.org/а—б" in result.digest_text
    assert "https://example.org/а—б" in result.post_text
    assert "https://example.org/а—б" in result.email_preview_html


def test_rejected_outside_period_duplicate_cannot_supply_date():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[article(published_at="2026-10-13T16:00:00+03:00"), article()],
        )
    )
    assert "Поставщик · 14.10.2026 12:00 MSK" in result.digest_text
    assert "Поставщик · 13.10.2026 16:00 MSK" not in result.digest_text


def test_ai_ignores_failed_duplicate_record(tmp_path, monkeypatch):
    from app.main import create_app
    from app.providers.storage import Storage
    from fastapi.testclient import TestClient

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    plan = plan_for([article()])

    def response(self, payload):
        from editorial_transport import response_for

        if payload["response_format"]["json_schema"]["name"] == "editorial_v2":
            supplied = json.loads(payload["messages"][1]["content"])["eligible_articles"]
            assert len(supplied) == 1
        return response_for(payload, plan)

    monkeypatch.setattr(OpenAICompatibleProvider, "request_json", response)
    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'failed-duplicate.db'}")))
    data = api_ai(client, [article(text=None, read_error="Недоступен"), article()]).json()
    assert data["event_count"] == 1
    assert data["metrics"]["mode"] == "api"


def test_ai_cannot_merge_distinct_cve_identifiers_in_titles(tmp_path, monkeypatch):
    from app.main import create_app
    from app.providers.storage import Storage
    from fastapi.testclient import TestClient

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    text = "Поставщик подтвердил критическую уязвимость продукта. Выпущено исправление для сервера."
    articles = [
        article(text=text),
        article(id="b", url="https://example.org/b", text=text, title="Уязвимость CVE-2026-54321"),
    ]
    plan = plan_for(articles)
    plan["groups"] = plan["groups"][:1]
    plan["groups"][0]["source_ids"] = ["a", "b"]
    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "request_json",
        lambda self, payload: {"choices": [{"message": {"content": json.dumps(plan)}}]},
    )
    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'title-cve.db'}")))
    data = api_ai(client, articles).json()
    assert data["event_count"] == 2
    assert data["editorial_plan"] is None


def plan_for(articles, relevant=True):
    return {
        "decisions": [
            {
                "source_id": a.id,
                "relevant": relevant,
                "evidence": {
                    "source_id": a.id,
                    "url": a.url,
                    "fragment": a.text.split(". ")[0] + ".",
                },
            }
            for a in articles
        ],
        "groups": [
            {
                "source_ids": [a.id],
                "lead": {"source_id": a.id, "url": a.url, "fragment": a.text.split(". ")[0] + "."},
                "priority": i,
                "ranking_evidence": {
                    "source_id": a.id,
                    "url": a.url,
                    "fragment": a.text.split(". ")[0] + ".",
                },
            }
            for i, a in enumerate(reversed(articles))
        ]
        if relevant
        else [],
    }


def api_ai(client, articles):
    return client.post(
        "/api/v1/digest",
        json=DigestRequest(control_time=CONTROL, articles=articles, use_ai=True).model_dump(),
    )


def test_ai_editorial_plan_changes_order_and_is_reproducible(tmp_path, monkeypatch):
    from app.main import create_app
    from app.providers.storage import Storage
    from editorial_transport import response_for
    from fastapi.testclient import TestClient

    monkeypatch.setenv("LLM_API_KEY", "test-key-never-export")
    articles = [
        article(),
        article(
            id="b",
            url="https://example.org/b",
            text="Поставщик подтвердил уязвимость CVE-2026-54321. Выпущено исправление для сервера.",
        ),
    ]
    plan = plan_for(articles)
    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "request_json",
        lambda self, payload: response_for(payload, plan, {"total_tokens": 77}),
    )
    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'ai.db'}")))
    response = api_ai(client, articles)
    assert response.status_code == 200
    data = response.json()
    assert data["events"][0]["source_ids"] == ["b"]
    assert data["editorial_plan"] == plan
    assert data["metrics"]["tokens_used"] == 231
    assert data["metrics"]["model_calls"] == 3
    assert all(c["passed"] for c in data["checks"])
    assert client.post("/api/v1/validate", json=data).json()["valid"]
    assert "test-key-never-export" not in response.text


@pytest.mark.parametrize("corruption", ["invented_quote", "unknown_id", "mixed_cve", "lost_source"])
def test_bad_ai_plan_falls_back_without_losing_news(tmp_path, monkeypatch, corruption):
    from app.main import create_app
    from app.providers.storage import Storage
    from fastapi.testclient import TestClient

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    articles = [
        article(),
        article(
            id="b",
            url="https://example.org/b",
            text="Поставщик подтвердил уязвимость CVE-2026-54321. Выпущено исправление для сервера.",
        ),
    ]
    plan = plan_for(articles)
    if corruption == "invented_quote":
        plan["groups"][0]["lead"]["fragment"] = "Хакеры похитили 999 миллионов паролей."
    elif corruption == "unknown_id":
        plan["groups"][0]["source_ids"] = ["invented"]
    elif corruption == "mixed_cve":
        plan["groups"][0]["source_ids"] = ["a", "b"]
        plan["groups"] = plan["groups"][:1]
    else:
        plan["groups"] = plan["groups"][:1]
    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "request_json",
        lambda self, payload: {"choices": [{"message": {"content": json.dumps(plan)}}]},
    )
    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'bad.db'}")))
    data = api_ai(client, articles).json()
    assert data["event_count"] == 2
    assert data["editorial_plan"] is None
    assert data["metrics"]["mode"] == "mock"
    assert data["metrics"]["model_calls"] == 2
    assert all(c["passed"] for c in data["checks"])


def test_ai_relevance_exclusion_has_audited_evidence(tmp_path, monkeypatch):
    from app.main import create_app
    from app.providers.storage import Storage
    from editorial_transport import response_for
    from fastapi.testclient import TestClient

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    articles = [article()]
    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "request_json",
        lambda self, payload: response_for(payload, plan_for(articles, relevant=False)),
    )
    client = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'irrelevant.db'}")))
    data = api_ai(client, articles).json()
    assert data["event_count"] == 0
    assert data["journal"][0]["status"] == "excluded_irrelevant"
    assert data["journal"][0]["exclusion_reason"].startswith("Оценка ИИ")
    assert all(c["passed"] for c in data["checks"])
