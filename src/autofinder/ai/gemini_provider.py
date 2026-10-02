"""Gemini adapter using the official Google Gen AI SDK's JSON Schema output."""

from __future__ import annotations

import time
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from autofinder.ai.credentials import load_api_key
from autofinder.ai.models import AIUsageMetadata, ProviderResponse, StructuredAIRequest
from autofinder.ai.provider import AIProvider
from autofinder.core.exceptions import AIProviderError


class GeminiProvider(AIProvider):
    """Adapt canonical requests to Gemini structured-output generation."""

    name = "gemini"

    def __init__(self, model: str, timeout_seconds: int, *, api_key: str | None = None, client: Any | None = None) -> None:
        self.model = model
        self._timeout_seconds = timeout_seconds
        self._client = client or genai.Client(api_key=api_key or load_api_key("GEMINI_API_KEY"))

    def generate_structured(self, request: StructuredAIRequest) -> ProviderResponse:
        """Call Gemini for JSON Schema output and return no hidden reasoning or raw response."""
        started = time.monotonic()
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=request.user_content,
                config=types.GenerateContentConfig(system_instruction=request.system_instructions, response_mime_type="application/json", response_json_schema=request.json_schema, max_output_tokens=request.max_output_tokens, http_options=types.HttpOptions(timeout=self._timeout_seconds * 1000)),
            )
        except errors.ServerError as error:
            raise AIProviderError("Gemini server failed the request.", kind="server_error") from error
        except errors.ClientError as error:
            if getattr(error, "code", None) == 429:
                raise AIProviderError("Gemini rate limit prevented the request.", kind="rate_limit") from error
            raise AIProviderError("Gemini rejected the request.", kind="api_error", retryable=False) from error
        except httpx.TimeoutException as error:
            raise AIProviderError("Gemini transport timed out.", kind="timeout") from error
        try:
            content = getattr(response, "text", None)
            if not isinstance(content, str) or not content.strip():
                raise ValueError("missing content")
            return ProviderResponse(self.name, self.model, content, time.monotonic() - started, _usage(getattr(response, "usage_metadata", None)), _safe_text(getattr(response, "response_id", None)), _safe_text(_finish_reason(response)))
        except (AttributeError, IndexError, TypeError, ValueError) as error:
            raise AIProviderError("Gemini response lacked structured content.", kind="invalid_response") from error


def _usage(value: Any) -> AIUsageMetadata | None:
    """Map documented Gemini token metadata without estimating unavailable values."""
    if value is None:
        return None
    return AIUsageMetadata(getattr(value, "prompt_token_count", None), getattr(value, "candidates_token_count", None), getattr(value, "total_token_count", None))


def _finish_reason(response: Any) -> Any:
    """Read only candidate finish metadata, never thought/reasoning fields."""
    candidates = getattr(response, "candidates", None)
    return getattr(candidates[0], "finish_reason", None) if candidates else None


def _safe_text(value: Any) -> str | None:
    """Accept only bounded safe scalar metadata; never serialize raw responses."""
    return value if isinstance(value, str) and len(value) <= 200 else None
