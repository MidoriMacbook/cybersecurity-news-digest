import asyncio
import json
import os
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import MAX_REQUEST_BYTES
from app.providers.editorial import apply_ai_editorial
from app.providers.sources import preview
from app.providers.storage import IdempotencyConflict, Storage
from app.schemas.models import DemoRequest, DigestRequest, ParseRequest, PreviewRequest, Result
from app.services.ingestion import export_csv, parse_articles
from app.services.pipeline import process, validate_result

DEMO_DATA_DIR = Path(
    os.getenv("DEMO_DATA_DIR") or str(Path(__file__).resolve().parents[3] / "data/demo")
)
UPLOAD_DEADLINE_SECONDS = 10.0


def demo_data() -> dict[str, object]:
    return {
        "articles": json.loads((DEMO_DATA_DIR / "sample_news.json").read_text(encoding="utf-8")),
        "control_time": "2026-10-14T18:00:00+03:00",
    }


def create_app(storage: Storage | None = None) -> FastAPI:
    app = FastAPI(
        title="Кибердайджест API", version="1.0.0", docs_url="/api/docs", redoc_url="/api/redoc"
    )
    store = storage or Storage(
        os.getenv("DATABASE_URL", "sqlite:///./digest.db")
        .replace("postgres://", "postgresql+psycopg://", 1)
        .replace("postgresql://", "postgresql+psycopg://", 1)
    )
    origins = [
        value.strip()
        for value in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(
            ","
        )
        if value.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )
    rates: OrderedDict[str, deque[float]] = OrderedDict()
    rate_lock = threading.Lock()
    processing = threading.BoundedSemaphore(4)

    @app.middleware("http")
    async def limits(request: Request, call_next):
        if request.method == "POST":
            host = request.client.host if request.client else "unknown"
            now = time.monotonic()
            with rate_lock:
                bucket = rates.setdefault(host, deque())
                while bucket and now - bucket[0] > 60:
                    bucket.popleft()
                if len(bucket) >= 30:
                    return JSONResponse({"detail": "Лимит 30 запросов в минуту"}, status_code=429)
                bucket.append(now)
                rates.move_to_end(host)
                while len(rates) > 1000:
                    rates.popitem(last=False)
            try:
                if int(request.headers.get("content-length", "0")) > MAX_REQUEST_BYTES:
                    return JSONResponse(
                        {"detail": "Максимальный размер запроса — 2 МБ"}, status_code=413
                    )
            except ValueError:
                return JSONResponse({"detail": "Некорректный Content-Length"}, status_code=400)
            body = bytearray()
            try:
                async with asyncio.timeout(UPLOAD_DEADLINE_SECONDS):
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body) > MAX_REQUEST_BYTES:
                            return JSONResponse(
                                {"detail": "Максимальный размер запроса — 2 МБ"}, status_code=413
                            )
            except TimeoutError:
                return JSONResponse(
                    {"detail": "Превышен лимит 10 секунд на загрузку"}, status_code=408
                )
            request._body = bytes(body)
        return await call_next(request)

    @app.exception_handler(ValidationError)
    async def model_errors(request: Request, exc: ValidationError):
        return JSONResponse({"detail": "Некорректная структура данных"}, status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def storage_errors(request: Request, exc: SQLAlchemyError):
        return JSONResponse(
            {"detail": "Хранилище временно недоступно. Повторите запрос позже."}, status_code=503
        )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "mode": "api" if os.getenv("LLM_API_KEY") else "mock",
            "model_name": os.getenv("LLM_MODEL", "extractive-local"),
            "prompt_version": "pipeline-v1",
        }

    @app.get("/api/v1/demo")
    def demo(scenario: str | None = None):
        if scenario is None:
            return demo_data()
        scenarios = {
            "sample_news": "Общий набор обязательных проверок",
            "duplicate_event": "Повтор одного события",
            "no_relevant_news": "Нет подходящих новостей",
            "incomplete_article": "Недостаточно текста",
            "conflicting_sources": "Противоречия источников",
            "unavailable_sources": "Недоступный источник",
            "prompt_injection": "Посторонняя инструкция в новости",
        }
        if scenario not in scenarios:
            raise HTTPException(422, "Неизвестный демонстрационный сценарий")
        data = demo_data()
        articles = json.loads((DEMO_DATA_DIR / (scenario + ".json")).read_text(encoding="utf-8"))
        if scenario == "unavailable_sources":
            demo_articles = data["articles"]
            assert isinstance(demo_articles, list)
            articles = [
                {
                    "id": "unavailable-demo",
                    "title": "Источник недоступен",
                    "text": None,
                    "source": "Учебный источник",
                    "url": articles[0]["url"],
                    "published_at": data["control_time"],
                    "source_type": "unknown",
                    "read_error": "Учебный сценарий: источник недоступен; остальные материалы обработаны.",
                }
            ] + [demo_articles[0]]
        return {
            **data,
            "articles": articles,
            "scenario": scenario,
            "description": scenarios[scenario],
        }

    def generate(payload: DigestRequest, key: str | None = None) -> Result:
        if key and len(key) > 128:
            raise HTTPException(422, "Idempotency-Key: максимум 128 символов")
        try:
            existing = store.find(payload, key)
            if existing:
                return store.save(payload, existing, key)
            if not processing.acquire(blocking=False):
                raise HTTPException(429, "Сервис обрабатывает максимум 4 запуска одновременно")
            try:
                started = time.monotonic()
                result = process(payload)
                if payload.use_ai:
                    result = apply_ai_editorial(payload, result)
                result.metrics.duration_ms = int((time.monotonic() - started) * 1000)
                return store.save(payload, result, key)
            finally:
                processing.release()
        except IdempotencyConflict as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/api/v1/digest", response_model=Result)
    def digest(payload: DigestRequest, idempotency_key: str | None = Header(default=None)):
        return generate(payload, idempotency_key)

    @app.post("/api/v1/digest/demo", response_model=Result)
    def digest_demo(payload: DemoRequest | None = None):
        data = demo_data()
        if payload and payload.control_time:
            data["control_time"] = payload.control_time
        return generate(DigestRequest.model_validate(data))

    def load(ident: str) -> Result:
        result = store.get(ident)
        if not result:
            raise HTTPException(404, "Дайджест не найден")
        return result

    @app.get("/api/v1/digest/{digest_id}", response_model=Result)
    def saved(digest_id: str):
        return load(digest_id)

    @app.get("/api/v1/digest/{digest_id}/journal")
    def journal(
        digest_id: str,
        status: str | None = None,
        exclusion_reason: str | None = None,
        event_id: str | None = None,
        source_type: str | None = None,
        has_error: bool | None = None,
        published_at: str | None = None,
    ):
        return [
            j
            for j in load(digest_id).journal
            if (status is None or j.status == status)
            and (exclusion_reason is None or exclusion_reason in (j.exclusion_reason or ""))
            and (event_id is None or j.event_id == event_id)
            and (source_type is None or j.source_type == source_type)
            and (has_error is None or bool(j.errors) == has_error)
            and (published_at is None or (j.published_at or "").startswith(published_at))
        ]

    @app.get("/api/v1/digest/{digest_id}/export/json")
    def json_export(digest_id: str):
        return Response(
            load(digest_id).model_dump_json(indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="digest.json"'},
        )

    @app.get("/api/v1/digest/{digest_id}/export/csv")
    def csv_export(digest_id: str):
        return Response(
            "\ufeff" + export_csv([j.model_dump() for j in load(digest_id).journal]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="journal.csv"'},
        )

    @app.post("/api/v1/validate")
    def validate(payload: Result):
        checks = validate_result(payload)
        return {"valid": all(check.passed for check in checks), "checks": checks}

    @app.post("/api/v1/parse")
    def parse(payload: ParseRequest):
        try:
            articles = parse_articles(payload.format, payload.content)
        except (ValueError, TypeError):
            raise HTTPException(
                422, "Не удалось разобрать данные; проверьте JSON/CSV и поля материалов"
            ) from None
        return {
            "articles": articles,
            "warnings": [
                "Отсутствующие метаданные сохраняются как null; неизвестные даты будут исключены."
            ],
        }

    @app.post("/api/v1/sources/preview")
    async def source_preview(payload: PreviewRequest):
        try:
            return await asyncio.wait_for(asyncio.to_thread(preview, payload.urls), timeout=45)
        except TimeoutError:
            raise HTTPException(504, "Источники превысили общий лимит 45 секунд") from None

    static_dir = os.getenv("STATIC_DIR")
    if static_dir and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    return app


app = create_app()
