"""Stable contract for future marketplace collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ListingCollector(ABC):
    """Collect raw marketplace evidence without downstream business decisions."""

    @abstractmethod
    def collect(self) -> list[dict[str, Any]]:
        """Return raw listing records preserved for future normalization.

        Raises:
            NotImplementedError: Until a concrete collector is implemented.
        """
        raise NotImplementedError
