"""Stable contract for marketplace collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from autofinder.models.collection import CollectionResult


class ListingCollector(ABC):
    """Collect raw marketplace evidence without downstream business decisions."""

    @abstractmethod
    def collect(self) -> CollectionResult:
        """Collect the configured bounded newest-first raw marketplace batch.

        Returns:
            Raw evidence and safe collection metadata.

        Raises:
            NotImplementedError: Until a concrete collector is implemented.
        """
        raise NotImplementedError
