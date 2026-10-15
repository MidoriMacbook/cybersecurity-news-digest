# Локальный запуск и повторная публикация

Версия выполнения после исправлений — 1.6.1. Публикуйте тот же SHA, который прошёл CI; отдельно проверьте Live и `application_version` в `/health`. Ключ Groq уже настроен только в Environment существующего сервиса; повторное добавление не требуется. [Отчёт исправлений](bugfix-report.md).

## Опубликованный сервис

- Репозиторий: https://github.com/MidoriMacbook/cybersecurity-news-digest, ветка main.
- Сайт и backend: https://cybersecurity-news-digest-clean.onrender.com.
- Health: https://cybersecurity-news-digest-clean.onrender.com/health.
- Панель сервиса: https://dashboard.render.com/web/srv-db84l1uq1p3s739iek20.
- Тариф Free, Frankfurt, Dockerfile ./Dockerfile, context .; постоянный диск и платная база не подключены.

Для версии 1.6 подтверждены Docker build/run в CI и Render, /health, demo-run, экспорт и публичный адаптивный интерфейс; результаты — в verification-report.md. При создании сервиса включён autoDeploy, но получение webhook от нового публичного репозитория не подтверждено: исправленная версия опубликована ручным деплоем. До проверки интеграции GitHub используйте Manual Deploy → Deploy latest commit в панели сервиса. Файл render.yaml содержит рекомендуемый healthCheckPath /health; HTTP-проверка этого адреса выполнена отдельно.

## Вариант A: Vercel + Render

1. Используйте репозиторий cybersecurity-news-digest-clean с проверенным кодом без .env и локальных данных.
2. Создайте Render Web Service из GitHub, plan Free, Dockerfile `apps/api/Dockerfile`, context корень репозитория, health check `/health`.
3. Задайте MODE=mock и DATABASE_URL; для демонстрации допустим SQLite с учётом непостоянного диска. Для постоянной истории используйте внешнюю PostgreSQL.
4. Создайте Vercel-проект из того же репозитория, root directory `apps/web`, framework Next.js. Команда установки `corepack pnpm install --frozen-lockfile`, build `corepack pnpm build`, output `out`.
5. Задайте NEXT_PUBLIC_API_URL равным HTTPS URL backend. Не задавайте API-ключ модели на frontend.
6. На backend задайте CORS_ORIGINS точно равным домену frontend, без wildcard, и перезапустите.
7. Проверьте `/health`, откройте web, загрузите демо и создайте дайджест; проверьте вкладки и JSON/CSV export.

## Вариант B: единый Render Free

Корневой Dockerfile собирает статический Next.js frontend и помещает его в FastAPI-контейнер. STATIC_DIR=/app/static, NEXT_PUBLIC_API_URL пустой: API вызывается на том же origin. Один сервис снижает число cold starts и упрощает CORS.

В Render создайте Blueprint из `render.yaml` либо Web Service runtime Docker, Dockerfile `./Dockerfile`, context `.`, region Frankfurt, plan Free, health `/health`. Запускайте только проверенный commit. Имя может быть занято; используйте свободное имя и обновите CORS_ORIGINS до фактически выданного URL.

## Повторный деплой

Измените код → запустите тесты/lint/typecheck/build → commit → push main → дождитесь Tests/Lint/Deploy в GitHub Actions → откройте панель Render и выберите Manual Deploy → Deploy latest commit. Дождитесь Live, проверьте /health и создайте новый демо-выпуск. Историю SQLite заранее экспортируйте: новый контейнер может её потерять.

Blueprint описывает checksPass; GitHub workflow Deploy запускается после успешного Tests. При настройке RENDER_DEPLOY_HOOK сохраните его в GitHub Actions Secrets. Без секрета workflow только проверяет сборку; зелёный workflow сам по себе не означает публикацию. Автоматический запуск после push нужно отдельно подтвердить по commit SHA в Render.

Для обновления локальной копии выполните git pull --ff-only из каталога проекта. Проверяйте git status до обновления и сохраняйте собственные изменения отдельным коммитом. Автор и коммиттер новых изменений — MidoriMacbook; email задаётся только в локальной конфигурации Git и не приводится в публичной документации.

