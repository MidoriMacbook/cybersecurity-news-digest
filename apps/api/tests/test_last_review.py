import pytest
from app.main import create_app
from app.providers.llm import OpenAICompatibleProvider, apply_ai_verification
from app.providers.storage import Storage
from app.schemas.models import DigestRequest
from app.services.ingestion import export_csv, parse_articles
from app.services.pipeline import process
from fastapi.testclient import TestClient
from test_pipeline import CONTROL, article


def test_csv_keeps_false_and_zero_and_text_keeps_spaces():
    csv = export_csv([{"relevance": False, "fact_check": False, "count": 0, "missing": None}])
    assert "False,False,0," in csv
    assert parse_articles("text", "  Текст публикации  \n")[0].text == "  Текст публикации  \n"


def test_extreme_dates_are_validated(tmp_path):
    api = TestClient(create_app(Storage(f"sqlite:///{tmp_path / 'date.db'}")))
    for date in ["0001-01-01T00:00:00+03:00", "9999-12-31T23:00:00-12:00"]:
        assert (
            api.post("/api/v1/digest", json={"control_time": date, "articles": []}).status_code
            == 422
        )
    result = process(
        DigestRequest(
            control_time=CONTROL, articles=[article(published_at="9999-12-31T23:00:00-12:00")]
        )
    )
    assert result.journal[0].status == "invalid_date"


def test_old_event_new_update_and_foreign_text():
    old = "Атака произошла 2026-10-01. Организация подтвердила утечку данных своих клиентов."
    result = process(DigestRequest(control_time=CONTROL, articles=[article(text=old)]))
    assert result.event_count == 0
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[article(text=old + " Выпущено исправление для сервера.")],
        )
    )
    assert result.event_count == 1
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="A data breach affected company customers. An investigation of the cybersecurity incident is underway."
                )
            ],
        )
    )
    assert result.event_count == 0


def test_long_sentence_keeps_caveat():
    text = (
        "По неподтвержденным данным "
        + "из закрытых сетевых обсуждений " * 30
        + ": утечка данных затронула 100 клиентов."
    )
    result = process(
        DigestRequest(
            control_time=CONTROL, articles=[article(title="Утечка данных компании", text=text)]
        )
    )
    assert result.event_count == 1
    assert result.events[0].is_preliminary
    assert "неподтвержденным" in result.post_text


def test_generic_same_fact_disagreeing_quantity_is_one_conflicting_event():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    title="Утечка",
                    text="Утечка данных затронула 100 серверов. Проверка информационной безопасности продолжается.",
                ),
                article(
                    id="b",
                    title="Утечка",
                    text="Утечка данных затронула 200 серверов. Проверка информационной безопасности продолжается.",
                ),
            ],
        )
    )
    assert result.event_count == 1 and result.events[0].conflicts


def test_single_source_distinct_counts_and_invalid_event_date():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="Кибератака затронула 100 серверов банка Альфа и 200 серверов банка Бета. Компания завершила анализ инцидента."
                )
            ],
        )
    )
    assert not result.events[0].conflicts
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="Кибератака затронула серверы 2026-99-99. Организация проводит проверку информационной безопасности."
                )
            ],
        )
    )
    assert result.events[0].event_date is None


def test_headline_cannot_invent_facts():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    title="Хакеры украли миллион паролей",
                    text="Организация обнаружила уязвимость в шлюзе. Утечек данных не зафиксировано; шлюз обновлён.",
                )
            ],
        )
    )
    assert "миллион" not in result.digest_text
    assert result.events[0].title == "Организация обнаружила уязвимость в шлюзе."


@pytest.mark.parametrize("envelope", [[], {"usage": [], "choices": []}])
def test_malformed_llm_envelope_falls_back(monkeypatch, envelope):
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setattr(OpenAICompatibleProvider, "request_json", lambda self, payload: envelope)
    result = apply_ai_verification(
        process(DigestRequest(control_time=CONTROL, articles=[article()]))
    )
    assert result.metrics.model_calls == 2 and result.metrics.mode == "mock"
