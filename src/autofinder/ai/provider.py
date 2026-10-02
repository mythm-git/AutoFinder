"""Stable contract for provider-specific structured-output adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from autofinder.ai.models import ProviderResponse, StructuredAIRequest


class AIProvider(ABC):
    """Translate one canonical request into one provider's structured API call."""

    name: str
    model: str

    @abstractmethod
    def generate_structured(self, request: StructuredAIRequest) -> ProviderResponse:
        """Return a sanitized provider response or a classified ``AIProviderError``."""
        raise NotImplementedError
