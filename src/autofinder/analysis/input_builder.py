"""Deterministic, minimal evidence boundary for text-only vehicle analysis."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from autofinder.models.normalized_listing import NormalizedListing


_ROOT_ATTRIBUTE_KEYS = (
    "firstRegistration",
    "registrationYear",
    "fuel",
    "fuelType",
    "transmission",
    "gearbox",
    "engine",
    "engineCc",
    "displacement",
    "tuv",
    "tuvUntil",
    "huUntil",
    "accidentFree",
    "accidentHistory",
    "owners",
    "numberOfOwners",
)
_VEHICLE_ATTRIBUTE_KEYS = _ROOT_ATTRIBUTE_KEYS + ("variant", "trim", "powerKw")


def build_vehicle_analysis_evidence(listing: NormalizedListing) -> dict[str, Any]:
    """Build stable listing evidence without serializing arbitrary raw payload data.

    Images, source URLs, collection timestamps, internal state, and unselected raw
    metadata are deliberately excluded. Structured canonical values are presented
    separately so the model can recognize their priority over free text.
    """
    source = listing.source.raw_data
    return {
        "listing_identity": {"marketplace": listing.identity.marketplace, "external_listing_id": listing.identity.external_listing_id},
        "structured_source": {
            "title": listing.title,
            "price_eur": listing.price_eur,
            "currency": listing.currency,
            "location": {"city": listing.location.city, "postal_code": listing.location.postal_code},
            "seller_type": listing.seller.type.value,
            "vehicle": {
                "make": listing.vehicle.make,
                "model": listing.vehicle.model,
                "mileage_km": listing.vehicle.mileage_km,
                "power_ps": listing.vehicle.power_ps,
            },
        },
        "listing_text": {"title": listing.title, "description": listing.description},
        "selected_raw_vehicle_attributes": _selected_raw_attributes(source),
    }


def _selected_raw_attributes(source: dict[str, Any]) -> dict[str, Any]:
    """Retain only whitelisted scalar structured attributes useful for identification."""
    selected = {key: deepcopy(source[key]) for key in _ROOT_ATTRIBUTE_KEYS if key in source and _safe_scalar(source[key])}
    vehicle = source.get("vehicle")
    if isinstance(vehicle, dict):
        vehicle_selected = {key: deepcopy(vehicle[key]) for key in _VEHICLE_ATTRIBUTE_KEYS if key in vehicle and _safe_scalar(vehicle[key])}
        if vehicle_selected:
            selected["vehicle"] = vehicle_selected
    return selected


def _safe_scalar(value: Any) -> bool:
    """Permit only scalar attributes; never pass opaque nested source payloads."""
    return value is None or isinstance(value, (str, int, float, bool))
