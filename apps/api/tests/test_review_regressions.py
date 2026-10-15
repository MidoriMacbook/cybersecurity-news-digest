from app.schemas.models import DigestRequest
from app.services.pipeline import process
from test_pipeline import CONTROL, article


def test_late_uncertainty_preserved_and_headline_neutral():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    title="Подтверждена утечка данных",
                    text="Сотрудник заявил об утечке данных компании. Начато расследование инцидента. Эксперты изучают систему. Это лишь слух, достоверность сообщения ещё не установлена.",
                )
            ],
        )
    )
    event = result.events[0]
    assert event.is_preliminary
    assert "Подтверждена" not in event.title
    assert "лишь слух" in result.digest_text and "лишь слух" in result.post_text


def test_same_title_distinct_named_banks_not_grouped():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    title="Сообщение об утечке",
                    text="Банк Альфа сообщил об утечке данных своих клиентов. Выполняется проверка систем информационной безопасности.",
                ),
                article(
                    id="b",
                    title="Сообщение об утечке",
                    text="Банк Бета сообщил об утечке данных своих клиентов. Выполняется проверка систем информационной безопасности.",
                ),
            ],
        )
    )
    assert result.event_count == 2
    assert "Альфа" in result.post_text and "Бета" in result.post_text


def test_agreeing_metric_and_extra_background_number_not_conflicting():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    title="Сообщение об утечке",
                    text="Утечка затронула 100 серверов. Проверка информационной безопасности завершена.",
                ),
                article(
                    id="b",
                    title="Сообщение об утечке",
                    text="Утечка затронула 100 серверов. Компания обслуживает 200 клиентов по действующим договорам.",
                ),
            ],
        )
    )
    assert result.event_count == 1
    assert not result.events[0].conflicts


def test_nonnumeric_consequence_preserved_in_post():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="Организация подтвердила уязвимость в сервере. Работа сервера временно приостановлена. Выпущено исправление для сервера."
                )
            ],
        )
    )
    assert "приостановлена" in result.post_text


def test_boilerplate_intro_does_not_override_different_entities():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    title="Сообщение об утечке",
                    text="Обнаружена кибератака. Банк Альфа сообщил об утечке данных своих клиентов и начал расследование.",
                ),
                article(
                    id="b",
                    title="Сообщение об утечке",
                    text="Обнаружена кибератака. Банк Бета сообщил об утечке данных своих клиентов и начал расследование.",
                ),
            ],
        )
    )
    assert result.event_count == 2
    assert "Альфа" in result.post_text and "Бета" in result.post_text
