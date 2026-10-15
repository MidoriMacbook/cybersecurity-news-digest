# Локальный запуск и повторная публикация

## Вариант A: Vercel + Render

1. Создайте public GitHub-репозиторий cybersecurity-news-digest и загрузите проверенный код без .env и локальных данных.
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

Измените код → запустите тесты/lint/typecheck/build → commit → push main. Blueprint использует checksPass; GitHub workflow Deploy запускается после успешного Tests. При настройке RENDER_DEPLOY_HOOK сохраните его в GitHub Actions Secrets. Без секрета workflow только проверяет сборку; это не означает публикацию.

Для новой среды поменяйте NEXT_PUBLIC_API_URL до frontend build. Переменная в статическом bundle не изменяется после сборки. Проверьте фактически выданные URL, а не ожидаемый шаблон домена.

## Ключ и база

Изменение LLM_API_KEY, LLM_BASE_URL и LLM_MODEL выполняется только на backend. Проверьте model_name/mode/attempts в новом результате. Для PostgreSQL используйте SQLAlchemy URL и подходящий psycopg driver; не коммитьте connection string. Миграцию уже существующей истории из SQLite в PostgreSQL выполняйте отдельно с резервной копией.

## Ограничения бесплатного хостинга

Render Free останавливает web-сервис после периода бездействия, поэтому первый запрос может быть медленным. Локальная файловая система непостоянна: при перезапуске или новом деплое история SQLite может исчезнуть. Бесплатный тариф и квоты могут изменяться. Проверяйте [Render Free docs](https://render.com/docs/free) и [persistent disks](https://render.com/docs/disks). Не рассчитывайте на фоновые cron или память процесса как на долговременное хранилище.

## Production

Используйте платный always-on instance, постоянную PostgreSQL, аутентификацию и права на результат, job queue, внешние rate limits, резервные копии, retention, мониторинг ошибок, проверенные источники и оценку качества на размеченном корпусе. Наличие AI-ключа само по себе не повышает достоверность.

## GitHub

Рекомендуется защитить main: PR review, обязательные Tests/Lint, запрет force push/deletion. Labels описаны в `.github/labels.json`: bug, feature, documentation, security. Установка этих рекомендаций зависит от прав владельца и доступных функций GitHub; файл рекомендаций не означает применённую защиту.
