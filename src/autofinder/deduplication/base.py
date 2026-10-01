"""Stable contract for persistent seen-listing repositories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from autofinder.models.identity import ListingIdentity


class SeenListingRepository(ABC):
    """Store listing identities independently of their persistence mechanism."""

    @abstractmethod
    def contains(self, identity: ListingIdentity) -> bool:
        """Return whether an identity has been persisted previously."""
        raise NotImplementedError

    @abstractmethod
    def mark_seen(self, identity: ListingIdentity, first_seen_at: datetime) -> None:
        """Persist a new identity while preserving its original first-seen timestamp."""
        raise NotImplementedError
