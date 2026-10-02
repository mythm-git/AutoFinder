"""Provider-neutral structured AI request, response, and diagnostics models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from autofinder.core.exceptions import AIRequestError


class ProviderHealthResponse(BaseModel):
    """Deliberately neutral schema used only for Step 6 verification."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^ok$")
    message: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0, le=1)
    checks: list[str] = Field(min_length=1, max_length=3)


@dataclass(frozen=True)
class StructuredAIRequest:
    """One provider-independent request with one canonical Pydantic response model."""

    purpose: str
    system_instructions: str
    user_content: str
    response_model: type[BaseModel]
    schema_name: str | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.purpose.strip() or not self.system_instructions.strip() or not self.user_content.strip():
            raise AIRequestError("AI request purpose, instructions, and user content must be non-empty.")
        if not isinstance(self.response_model, type) or not issubclass(self.response_model, BaseModel):
            raise AIRequestError("AI response_model must be a Pydantic BaseModel subclass.")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise AIRequestError("AI max_output_tokens must be positive when supplied.")

    @property
    def resolved_schema_name(self) -> str:
        """Return a safe schema identifier for provider adapters."""
        name = (self.schema_name or self.response_model.__name__).strip()
        if not name.replace("_", "").isalnum():
            raise AIRequestError("AI schema_name must contain only letters, numbers, and underscores.")
        return name

    @property
    def json_schema(self) -> dict[str, Any]:
        """Generate the single canonical JSON Schema source for all adapters."""
        return self.response_model.model_json_schema()


@dataclass(frozen=True)
class AIUsageMetadata:
    """Optional provider-neutral token counts; values are never estimated."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ProviderResponse:
    """Sanitized raw structured payload returned by an individual provider adapter."""

    provider: str
    model: str
    content: str
    latency_seconds: float
    usage: AIUsageMetadata | None = None
    request_id: str | None = None
    finish_reason: str | None = None


@dataclass(frozen=True)
class ProviderAttempt:
    """Safe diagnostic summary; never includes prompts, responses, or credentials."""

    provider: str
    model: str
    outcome: str
    error_kind: str | None
    latency_seconds: float | None


@dataclass(frozen=True)
class StructuredAIResult:
    """Validated structured data plus safe provider-selection metadata."""

    data: BaseModel
    provider: str
    model: str
    latency_seconds: float
    usage: AIUsageMetadata | None
    fallback_used: bool
    attempts: tuple[ProviderAttempt, ...]
    request_id: str | None = None
    finish_reason: str | None = None

    @property
    def payload(self) -> dict[str, Any]:
        """Return the locally validated JSON-compatible structured data."""
        return self.data.model_dump(mode="json")