Для новой среды поменяйте NEXT_PUBLIC_API_URL до frontend build. Переменная в статическом bundle не изменяется после сборки. Проверьте фактически выданные URL, а не ожидаемый шаблон домена.

## Ключ и база

Текущее подключение: Groq, `LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=openai/gpt-oss-20b`. Секрет задан только в окружении backend; его значение не публикуется. Подтверждён один реальный AI-выпуск и безопасные fallback-прогоны, [результаты](live-ai-report.md). Наличие конфигурации в `/health` по-прежнему не подтверждает успех любого следующего запроса.

Изменение LLM_API_KEY, LLM_BASE_URL и LLM_MODEL выполняется только на backend. Проверьте model_name/mode/attempts в новом результате. Для PostgreSQL используйте SQLAlchemy URL и подходящий psycopg driver; не коммитьте connection string. Миграцию уже существующей истории из SQLite в PostgreSQL выполняйте отдельно с резервной копией.

### Подключение модели после получения ключа

Эти шаги подходят для подключения или замены ключа без изменения frontend-кода. Демо продолжает работать без обращения к модели.

1. Откройте Render → существующий backend-сервис → Environment.
2. Добавьте `LLM_API_KEY` с ключом поставщика. Не отправляйте ключ в чат и не помещайте его в Git, скриншоты или результаты.
3. Задайте `LLM_BASE_URL` — HTTPS базовый URL совместимого API, обычно с `/v1`, без `/chat/completions` в конце. URL должен принадлежать выбранному доверенному поставщику.
4. Задайте `LLM_MODEL` — точное имя доступной модели. Адаптер требует `/chat/completions`, structured output `json_schema` со strict-схемой и `max_completion_tokens`. Совместимость конкретного поставщика ещё не доказана.
5. Сохраните переменные и перезапустите сервис. Не добавляйте ключ в `NEXT_PUBLIC_*`: они попадают в публичную статическую сборку.
6. На странице создания включите «Использовать ИИ».
7. Проверьте `/health`: `llm_configured=true` означает наличие конфигурации, а не успешную авторизацию или генерацию. Зелёный health не заменяет следующий шаг.
8. Создайте **новый** выпуск из учебного набора. Прежний сохранённый выпуск не подтверждает новый вызов.
9. Проверьте `mode`, `model_name`, `model_version`, `prompt_version`, `llm_attempts`, `token_usage`, `started_at`, `completed_at`. Успешный принятый пересказ имеет `mode=ai`; `fallback` означает локальный выпуск после ошибки/отклонения ответа, `mock` — обработку без модели. Неизвестный usage остаётся `null`. Сравните факты, оговорки, письмо и пост с источниками; проверьте prompt injection. Только после этого зафиксируйте результат реального прогона.
10. После использования удалите или замените ключ в Render и при необходимости отзовите его у поставщика. Сохраните с перезапуском; при удалённом ключе новые выпуски используют mock. Если ключ был раскрыт, отзовите его сразу.

При неверном ключе, сетевой ошибке, ошибке сервера модели, невалидном JSON или timeout адаптер ограничивает повторы и возвращает безопасный fallback с фактическим числом обращений. Проверки этих ошибок локально имитируют HTTP-транспорт и не доказывают работу внешнего API.

## Ограничения бесплатного хостинга

Render Free останавливает web-сервис после периода бездействия, поэтому первый запрос может быть медленным. Локальная файловая система непостоянна: при перезапуске или новом деплое история SQLite может исчезнуть. Бесплатный тариф и квоты могут изменяться. Проверяйте [Render Free docs](https://render.com/docs/free) и [persistent disks](https://render.com/docs/disks). Не рассчитывайте на фоновые cron или память процесса как на долговременное хранилище.

## Production

Используйте платный always-on instance, постоянную PostgreSQL, аутентификацию и права на результат, job queue, внешние rate limits, резервные копии, retention, мониторинг ошибок, проверенные источники и оценку качества на размеченном корпусе. Наличие AI-ключа само по себе не повышает достоверность.

## GitHub

Рекомендуется защитить main: PR review, обязательные Tests/Lint, запрет force push/deletion. Labels описаны в `.github/labels.json`: bug, feature, documentation, security. Установка этих рекомендаций зависит от прав владельца и доступных функций GitHub; файл рекомендаций не означает применённую защиту.
