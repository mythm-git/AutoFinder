"""Stable contract for marketplace-specific canonical listing normalizers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.normalization import NormalizationBatchResult, NormalizationResult


class ListingNormalizer(ABC):
    """Convert post-dedup raw listings into canonical AutoFinder domain models."""

    @abstractmethod
    def normalize(self, listing: RawMarketplaceListing) -> NormalizationResult:
        """Normalize one raw listing without mutating its source evidence."""
        raise NotImplementedError

    @abstractmethod
    def normalize_batch(self, listings: tuple[RawMarketplaceListing, ...]) -> NormalizationBatchResult:
        """Normalize a deduplicated raw listing batch."""
        raise NotImplementedError
