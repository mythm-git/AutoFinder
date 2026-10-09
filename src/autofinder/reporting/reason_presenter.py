"""Canonical human presentation for stable filter and decision reason codes."""

from __future__ import annotations

from autofinder.models.filtering import FilterRejectionReason
from autofinder.notifications.runtime_reporter import reason_text

_FILTER_TEXT = {
    FilterRejectionReason.INVALID_IDENTITY.value: "Listing identity is invalid.",
    FilterRejectionReason.MISSING_OR_INVALID_URL.value: "Listing URL is missing or invalid.",
    FilterRejectionReason.MISSING_PRICE.value: "Listing price is missing.",
    FilterRejectionReason.INVALID_PRICE.value: "Listing price is invalid.",
    FilterRejectionReason.PRICE_BELOW_MINIMUM.value: "Price is below the configured range.",
    FilterRejectionReason.PRICE_ABOVE_MAXIMUM.value: "Price exceeds the configured range.",
    FilterRejectionReason.DEALER_SELLER.value: "Dealer seller detected.",
    FilterRejectionReason.DEALER_TEXT_INDICATOR.value: "Dealer text indicator detected.",
    FilterRejectionReason.INVALID_MILEAGE.value: "Mileage is invalid.",
    FilterRejectionReason.MILEAGE_BELOW_MINIMUM.value: "Mileage is below the configured range.",
    FilterRejectionReason.MILEAGE_ABOVE_MAXIMUM.value: "Mileage exceeds the configured range.",
    FilterRejectionReason.INVALID_POWER.value: "Power is invalid.",
    FilterRejectionReason.POWER_BELOW_MINIMUM.value: "Power is below the configured range.",
    FilterRejectionReason.POWER_ABOVE_MAXIMUM.value: "Power exceeds the configured range.",
    FilterRejectionReason.UNUSABLE_LISTING.value: "Listing does not contain usable vehicle information.",
}


def present_reason(code: str) -> str:
    """Humanize one canonical code while preserving unknown codes safely."""
    return _FILTER_TEXT.get(code, reason_text(code) if code.startswith(("expected_", "vehicle_", "conservative_", "analysis_", "repair_", "valuation_", "listing_")) else f"Unrecognized diagnostic reason: {code}")
