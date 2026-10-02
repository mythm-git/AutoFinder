"""Gemini adapter using the official Google Gen AI SDK's JSON Schema output."""

from __future__ import annotations

import time
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from autofinder.ai.credentials import load_api_key
from autofinder.ai.diagnostics import error_details
from autofinder.ai.models import AIUsageMetadata, ProviderResponse, StructuredAIRequest
from autofinder.ai.schema_adapters import gemini_schema
from autofinder.ai.provider import AIProvider
from autofinder.core.exceptions import AIProviderError


class GeminiProvider(AIProvider):
    """Adapt canonical requests to Gemini structured-output generation."""

    name = "gemini"

    def __init__(self, model: str, timeout_seconds: int, *, api_key: str | None = None, client: Any | None = None) -> None:
        self.model = model
        self._timeout_seconds = timeout_seconds
        self._client = client or genai.Client(api_key=api_key or load_api_key("GEMINI_API_KEY"), http_options=types.HttpOptions(timeout=timeout_seconds * 1000))

    def generate_structured(self, request: StructuredAIRequest) -> ProviderResponse:
        """Call Gemini for JSON Schema output and return no hidden reasoning or raw response."""
        started = time.monotonic()
        try:
            interaction = self._client.interactions.create(
                model=self.model,
                input=request.user_content,
                system_instruction=request.system_instructions,
                response_format={"type": "text", "mime_type": "application/json", "schema": gemini_schema(request)},
                **({"generation_config": {"max_output_tokens": request.max_output_tokens, "thinking_level": "low", "thinking_summaries": "none"}} if request.max_output_tokens else {"generation_config": {"thinking_level": "low", "thinking_summaries": "none"}}),
            )
        except errors.ServerError as error:
            raise _provider_error(error, "server_error", retryable=True) from error
        except errors.ClientError as error:
            status, provider_code, _ = error_details(error)
            kind = "rate_limit" if status == 429 else provider_code or "api_error"
            raise _provider_error(error, kind, retryable=status == 429) from error
        except httpx.TimeoutException as error:
            raise _provider_error(error, "timeout", retryable=True) from error
        try:
            content = getattr(interaction, "output_text", None)
            if not isinstance(content, str) or not content.strip():
                raise ValueError("missing output_text")
            return ProviderResponse(self.name, self.model, content, time.monotonic() - started, _usage(getattr(interaction, "usage", getattr(interaction, "usage_metadata", None))), _safe_text(getattr(interaction, "id", None)), _safe_text(getattr(interaction, "status", None)))
        except (AttributeError, IndexError, TypeError, ValueError) as error:
            raise AIProviderError("Gemini response lacked structured content.", kind="invalid_response", stage="response_handling", exception_type=type(error).__name__) from error


def _provider_error(error: Any, kind: str, *, retryable: bool) -> AIProviderError:
    """Preserve a redacted SDK diagnostic without retaining raw response bodies."""
    status_code, provider_code, message = error_details(error)
    return AIProviderError(message, kind=kind, retryable=retryable, stage="provider_request", exception_type=type(error).__name__, status_code=status_code, provider_code=provider_code)


def _usage(value: Any) -> AIUsageMetadata | None:
    """Map legacy or Interactions token metadata without estimating unavailable values."""
    if value is None:
        return None
    return AIUsageMetadata(
        getattr(value, "total_input_tokens", getattr(value, "prompt_token_count", None)),
        getattr(value, "total_output_tokens", getattr(value, "candidates_token_count", None)),
        getattr(value, "total_tokens", getattr(value, "total_token_count", None)),
    )


def _safe_text(value: Any) -> str | None:
    """Accept only bounded safe scalar metadata; never serialize raw responses."""
    return value if isinstance(value, str) and len(value) <= 200 else None
