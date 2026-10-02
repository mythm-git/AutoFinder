"""Composition root for the configured provider-agnostic AI manager."""

from __future__ import annotations

from autofinder.ai.gemini_provider import GeminiProvider
from autofinder.ai.groq_provider import GroqProvider
from autofinder.ai.manager import AIManager
from autofinder.core.config import AIConfig


def create_ai_manager(config: AIConfig) -> AIManager:
    """Build the only application-facing manager from typed non-secret settings."""
    providers = {
        "groq": GroqProvider(config.groq.model, config.timeout_seconds),
        "gemini": GeminiProvider(config.gemini.model, config.timeout_seconds),
    }
    return AIManager(providers, config.primary_provider, config.fallback_provider, config.max_retries_per_provider)
