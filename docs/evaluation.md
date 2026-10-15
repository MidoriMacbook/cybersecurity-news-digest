# Соответствие конкурсному ТЗ

Дата аудита: 15 октября 2026. Подтверждение относится к перечисленным синтетическим входам и регрессионным тестам, а не к универсальной достоверности новостей. Реальный ключ отсутствует по сообщению пользователя; фактический набор организаторов не найден среди предоставленных входов проекта.

| Требование | Проверка | Статус |
| --- | --- | --- |
| Русский язык | Русский UI, локальные шаблоны, русский rewrite prompt, test_old_event_new_update_and_foreign_text | Подтверждено для русского входа; автоматического перевода нет |
| Контрольное время | test_period_boundaries_and_naive_dates, frontend controlTime | Подтверждено |
| Europe/Moscow | test_period_boundaries_and_naive_dates, test_extreme_dates_are_validated | Подтверждено |
| Последние 24 часа | Точная граница начала/окончания в test_period_boundaries_and_naive_dates | Подтверждено |
| Исключение вне периода | outside_period и old_event_update | Подтверждено |
| Неизвестные даты | invalid_date, expanded JSON/CSV и test_period_boundaries_and_naive_dates | Подтверждено |
| Релевантность | no_relevant, test_missing_essentials_empty_and_injection, AI protocol fixtures | Подтверждено на проверенных примерах |
| Объединение сообщений | duplicate, test_duplicates_and_distinct_cves, test_ai_cannot_split_known_reprints | Подтверждено |
| Максимум пять событий | test_limits_and_grounding, demo-run | Подтверждено |
| Объяснение порядка | test_actual_operational_harm_ranks_above_patch_without_exploitation; поля selection_reason/ranking_factors и вкладка выбора | Подтверждено |
| Факты, даты, числа, ссылки | test_fabricated_metadata_caveats_and_period_rejected, test_unverified_copy_rolls_back_entire_result | Подтверждено механически на проверенных примерах |
| Системы и организации | test_unaffected_system_is_not_promoted_to_affected, test_researcher_is_not_promoted_to_victim, test_unconfirmed_victim_is_not_recorded_as_affected | Подтверждено консервативно; неизвестные роли пусты |
| Последствия | test_nonnumeric_consequence_preserved_in_post, test_truthful_but_incomplete_rewrite_cannot_erase_consequences | Подтверждено |
| Оговорки | test_late_uncertainty_preserved_and_headline_neutral, test_negation_cannot_be_removed_even_if_verifier_would_approve | Подтверждено |
| Противоречия | conflict, test_conflicting_counts_and_preliminary_preserved | Подтверждено |
| Первичный источник | demo vulnerability: приоритет вендора, primary_source_id; вкладка выбора | Частично: эвристический основной источник по заявленному типу/качеству, а не независимая проверка первичного происхождения |
| Дайджест до 4000 без URL | digest_length, test_limits_and_grounding | Подтверждено; длинный fixture 3640 |
| Пост до 2000 без URL | post_length, test_limits_and_grounding | Подтверждено; длинный fixture 1923 |
| Предпросмотр письма | test_demo_export_idempotency_and_validation и iframe браузера | Подтверждено |
| Согласованность письма/поста | validate_result, test_unverified_copy_rolls_back_entire_result, сохранение evidence в обоих форматах | Подтверждено; смысловая полнота вероятностного пересказа ограничена |
| Журнал | test_unavailable_source_survives_into_exported_journal; source_index/raw/normalized/evidence | Подтверждено |
| JSON/CSV экспорт | test_demo_export_idempotency_and_validation, публичные endpoints | Подтверждено в предыдущей опубликованной версии; повторная проверка новой версии фиксируется в verification-report.md |
| Ошибки | model_error, invalid_model, unavailable, oversized и test_storage_error_returns_safe_retryable_response | Подтверждено; модельные ошибки имитированы |
| Prompt injection | injection и test_exact_requested_injection_is_data_in_mock_and_ai | Mock и имитированный AI подтверждены; реальный AI не проверен |
| Воспроизводимость | test_demo_export_idempotency_and_validation, test_cache_namespace_tracks_key_presence_model_endpoint_and_engine | Подтверждено |
| Версия модели | test_successful_paraphrase_has_actual_model_and_unknown_usage | Подтверждено имитацией; реальный провайдер не проверен |
| Версия промпта | Тот же тест, mode mock=pipeline-v1, ai=editorial-v3 | Подтверждено |
| Время запуска | test_missing_key_has_explicit_telemetry_and_original_record; started_at/completed_at | Подтверждено |
| Число обращений | test_every_failed_attempt_counted_without_key_or_exception_leak, test_usage_includes_invalid_successful_response_before_retry | Подтверждено имитацией |
| Расход токенов | test_malformed_usage_never_creates_fabricated_token_count, test_usage_includes_invalid_successful_response_before_retry | Нулевые/неизвестные значения различены; реальный usage не измерен |

## Обязательные артефакты

`python scripts/validate_contest.py` создаёт artifacts/validation/summary.json и отдельные папки для 18 сценариев. Каждая содержит input.json, response.json, result.json, verdict.json с expected/actual/passed, временем и версиями. Дополнительно проверяются расширенные JSON и CSV: UTF-8, пустые поля, неизвестные колонки, повторяющиеся ID, длинный текст, HTML, переносы, даты с timezone и без.

`python scripts/validate_contest.py --base-url https://cybersecurity-news-digest-clean.onrender.com --output artifacts/validation-public` повторяет публичные сценарии. Ошибка и невалидный ответ модели по-прежнему проверяются в локальном приложении с подменённым транспортом; target и simulation указаны в verdict. Их нельзя представлять как реальные сбои внешнего API.

## Частично подтверждено и не проверено

Реальное качество релевантности/группировки/пересказа, совместимость конкретного провайдера, реальный usage и prompt injection с ним не проверены без ключа. AI выбирает подтверждающие фрагменты; структурные факты и ограничения остаются серверными. Новые синонимы могут вызвать fallback. Фактический набор организаторов и внешний PostgreSQL не проверены. Полный WCAG-аудит и production-нагрузка не проводились.

Результаты команд, Docker и публичного браузера — verification-report.md. До успешного реального AI-прогона нельзя утверждать полную конкурсную готовность.
