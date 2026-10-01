"""Stable contract for future AI provider integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Provide uncertain vehicle interpretation without owning deal arithmetic."""

    @abstractmethod
    def analyze(self, listing: dict[str, Any]) -> dict[str, Any]:
        """Return structured AI output for a normalized listing."""
        raise NotImplementedError
