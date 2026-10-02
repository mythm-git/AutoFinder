"""Groq adapter using the official Python SDK's strict JSON Schema output."""

from __future__ import annotations

import time
from typing import Any

from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq, InternalServerError, RateLimitError

from autofinder.ai.credentials import load_api_key
from autofinder.ai.models import AIUsageMetadata, ProviderResponse, StructuredAIRequest
from autofinder.ai.provider import AIProvider
from autofinder.core.exceptions import AIProviderError


class GroqProvider(AIProvider):
    """Adapt canonical requests to Groq Chat Completions structured outputs."""

    name = "groq"

    def __init__(self, model: str, timeout_seconds: int, *, api_key: str | None = None, client: Any | None = None) -> None:
        self.model = model
        self._timeout_seconds = timeout_seconds
        self._client = client or Groq(api_key=api_key or load_api_key("GROQ_API_KEY"), timeout=timeout_seconds)

    def generate_structured(self, request: StructuredAIRequest) -> ProviderResponse:
        """Call Groq with strict JSON Schema and return only safe final-answer metadata."""
        started = time.monotonic()
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": request.system_instructions}, {"role": "user", "content": request.user_content}],
                response_format={"type": "json_schema", "json_schema": {"name": request.resolved_schema_name, "strict": True, "schema": request.json_schema}},
                **({"max_completion_tokens": request.max_output_tokens} if request.max_output_tokens else {}),
            )
        except RateLimitError as error:
            raise AIProviderError("Groq rate limit prevented the request.", kind="rate_limit") from error
        except (APITimeoutError, APIConnectionError) as error:
            raise AIProviderError("Groq transport timed out or was unavailable.", kind="timeout") from error
        except InternalServerError as error:
            raise AIProviderError("Groq server failed the request.", kind="server_error") from error
        except APIStatusError as error:
            raise AIProviderError("Groq rejected the request.", kind="api_error", retryable=getattr(error, "status_code", 0) >= 500) from error
        try:
            content = completion.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise ValueError("missing content")
            usage = getattr(completion, "usage", None)
            return ProviderResponse(self.name, str(getattr(completion, "model", self.model)), content, time.monotonic() - started, _usage(usage), _safe_text(getattr(completion, "id", None)), _safe_text(getattr(completion.choices[0], "finish_reason", None)))
        except (AttributeError, IndexError, TypeError, ValueError) as error:
            raise AIProviderError("Groq response lacked structured content.", kind="invalid_response") from error


def _usage(value: Any) -> AIUsageMetadata | None:
    """Map documented Groq usage fields without estimating unavailable values."""
    if value is None:
        return None
    return AIUsageMetadata(getattr(value, "prompt_tokens", None), getattr(value, "completion_tokens", None), getattr(value, "total_tokens", None))


def _safe_text(value: Any) -> str | None:
    """Accept only bounded safe scalar metadata; never serialize raw responses."""
    return value if isinstance(value, str) and len(value) <= 200 else None
