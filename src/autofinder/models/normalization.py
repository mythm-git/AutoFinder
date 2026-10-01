"""Typed normalization results and non-fatal mapping diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from autofinder.models.normalized_listing import NormalizedListing


class NormalizationWarning(StrEnum):
    """Non-fatal source mapping availability or validity observations."""

    MISSING_PRICE = "missing_price"
    INVALID_PRICE = "invalid_price"
    UNKNOWN_CURRENCY = "unknown_currency"
    MISSING_LOCATION = "missing_location"
    MISSING_MILEAGE = "missing_mileage"
    INVALID_MILEAGE = "invalid_mileage"
    MISSING_POWER = "missing_power"
    INVALID_POWER = "invalid_power"
    UNKNOWN_SELLER_TYPE = "unknown_seller_type"


@dataclass(frozen=True)
class NormalizationResult:
    """One normalized listing and non-fatal source mapping warnings."""

    listing: NormalizedListing
    warnings: tuple[NormalizationWarning, ...]


@dataclass(frozen=True)
class NormalizationBatchResult:
    """Normalized output and warning totals for a deduplicated batch."""

    received_count: int
    normalized_count: int
    warning_count: int
    results: tuple[NormalizationResult, ...]
    listings: tuple[NormalizedListing, ...]
