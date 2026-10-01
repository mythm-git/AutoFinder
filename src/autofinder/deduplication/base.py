"""Stable contract for future seen-listing repositories."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SeenListingRepository(ABC):
    """Store listing identities independently of their persistence mechanism."""

    @abstractmethod
    def has_seen(self, marketplace: str, external_listing_id: str) -> bool:
        """Return whether a marketplace-specific listing identity was processed."""
        raise NotImplementedError

    @abstractmethod
    def mark_seen(self, marketplace: str, external_listing_id: str) -> None:
        """Persist a processed marketplace-specific listing identity."""
        raise NotImplementedError
