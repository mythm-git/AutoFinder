"""Provider-independent orchestration, validation, retries, and fallback."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping

from pydantic import ValidationError

from autofinder.ai.models import ProviderAttempt, StructuredAIRequest, StructuredAIResult
from autofinder.ai.provider import AIProvider
from autofinder.core.exceptions import AIAllProvidersFailed, AIProviderError, AIResponseValidationError


class AIManager:
    """Request validated structured output from a primary provider then one fallback."""

    def __init__(self, providers: Mapping[str, AIProvider], primary_provider: str, fallback_provider: str, max_retries_per_provider: int) -> None:
        if primary_provider not in providers or fallback_provider not in providers:
            raise ValueError("Configured AI providers must be registered.")
        if primary_provider == fallback_provider:
            raise ValueError("AI primary and fallback providers must differ.")
        if max_retries_per_provider < 0:
            raise ValueError("AI max_retries_per_provider cannot be negative.")
        self._providers = dict(providers)
        self._primary_provider = primary_provider
        self._fallback_provider = fallback_provider
        self._max_retries_per_provider = max_retries_per_provider
        self._logger = logging.getLogger("autofinder.ai.manager")

    def generate_structured(self, request: StructuredAIRequest) -> StructuredAIResult:
        """Generate locally validated data, falling back only for classified provider failures."""
        self._logger.info("AI request started: purpose=%s primary_provider=%s", request.purpose, self._primary_provider)
        attempts: list[ProviderAttempt] = []
        for index, provider_name in enumerate((self._primary_provider, self._fallback_provider)):
            provider = self._providers[provider_name]
            if index:
                self._logger.warning("AI fallback activated: provider=%s purpose=%s", provider_name, request.purpose)
            result = self._attempt_provider(provider, request, attempts, fallback_used=bool(index))
            if result is not None:
                return result
            if attempts and attempts[-1].error_kind == "non_retryable":
                break
        self._logger.error("AI request failed after configured providers: purpose=%s", request.purpose)
        raise AIAllProvidersFailed("All configured AI providers failed; no structured result was produced.")

    def _attempt_provider(self, provider: AIProvider, request: StructuredAIRequest, attempts: list[ProviderAttempt], fallback_used: bool) -> StructuredAIResult | None:
        for attempt_number in range(self._max_retries_per_provider + 1):
            try:
                self._logger.info("AI provider selected: provider=%s model=%s purpose=%s", provider.name, provider.model, request.purpose)
                response = provider.generate_structured(request)
                try:
                    data = request.response_model.model_validate_json(response.content)
                except (json.JSONDecodeError, ValidationError, ValueError) as error:
                    raise AIResponseValidationError("Provider structured response failed local schema validation.", kind="invalid_response") from error
                attempts.append(ProviderAttempt(provider.name, response.model, "success", None, response.latency_seconds))
                self._logger.info("AI provider succeeded: provider=%s model=%s fallback_used=%s", provider.name, response.model, fallback_used)
                return StructuredAIResult(data, response.provider, response.model, response.latency_seconds, response.usage, fallback_used, tuple(attempts), response.request_id, response.finish_reason)
            except AIProviderError as error:
                attempts.append(ProviderAttempt(provider.name, provider.model, "failed", error.kind, None))
                if not error.retryable:
                    attempts[-1] = ProviderAttempt(provider.name, provider.model, "failed", "non_retryable", None)
                    self._logger.error("AI provider configuration/request failure: provider=%s kind=%s", provider.name, error.kind)
                    return None
                if attempt_number < self._max_retries_per_provider:
                    self._logger.warning("AI provider retrying: provider=%s kind=%s attempt=%s", provider.name, error.kind, attempt_number + 1)
                    continue
                self._logger.warning("AI provider failed: provider=%s kind=%s", provider.name, error.kind)
                return None
        return None
