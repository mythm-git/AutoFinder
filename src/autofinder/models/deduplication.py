"""Typed output of early listing duplicate detection."""

from __future__ import annotations

from dataclasses import dataclass

from autofinder.models.collection import RawMarketplaceListing


@dataclass(frozen=True)
class DeduplicationResult:
    """Safe statistics and raw listings that may proceed to later pipeline stages."""

    received_count: int
    new_count: int
    previously_seen_count: int
    invalid_identity_count: int
    duplicate_within_batch_count: int
    new_listings: tuple[RawMarketplaceListing, ...]
