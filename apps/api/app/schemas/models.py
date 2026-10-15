import re
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceType = Literal["media", "author", "vendor", "regulator", "official", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Article(StrictModel):
    id: str | None = Field(default=None, max_length=128)
    title: str | None = Field(default=None, max_length=500)
    text: str | None = Field(default=None, max_length=30000)
    source: str | None = Field(default=None, max_length=250)
    source_type: SourceType | None = None
    url: str | None = Field(default=None, max_length=2000)
    published_at: str | None = Field(default=None, max_length=100)
    read_error: str | None = Field(default=None, max_length=1000)
    original_record: dict[str, Any] | None = None


class DigestRequest(StrictModel):
    control_time: str
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    event_limit: int = Field(default=5, ge=1, le=5)
    use_ai: bool = False
    articles: list[Article] = Field(max_length=100)

    @field_validator("control_time")
    @classmethod
    def aware(cls, value: str) -> str:
        date = datetime.fromisoformat(value)
        if date.tzinfo is None:
            raise ValueError("Контрольное время должно содержать часовой пояс")
        try:
            date.astimezone(ZoneInfo("Europe/Moscow")) - timedelta(hours=24)
        except OverflowError:
            raise ValueError("Контрольное время выходит за допустимый диапазон дат") from None
        return date.isoformat()


class Evidence(StrictModel):
    fragment: str
    source_id: str
    url: str


class EditorialDecision(StrictModel):
    source_id: str
    relevant: bool
    evidence: Evidence


class EditorialGroup(StrictModel):
    source_ids: list[str] = Field(min_length=1, max_length=100)
    lead: Evidence
    priority: int = Field(ge=0, le=99)
    ranking_evidence: Evidence


class EditorialPlan(StrictModel):
    decisions: list[EditorialDecision] = Field(max_length=100)
    groups: list[EditorialGroup] = Field(max_length=100)


class GroundedSentence(StrictModel):
    text: str = Field(min_length=1, max_length=1600)
    evidence: list[Evidence] = Field(min_length=1, max_length=100)


class RewrittenEvent(StrictModel):
    event_id: str
    digest: list[GroundedSentence] = Field(min_length=1, max_length=100)
    post: list[GroundedSentence] = Field(min_length=1, max_length=100)


class RewrittenCopy(StrictModel):
    events: list[RewrittenEvent] = Field(max_length=5)


class SentenceVerdict(StrictModel):
    sentence_id: str
    entailed: bool
    evidence: list[Evidence] = Field(min_length=1, max_length=100)


class SemanticVerification(StrictModel):
    sentences: list[SentenceVerdict] = Field(max_length=1000)


class RankingFactors(StrictModel):
    impact: int = Field(ge=0, le=5)
    scale: int = Field(ge=0, le=5)
    urgency: int = Field(ge=0, le=5)
    audience_relevance: int = Field(ge=0, le=5)
    source_quality: int = Field(ge=0, le=5)
    recency: int = Field(default=0, ge=0, le=5)
    confirmation: int = Field(default=0, ge=0, le=5)
    new_facts: int = Field(default=0, ge=0, le=5)
    completeness: int = Field(default=0, ge=0, le=5)


class Event(StrictModel):
    event_id: str
    title: str
    summary: str
    consequences: str
    affected_entities: list[str] = []
    affected_systems: list[str] = []
    reported_by: list[str] = []
    confidence: Literal["high", "medium", "low"]
    is_preliminary: bool
    conflicts: list[str]
    source_ids: list[str]
    primary_source_id: str | None
    selection_reason: str
    ranking_factors: RankingFactors
    evidence: list[Evidence]
    numbers: list[str] = []
    event_date: str | None = None


class Journal(StrictModel):
    id: str | None
    title: str | None
    source: str | None
    source_type: SourceType | None
    url: str | None
    published_at: str | None
    status: str
    event_id: str | None = None
    inclusion_reason: str | None = None
    exclusion_reason: str | None = None
    missing_fields: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    relevance: bool = False
    period_check: bool = False
    fact_check: bool = False
    model_name: str = "extractive-local"
    prompt_version: str = "pipeline-v1"
    processed_at: str
    model_attempts: list[dict[str, str | int | bool]] = []
    source_index: int = 0
    original_record: dict[str, Any] = {}
    normalized_record: Article | None = None
    evidence: list[Evidence] = []
    related_sources: list[str] = []


class Check(StrictModel):
    name: str
    passed: bool
    details: str


class Metrics(StrictModel):
    input_count: int
    relevant_count: int
    excluded_count: int
    event_groups: int
    selected_count: int
    duration_ms: int
    model_calls: int = 0
    tokens_used: int = 0
    token_usage_available: bool = False
    cost_usd: float | None = None
    mode: str = "mock"
    model_attempts: list[dict[str, str | int | bool]] = []


class TokenUsage(StrictModel):
    input: int | None = Field(default=None, ge=0)
    output: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)


class Result(StrictModel):
    digest_id: str
    period_start: str
    period_end: str
    control_time: str
    timezone: str
    events: list[Event]
    event_count: int
    digest_text: str
    email_subject: str
    email_preview_html: str
    post_text: str
    warnings: list[str]
    sources: list[Article]
    journal: list[Journal]
    checks: list[Check]
    metrics: Metrics
    model_name: str
    model_version: str
    prompt_version: str
    created_at: str
    editorial_plan: EditorialPlan | None = None
    ai_copy: RewrittenCopy | None = None
    semantic_verification: SemanticVerification | None = None
    mode: Literal["ai", "mock", "fallback"] = "mock"
    llm_attempts: int = 0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    started_at: str = ""
    completed_at: str = ""
    application_version: str = "1.6"

    def digest_text_without_urls(self) -> str:
        return re.sub(r"https?://\S+", "", self.digest_text)

    def post_text_without_urls(self) -> str:
        return re.sub(r"https?://\S+", "", self.post_text)


class ParseRequest(StrictModel):
    format: Literal["json", "csv", "text"]
    content: str = Field(max_length=1_000_000)


class PreviewRequest(StrictModel):
    urls: list[str] = Field(max_length=5)


class DemoRequest(StrictModel):
    control_time: str | None = None
