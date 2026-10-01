"""Typed deterministic filtering decisions and stable reason codes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from autofinder.models.normalized_listing import NormalizedListing


class FilterRejectionReason(StrEnum):
    """Stable machine-readable reasons why a listing cannot continue."""

    INVALID_IDENTITY = "invalid_identity"
    MISSING_OR_INVALID_URL = "missing_or_invalid_url"
    MISSING_PRICE = "missing_price"
    INVALID_PRICE = "invalid_price"
    PRICE_BELOW_MINIMUM = "price_below_minimum"
    PRICE_ABOVE_MAXIMUM = "price_above_maximum"
    DEALER_SELLER = "dealer_seller"
    DEALER_TEXT_INDICATOR = "dealer_text_indicator"
    INVALID_MILEAGE = "invalid_mileage"
    MILEAGE_BELOW_MINIMUM = "mileage_below_minimum"
    MILEAGE_ABOVE_MAXIMUM = "mileage_above_maximum"
    INVALID_POWER = "invalid_power"
    POWER_BELOW_MINIMUM = "power_below_minimum"
    POWER_ABOVE_MAXIMUM = "power_above_maximum"
    UNUSABLE_LISTING = "unusable_listing"


class FilterWarning(StrEnum):
    """Non-blocking deterministic data-quality observations."""

    MISSING_MILEAGE = "missing_mileage"
    MISSING_POWER = "missing_power"
    UNKNOWN_SELLER_TYPE = "unknown_seller_type"


@dataclass(frozen=True)
class BasicFilterResult:
    """Decision for one normalized listing without changing source evidence."""

    listing: NormalizedListing
    passed: bool
    rejection_reasons: tuple[FilterRejectionReason, ...]
    warnings: tuple[FilterWarning, ...]
    matched_indicators: tuple[str, ...]


@dataclass(frozen=True)
class BasicFilterBatchResult:
    """Summary of deterministic filtering for deduplicated normalized listings."""

    received_count: int
    passed_count: int
    rejected_count: int
    passed_listings: tuple[NormalizedListing, ...]
    results: tuple[BasicFilterResult, ...]
    rejection_reason_counts: dict[FilterRejectionReason, int]
