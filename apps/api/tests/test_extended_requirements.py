from app.schemas.models import DigestRequest
from app.services.pipeline import process
from test_pipeline import CONTROL, article


def test_shorter_post_with_consequences_and_same_sources():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="Организация подтвердила уязвимость CVE-2026-12345 в сервере. Работа сервера временно приостановлена. Выпущено исправление для сервера."
                )
            ],
        )
    )
    assert result.post_text != result.digest_text
    assert len(result.post_text) < len(result.digest_text)
    assert "приостановлена" in result.events[0].consequences
    assert "сервере" in result.events[0].affected_systems
    assert "https://example.org/a" in result.post_text


def test_long_background_does_not_exclude_article():
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    text="Подтверждена уязвимость CVE-2026-12345 в сервере. "
                    + "Длинная справка " * 200
                    + ". Выпущено исправление."
                )
            ],
        )
    )
    assert result.event_count == 1


def test_invalid_date_distinguished():
    result = process(
        DigestRequest(control_time=CONTROL, articles=[article(published_at="yesterday")])
    )
    assert result.journal[0].status == "invalid_date"


def test_contextual_relevance_and_changed_headline_reprint():
    for keyword in ["SOC", "SIEM", "EDR", "DLP", "AppSec", "MFA", "Zero Trust", "AI security"]:
        result = process(
            DigestRequest(
                control_time=CONTROL,
                articles=[
                    article(
                        title=keyword,
                        text=f"Организация внедрила {keyword}. Опубликовано описание новых возможностей системы и результатов проверки.",
                    )
                ],
            )
        )
        assert result.event_count == 1, keyword
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(
                    title="Выдан сертификат",
                    text="Выдан сертификат организации. Министерство сообщило о работе базы данных и учётной записи пользователя.",
                )
            ],
        )
    )
    assert result.event_count == 0
    text = "Организация сообщила о фишинговой кампании. Поддельные страницы собирали пароли сотрудников."
    result = process(
        DigestRequest(
            control_time=CONTROL,
            articles=[
                article(title="Атака", text=text),
                article(id="b", title="Кампания против сотрудников", text=text),
            ],
        )
    )
    assert result.event_count == 1
    assert len(result.events[0].source_ids) == 2


def test_physical_leaks_security_and_fake_demo_domain_excluded():
    for text in [
        "Произошла утечка газа в жилом доме. Аварийные службы эвакуировали жильцов и устраняют повреждение трубы.",
        "Security guards reported a breach of the physical perimeter. A broken fence was repaired near the building.",
    ]:
        result = process(DigestRequest(control_time=CONTROL, articles=[article(text=text)]))
        assert result.event_count == 0
    result = process(
        DigestRequest(
            control_time=CONTROL, articles=[article(url="https://example.org.evil.com/a")]
        )
    )
    assert not any("Синтетическая" in warning for warning in result.warnings)
