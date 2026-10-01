"""Stable contract for marketplace collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from autofinder.models.collection import CollectionResult


class ListingCollector(ABC):
    """Collect raw marketplace evidence without downstream business decisions."""

    @abstractmethod
    def collect(self, requested_count: int | None = None) -> CollectionResult:
        """Collect a bounded newest-first raw marketplace batch.

        Args:
            requested_count: Optional acquisition limit overriding the collector
                default. It is independent of later unseen-listing limits.

        Returns:
            Raw evidence and safe collection metadata.

        Raises:
            NotImplementedError: Until a concrete collector is implemented.
        """
        raise NotImplementedError
