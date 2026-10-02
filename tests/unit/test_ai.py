"""Fixture-only tests for provider-agnostic structured AI infrastructure."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, Field

from autofinder.ai.credentials import load_api_key
from autofinder.ai.gemini_provider import GeminiProvider
from autofinder.ai.groq_provider import GroqProvider
from autofinder.ai.manager import AIManager
from autofinder.ai.models import AIUsageMetadata, ProviderHealthResponse, ProviderResponse, StructuredAIRequest
from autofinder.ai.provider import AIProvider
from autofinder.core.config import load_config
from autofinder.core.exceptions import AIAllProvidersFailed, AIConfigurationError, AIProviderError, AIRequestError


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "autofinder.yaml"
VALID = json.dumps({"status": "ok", "message": "structured response working", "confidence": 1.0, "checks": ["schema"]})


class FakeProvider(AIProvider):
    def __init__(self, name: str, outcomes: list[ProviderResponse | Exception], model: str | None = None) -> None:
        self.name = name
        self.model = model or f"{name}-model"
        self.outcomes = outcomes
        self.calls = 0

    def generate_structured(self, ai_request: StructuredAIRequest) -> ProviderResponse:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(provider: str, content: str = VALID, usage: AIUsageMetadata | None = None) -> ProviderResponse:
    return ProviderResponse(provider, f"{provider}-model", content, 0.01, usage, "safe-id", "stop")


@pytest.fixture
def ai_request() -> StructuredAIRequest:
    return StructuredAIRequest("provider_health", "Return only the required JSON.", "Confirm structured output.", ProviderHealthResponse)


def test_ai_configuration_is_typed_and_rejects_unknown_provider(tmp_path: Path) -> None:
    config = load_config(CONFIG_PATH)
    assert config.ai.primary_provider == "groq"
    assert config.ai.fallback_provider == "gemini"
    assert config.ai.timeout_seconds == 60
    assert config.ai.max_retries_per_provider == 1
    assert config.ai.groq.model == "openai/gpt-oss-120b"
    assert config.ai.gemini.model == "gemini-3.8-flash"
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(CONFIG_PATH.read_text(encoding="utf-8").replace('primary_provider: "groq"', 'primary_provider: "unknown"'), encoding="utf-8")
    with pytest.raises(Exception, match="providers must be groq or gemini"):
        load_config(invalid)


def test_missing_api_keys_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("autofinder.ai.credentials.load_dotenv", lambda: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(AIConfigurationError, match="GROQ_API_KEY"):
        load_api_key("GROQ_API_KEY")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(AIConfigurationError, match="GEMINI_API_KEY"):
        load_api_key("GEMINI_API_KEY")


def test_ai_request_validation_and_canonical_schema(ai_request: StructuredAIRequest) -> None:
    assert ai_request.resolved_schema_name == "ProviderHealthResponse"
    assert ai_request.json_schema["properties"]["confidence"]["maximum"] == 1
    with pytest.raises(AIRequestError):
        StructuredAIRequest("", "system", "user", ProviderHealthResponse)


def test_primary_success_skips_fallback_and_exposes_safe_metadata(ai_request: StructuredAIRequest) -> None:
    groq, gemini = FakeProvider("groq", [response("groq", usage=AIUsageMetadata(4, 3, 7))]), FakeProvider("gemini", [response("gemini")])
    result = AIManager({"groq": groq, "gemini": gemini}, "groq", "gemini", 0).generate_structured(ai_request)
    assert result.provider == "groq"
    assert result.model == "groq-model"
    assert result.payload["status"] == "ok"
    assert result.usage == AIUsageMetadata(4, 3, 7)
    assert not result.fallback_used and gemini.calls == 0


@pytest.mark.parametrize("kind", ["timeout", "rate_limit", "invalid_response"])
def test_retryable_primary_failure_uses_gemini(ai_request: StructuredAIRequest, kind: str) -> None:
    groq = FakeProvider("groq", [AIProviderError("safe", kind=kind)])
    gemini = FakeProvider("gemini", [response("gemini")])
    result = AIManager({"groq": groq, "gemini": gemini}, "groq", "gemini", 0).generate_structured(ai_request)
    assert result.provider == "gemini" and result.fallback_used
    assert result.attempts[0].error_kind == kind


@pytest.mark.parametrize("content", ["not json", '{"status":"ok"}', '{"status":"wrong","message":"x","confidence":2,"checks":[]}'])
def test_invalid_provider_output_falls_back(ai_request: StructuredAIRequest, content: str) -> None:
    result = AIManager({"groq": FakeProvider("groq", [response("groq", content)]), "gemini": FakeProvider("gemini", [response("gemini")])}, "groq", "gemini", 0).generate_structured(ai_request)
    assert result.provider == "gemini" and result.fallback_used


def test_both_provider_failures_fail_closed_and_retries_are_bounded(ai_request: StructuredAIRequest) -> None:
    groq = FakeProvider("groq", [AIProviderError("safe", kind="timeout"), AIProviderError("safe", kind="timeout")])
    gemini = FakeProvider("gemini", [AIProviderError("safe", kind="rate_limit"), AIProviderError("safe", kind="rate_limit")])
    with pytest.raises(AIAllProvidersFailed):
        AIManager({"groq": groq, "gemini": gemini}, "groq", "gemini", 1).generate_structured(ai_request)
    assert groq.calls == gemini.calls == 2


def test_non_retryable_error_does_not_call_fallback(ai_request: StructuredAIRequest) -> None:
    groq = FakeProvider("groq", [AIProviderError("safe", kind="configuration", retryable=False)])
    gemini = FakeProvider("gemini", [response("gemini")])
    with pytest.raises(AIAllProvidersFailed):
        AIManager({"groq": groq, "gemini": gemini}, "groq", "gemini", 1).generate_structured(ai_request)
    assert groq.calls == 1 and gemini.calls == 0


def test_groq_adapter_translates_canonical_ai_request_and_usage(ai_request: StructuredAIRequest) -> None:
    captured: dict[str, object] = {}
    completion = SimpleNamespace(id="groq-safe", model="configured-groq", usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3, total_tokens=5), choices=[SimpleNamespace(message=SimpleNamespace(content=VALID), finish_reason="stop")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: captured.update(kwargs) or completion)))
    result = GroqProvider("configured-groq", 12, client=client).generate_structured(ai_request)
    assert captured["model"] == "configured-groq"
    assert captured["response_format"]["json_schema"]["strict"] is True  # type: ignore[index]
    assert result.usage == AIUsageMetadata(2, 3, 5)


def test_gemini_adapter_translates_canonical_ai_request_and_allows_missing_usage(ai_request: StructuredAIRequest) -> None:
    captured: dict[str, object] = {}
    api_response = SimpleNamespace(text=VALID, usage_metadata=None, response_id="gemini-safe", candidates=[SimpleNamespace(finish_reason="STOP")])
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: captured.update(kwargs) or api_response))
    result = GeminiProvider("configured-gemini", 12, client=client).generate_structured(ai_request)
    assert captured["model"] == "configured-gemini"
    assert result.usage is None and result.finish_reason == "STOP"


def test_logs_do_not_include_provider_error_detail(ai_request: StructuredAIRequest, caplog: pytest.LogCaptureFixture) -> None:
    secret = "never-log-this-secret"
    with pytest.raises(AIAllProvidersFailed):
        AIManager({"groq": FakeProvider("groq", [AIProviderError(secret)]), "gemini": FakeProvider("gemini", [AIProviderError(secret)])}, "groq", "gemini", 0).generate_structured(ai_request)
    assert secret not in caplog.text


class WrongSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int = Field(ge=1)


def test_same_ai_request_contract_can_use_either_provider() -> None:
    ai_request = StructuredAIRequest("neutral", "system", "user", WrongSchema)
    for provider_name in ("groq", "gemini"):
        result = AIManager({"groq": FakeProvider("groq", [response("groq", '{"value":1}')]), "gemini": FakeProvider("gemini", [response("gemini", '{"value":1}')])}, provider_name, "gemini" if provider_name == "groq" else "groq", 0).generate_structured(ai_request)
        assert result.payload == {"value": 1}
