# Кибердайджест

Русский веб-сервис для подготовки проверяемого дайджеста по кибербезопасности: до пяти событий за последние 24 часа, письмо, пост и журнал обработки.

Cybersecurity news digest with source-grounded extraction, explainable ranking, audit exports and a keyless demo.

[Открыть сайт](https://cybersecurity-news-digest-clean.onrender.com) · [Проверить API](https://cybersecurity-news-digest-clean.onrender.com/health) · [OpenAPI](https://cybersecurity-news-digest-clean.onrender.com/api/docs)

Опубликован единый сервис Render Free. Интерфейс и API проверены 15 октября 2026; демонстрация работает без ключа. Подробные результаты: [отчёт проверок](docs/verification-report.md).

## Что делает приложение

Загрузите JSON/CSV, вставьте текст или выберите учебный набор. Укажите контрольное время в Europe/Moscow. Сервис исключает неподтверждённые даты, материалы вне периода, рекламу, нерелевантные и неполные записи; объединяет события и объясняет выбор. Результат содержит исходные ссылки, подтверждающие фрагменты, оговорки, противоречия и метрики.

Дайджест ограничен 4000 знаками, пост — 2000, без учёта URL. Предпросмотр письма не отправляет почту. Все демо-события синтетические; ссылки example.org иллюстрируют формат и не служат доказательствами реальных новостей.

## Интерфейс

Рабочая область со светлым фоном, тёмно-синей навигацией и бирюзовыми акцентами. Страницы: главная, создание, результат, журнал и документация. В результате восемь вкладок: дайджест, письмо, пост, источники, выбор, журнал, проверки и метрики. Адаптивная вёрстка и управление с клавиатуры.

## Архитектура и структура

```text
apps/web/       Next.js, React, TypeScript; статический экспорт
apps/api/app/   FastAPI, Pydantic; domain / services / providers / prompts
apps/api/tests/ Автоматические проверки правил и API
data/demo/      Синтетические наборы и пограничные сценарии
docs/           Архитектура, безопасность, оценка, публикация, демо
scripts/        Проверка набора, demo-run и экспорт
.github/        CI, шаблоны issues/PR и labels
Dockerfile      Единый контейнер: frontend + backend
render.yaml     Бесплатная публикация единого сервиса
```

UI → FastAPI → нормализация → даты → релевантность → grounded extraction → группировка → ранжирование → форматы → проверки → SQLAlchemy. SQLite используется локально; PostgreSQL подключается через DATABASE_URL. Отдельный OpenAI-compatible адаптер не меняет основные правила отбора.

## Быстрый запуск

На Windows можно запустить единое приложение одной командой из корня проекта:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -Rebuild
```

Откройте [Кибердайджест](http://127.0.0.1:8000). Для повторного запуска собранной версии уберите `-Rebuild`; остановка — Ctrl+C. Скрипт устанавливает отсутствующие зависимости и собирает интерфейс с API на том же адресе. Подготовка сдачи описана в [docs/submission-guide.md](docs/submission-guide.md), фактические проверки — в [docs/verification-report.md](docs/verification-report.md).

Требования: Python 3.12, Node.js 22, Corepack/pnpm. Команды выполняются из корня репозитория.

```sh
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r apps/api/requirements.txt
cp apps/api/.env.example apps/api/.env
python -m uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

Во втором терминале:

```sh
cd apps/web
corepack enable
corepack pnpm install --frozen-lockfile
# Windows: Copy-Item .env.example .env.local
cp .env.example .env.local
corepack pnpm dev
```

Откройте [frontend](http://localhost:3000), [health](http://localhost:8000/health), [OpenAPI](http://localhost:8000/api/docs). Копирование backend .env само по себе не меняет окружение: задайте переменные в shell перед запуском (PowerShell: `$env:LLM_API_KEY='ваш ключ'`; Linux/macOS: `export LLM_API_KEY='ваш ключ'`) либо используйте Docker Compose с корневым .env. Не сохраняйте команды с ключами в публичных файлах.

## Docker

```sh
docker compose up --build
```

Откройте [единый сервис](http://localhost:8000). Локальная база находится в Docker volume `digest-data`. Публичный бесплатный Render не обеспечивает постоянный локальный диск.

## Формат входа

```json
[
  {
    "id": "news-001",
    "title": "Заголовок публикации",
    "text": "Полный текст источника с достаточным контекстом.",
    "source": "Название источника",
    "source_type": "media",
    "url": "https://example.org/news-001",
    "published_at": "2026-10-14T10:30:00+03:00"
  }
]
```

CSV содержит те же колонки: id,title,text,source,source_type,url,published_at. Типы: media, author, vendor, regulator, official, unknown. Пропущенные значения остаются null; невозможность проверить требование приводит к исключению. Дата без часового пояса не считается подтверждённой. Указанная во входном файле дата является метаданными отправителя; сервис не утверждает, что независимо подтвердил её на сайте.

## API и демо

```sh
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/digest/demo -H 'Content-Type: application/json' -d '{}'
python scripts/run_demo.py --base-url http://localhost:8000
python scripts/validate_dataset.py data/demo/sample_news.json
```

Основной endpoint POST /api/v1/digest принимает articles, control_time с UTC-offset, timezone, event_limit 1..5 и use_ai. API также предоставляет получение сохранённых результатов, журнал, JSON/CSV export, validate, ingestion и безопасный preview RSS/HTML. Точный актуальный контракт находится в [OpenAPI](http://localhost:8000/api/docs).

Демо-контрольное время: **14 октября 2026, 18:00 MSK**. Демо и mock не требуют ключа. Чтобы использовать модель, задайте LLM_API_KEY, LLM_BASE_URL и LLM_MODEL на backend и включите «Использовать ИИ». При отсутствии конфигурации приложение явно объясняет использование локальной обработки. Версия промпта, модель, обращения и доступный расход токенов записываются в результат.

## Переменные окружения

| Переменная | Назначение |
| --- | --- |
| DATABASE_URL | SQLAlchemy URL базы; в контейнере по умолчанию SQLite в /app/runtime |
| STATIC_DIR | Каталог статического интерфейса; /app/static в едином контейнере |
| DEMO_DATA_DIR | Каталог учебных наборов; /app/data/demo в контейнере |
| CORS_ORIGINS | Разрешённые адреса отдельного frontend через запятую |
| NEXT_PUBLIC_API_URL | Публичный backend URL до сборки web; пустой для единого домена |
| LLM_API_KEY | Секрет модели, только backend; без него используется mock |
| LLM_BASE_URL, LLM_MODEL | Совместимый API и название модели |
| PORT | Порт сервера, передаваемый хостингом |

Фактический режим определяется наличием LLM_API_KEY, параметром use_ai и результатом обращения к модели. Переменная MODE сама по себе модель не подключает. Примеры безопасной конфигурации находятся в .env.example.

## Тестирование

```sh
python -m pytest apps/api/tests -q
python -m ruff check apps/api scripts
python -m ruff format --check apps/api scripts
python -m mypy apps/api/app
cd apps/web
corepack pnpm test
corepack pnpm typecheck
corepack pnpm lint
corepack pnpm format:check
corepack pnpm build
```

## Пример результата

Чтобы сохранить входы, ответы и статусы всех восьми обязательных проверок при работающем API:

```sh
python scripts/verify_submission.py
```

Результаты находятся в `artifacts/submission/`: полный JSON, CSV журнала, дайджест, пост и HTML письма по каждому сценарию. Общая сводка отмечает синтетические входы и отсутствие живого сетевого прогона модели.

Синтетическая публикация «Обнаружена критическая уязвимость DEMO-CVE-001» объединяется с перепечаткой. Результат показывает одну группу, оба source_ids и ссылки, пояснение оценки и предупреждение об учебных данных. Неподтверждённая утечка сохраняет оговорку. Материал с фразой «игнорируй предыдущие инструкции» не меняет настройки или адресатов.

## Публикация и ограничения

Развёрнут единый бесплатный Render-контейнер. Альтернативный вариант Vercel + Render и повторный деплой описаны в [docs/deployment.md](docs/deployment.md). Фактические результаты публикации, /health и демонстрационного прогона зафиксированы в [docs/verification-report.md](docs/verification-report.md).

Локальная обработка консервативна: она не заменяет журналистскую проверку, не гарантирует распознавание всех смысловых дублей и противоречий, не переводит произвольную статью с иностранного языка. Не вставляйте конфиденциальные материалы в публичный сервис. Результат — информационный дайджест, а не официальная рекомендация. Подробности: [security](docs/security.md), [architecture](docs/architecture.md), [prompt design](docs/prompt-design.md).

Лицензия MIT.

## Бесплатный хостинг

Сайт: https://cybersecurity-news-digest-clean.onrender.com. Единый Render Free сервис собран из корневого Dockerfile. Интерфейс и API работают на одном домене; ключ модели не нужен для демо.

Сервис предназначен для демонстрации и небольшой нагрузки. После простоя возможен медленный первый запрос. SQLite в бесплатном контейнере непостоянна: история может исчезнуть после перезапуска или нового деплоя. Для production нужны внешняя PostgreSQL, аутентификация, внешние ограничения запросов, мониторинг и резервное копирование. Лимиты тарифа могут меняться; актуальные условия опубликованы в [Render Free docs](https://render.com/docs/free).

Дополнительные браузерные проверки используют Playwright из установленного пакета либо из каталога, заданного BROWSER_RUNTIME_PATH; адрес приложения задаётся WEB_BASE_URL. Они требуют отдельно установленного браузера Chromium.

## Редакционный этап ИИ

Включённый ИИ получает допустимые материалы и дословные безопасные фрагменты. Структурированный план `editorial-v2` содержит оценку темы, группы, порядок и выбор ведущих предложений. Сервер запрещает неизвестные ID, изменение цитат и ссылок, разные CVE в одной группе, разделение известных повторов и исключение части известной группы. План и подтверждающие фрагменты сохраняются в результате. Текст остаётся экстрактивным: полноценный пересказ своими словами и автоматический перевод пока не реализованы.

Локальное ранжирование даёт последствиям больший вес, чем свежести и полноте метаданных. Отрицание эксплуатации не повышает срочность; клиентская база не считается масштабом пострадавших. Причины выбора сохранены в журнале, а основной выпуск содержит компактные ссылки с названием, датой и ID. Ошибки чтения источников сохраняются через необязательное поле `read_error`.
