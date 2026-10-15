from app.schemas.models import DigestRequest
from app.services.pipeline import process
from test_pipeline import CONTROL, article


def test_unaffected_system_is_not_promoted_to_affected():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="Обнаружена уязвимость в Linux. Windows не затронута; опубликованы результаты проверки безопасности систем."
                )
            ],
        )
    )
    assert "Windows" not in result.events[0].affected_systems


def test_researcher_is_not_promoted_to_victim():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="Компания «Исследователь» обнаружила уязвимость в Linux. Банк «Жертва» сообщил о компрометации серверов."
                )
            ],
        )
    )
    assert "Исследователь" not in result.events[0].affected_entities


def test_support_expiration_is_not_event_date():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="Обнаружена уязвимость в Linux. Поддержка продукта действует до 2027-12-31; опубликовано исправление."
                )
            ],
        )
    )
    assert result.events[0].event_date is None
