import hashlib
import threading
from typing import Any

from sqlalchemy import JSON, Column, MetaData, String, Table, create_engine, select
from sqlalchemy.exc import IntegrityError

from app.config import execution_fingerprint
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
            run_record = connection.execute(
                select(self.runs.c.result).where(self.runs.c.request_hash == request_hash)
            ).first()
            return Result.model_validate(run_record[0]) if run_record else None

    def save(self, request: DigestRequest, result: Result, key: str | None) -> Result:
        request_hash = self.request_hash(request)
        with self.lock:
            existing = self.get(result.digest_id)
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
