from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class TargetType(StrEnum):
    API = "api"
    BROWSER = "browser"


class RunStatus(StrEnum):
    QUEUED = "queued"
    PROFILING = "profiling"
    RUNNING = "running"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


class AttackCategory(StrEnum):
    INSTRUCTION = "instruction_based"
    TASK_DEFLECTION = "task_deflection"
    REPETITION = "repetition"
    CONTEXT_SWITCHING = "context_switching"
    VARIABLE_CODE = "variable_code_based"
    FORMATTING = "formatting"
    OBFUSCATION = "obfuscation"
    COGNITIVE_ROLE = "cognitive_role_based"
    INDIRECT = "indirect"


class BrowserSelectors(BaseModel):
    input: str = "#message-input"
    submit: str = "#send-message"
    messages: str = "#messages [data-role='assistant']"


class TargetConfig(BaseModel):
    type: TargetType
    url: HttpUrl
    model: str | None = None
    selectors: BrowserSelectors | None = None
    authorization_confirmed: bool = False

    @model_validator(mode="after")
    def require_authorization(self) -> "TargetConfig":
        if not self.authorization_confirmed:
            raise ValueError("Explicit authorization confirmation is required")
        if self.type == TargetType.BROWSER and not self.selectors:
            self.selectors = BrowserSelectors()
        return self


class CreateRunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target: TargetConfig
    categories: list[AttackCategory] = Field(default_factory=lambda: list(AttackCategory))
    max_attempts: int = Field(default=9, ge=1, le=50)


class TargetProfile(BaseModel):
    domain: str = "general assistant"
    purpose: str = "answer user questions"
    capabilities: list[str] = Field(default_factory=lambda: ["text chat"])
    observed_constraints: list[str] = Field(default_factory=list)
    sample_response: str = ""


class AttackTemplate(BaseModel):
    id: str
    category: AttackCategory
    technique: str
    prompt: str
    source: str = "AgentProbe"
    prerequisites: list[str] = Field(default_factory=list)


class Evaluation(BaseModel):
    success: bool
    severity: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    rationale: str
    evidence: str = ""


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    @classmethod
    def from_mapping(cls, usage: dict[str, Any] | None, *, called: bool = False) -> "TokenUsage":
        usage = usage or {}
        input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            calls=1 if called else int(usage.get("calls", 0) or 0),
        )

    def plus(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            calls=self.calls + other.calls,
        )


class AttackAttempt(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    template_id: str
    category: AttackCategory
    technique: str
    source: str = "AgentProbe"
    prompt: str
    response: str
    duration_ms: int
    evaluation: Evaluation
    token_usage: dict[str, TokenUsage] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Report(BaseModel):
    total_attacks: int
    successful_attacks: int
    attack_success_rate: float
    average_severity: float
    category_vulnerability: dict[str, float]
    duration_ms: int
    recommendations: list[str]
    token_usage: dict[str, TokenUsage] = Field(default_factory=dict)
    total_tokens: int = 0


class ScanRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    target: TargetConfig
    categories: list[AttackCategory]
    max_attempts: int
    status: RunStatus = RunStatus.QUEUED
    profile: TargetProfile | None = None
    attempts: list[AttackAttempt] = Field(default_factory=list)
    report: Report | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
