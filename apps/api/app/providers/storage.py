import hashlib
import json
import os
import threading
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Column, MetaData, String, Table, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from app.config import ENGINE_VERSION, execution_fingerprint
from app.schemas.models import DigestRequest, Result
from app.services.pipeline import normalize


class IdempotencyConflict(ValueError):
    pass


class Storage:
    def __init__(self, url: str):
        self.engine = create_engine(
            url,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
            pool_pre_ping=True,
            poolclass=StaticPool if url in {"sqlite://", "sqlite:///:memory:"} else None,
        )
        metadata = MetaData()
        self.runs = Table(
            "digest_runs",
            metadata,
            Column("id", String(64), primary_key=True),
            Column("request_hash", String(64), nullable=False),
            Column("raw", JSON, nullable=False),
            Column("normalized", JSON, nullable=False),
            Column("result", JSON, nullable=False),
            Column("journal", JSON, nullable=False),
        )
        self.keys = Table(
            "idempotency_keys",
            metadata,
            Column("key_hash", String(64), primary_key=True),
            Column("request_hash", String(64), nullable=False),
            Column("digest_id", String(64), nullable=False),
        )
        self.execution_status = Table(
            "ai_execution_status",
            metadata,
            Column("slot", String(32), primary_key=True),
            Column("configuration", String(64), nullable=False),
            Column("details", JSON, nullable=False),
        )
        metadata.create_all(self.engine)
        self.lock = threading.Lock()

    @staticmethod
    def request_hash(request: DigestRequest) -> str:
        return execution_fingerprint(request)

    def find(self, request: DigestRequest, key: str | None) -> Result | None:
        request_hash = self.request_hash(request)
        with self.engine.connect() as connection:
            if key:
                record = (
                    connection.execute(
                        select(self.keys).where(
                            self.keys.c.key_hash == hashlib.sha256(key.encode()).hexdigest()
                        )
                    )
                    .mappings()
                    .first()
                )
                if record:
                    if record["request_hash"] != request_hash:
                        raise IdempotencyConflict(
                            "Ключ повторного запроса уже связан с другими входными данными"
                        )
                    return self.get(record["digest_id"])
            run_records = connection.execute(
                select(self.runs.c.result).where(self.runs.c.request_hash == request_hash)
            )
            for run_record in run_records:
                result = Result.model_validate(run_record[0])
                # Explicit idempotency keys above replay their exact outcome. A new
                # request may retry a transient failure instead of caching it forever.
                if request.use_ai and result.mode == "fallback":
                    continue
                return result
            return None

    def save(self, request: DigestRequest, result: Result, key: str | None) -> Result:
        request_hash = self.request_hash(request)
        with self.lock:
            if key:
                with self.engine.connect() as connection:
                    bound = (
                        connection.execute(
                            select(self.keys).where(
                                self.keys.c.key_hash == hashlib.sha256(key.encode()).hexdigest()
                            )
                        )
                        .mappings()
                        .first()
                    )
                if bound:
                    if bound["request_hash"] != request_hash:
                        raise IdempotencyConflict("Ключ повторного запроса уже использован")
                    bound_result = self.get(bound["digest_id"])
                    if bound_result is not None:
                        return bound_result
            existing = self.get(result.digest_id)
            if (
                existing
                and request.use_ai
                and existing.mode == "fallback"
                and existing.model_dump() != result.model_dump()
            ):
                # Preserve old exports even if a legacy fallback occupied the
                # deterministic ID now used by a successful retry.
                result = result.model_copy(
                    update={"digest_id": result.digest_id + "-" + uuid4().hex[:16]}
                )
                existing = None
            if not existing:
                try:
                    with self.engine.begin() as connection:
                        connection.execute(
                            self.runs.insert().values(
                                id=result.digest_id,
                                request_hash=request_hash,
                                raw=request.model_dump(),
                                normalized=[normalize(a).model_dump() for a in request.articles],
                                result=result.model_dump(),
                                journal=[j.model_dump() for j in result.journal],
                            )
                        )
                        self._record_execution(connection, result)
                except IntegrityError:
                    existing = self.get(result.digest_id)
            if key:
                with self.engine.begin() as connection:
                    key_hash = hashlib.sha256(key.encode()).hexdigest()
                    record = (
                        connection.execute(
                            select(self.keys).where(self.keys.c.key_hash == key_hash)
                        )
                        .mappings()
                        .first()
                    )
                    if record and record["request_hash"] != request_hash:
                        raise IdempotencyConflict("Ключ повторного запроса уже использован")
                    if record:
                        bound_result = self.get(record["digest_id"])
                        if bound_result is not None:
                            return bound_result
                    if not record:
                        connection.execute(
                            self.keys.insert().values(
                                key_hash=key_hash,
                                request_hash=request_hash,
                                digest_id=result.digest_id,
                            )
                        )
        return existing or result

    def get(self, ident: str) -> Result | None:
        with self.engine.connect() as connection:
            data: Any = connection.execute(
                select(self.runs.c.result).where(self.runs.c.id == ident)
            ).first()
            return Result.model_validate(data[0]) if data else None

    @staticmethod
    def _status_configuration() -> str:
        # Only a digest of public execution configuration; never include the API key.
        context = {
            "configured": bool(os.getenv("LLM_API_KEY")),
            "model": os.getenv("LLM_MODEL", "gpt-4.1-mini"),
            "endpoint": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            "engine": ENGINE_VERSION,
            "prompt": "editorial-v3",
        }
        return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()

    def _record_execution(self, connection, result: Result) -> None:
        if result.mode not in {"ai", "fallback"} or result.llm_attempts < 1:
            return
        try:
            completed = datetime.fromisoformat(result.completed_at)
        except ValueError:
            return
        if completed.tzinfo is None:
            return
        details = result.model_dump(
            include={
                "digest_id",
                "mode",
                "model_name",
                "prompt_version",
                "completed_at",
                "application_version",
            }
        )
        configuration = self._status_configuration()
        slots = ["last_ai_run"]
        if result.mode == "ai":
            slots.append("last_successful_ai_run")
        for slot in slots:
            row = (
                connection.execute(
                    select(self.execution_status).where(self.execution_status.c.slot == slot)
                )
                .mappings()
                .first()
            )
            if row and row["configuration"] == configuration:
                previous = datetime.fromisoformat(row["details"]["completed_at"])
                if previous >= completed:
                    continue
            values = {"configuration": configuration, "details": details}
            if row:
                connection.execute(
                    self.execution_status.update()
                    .where(self.execution_status.c.slot == slot)
                    .values(**values)
                )
            else:
                connection.execute(self.execution_status.insert().values(slot=slot, **values))

    def public_execution_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {"last_ai_run": None, "last_successful_ai_run": None}
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(self.execution_status).where(
                    self.execution_status.c.configuration == self._status_configuration()
                )
            ).mappings()
            for row in rows:
                if row["slot"] in status:
                    status[row["slot"]] = {
                        key: value
                        for key, value in row["details"].items()
                        if key
                        in {
                            "mode",
                            "model_name",
                            "prompt_version",
                            "completed_at",
                            "application_version",
                        }
                    }
        return status
