"""Deterministic Step 8 repair evidence built from validated upstream contracts."""

from __future__ import annotations

from typing import Any

from autofinder.analysis.models import VehicleAnalysis
from autofinder.models.normalized_listing import NormalizedListing


def build_repair_estimation_evidence(listing: NormalizedListing, analysis: VehicleAnalysis) -> dict[str, Any]:
    """Use normalized facts and Step 7 output without re-sending raw listing text."""
    return {
        "listing_identity": {"marketplace": listing.identity.marketplace, "external_listing_id": listing.identity.external_listing_id},
        "normalized_vehicle_facts": {
            "price_eur": listing.price_eur,
            "make": listing.vehicle.make,
            "model": listing.vehicle.model,
            "mileage_km": listing.vehicle.mileage_km,
            "power_ps": listing.vehicle.power_ps,
        },
        "validated_vehicle_analysis": analysis.model_dump(mode="json"),
    }
