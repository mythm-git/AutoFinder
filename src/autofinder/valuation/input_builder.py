"""Deterministic evidence boundary for temporary AI-only valuation."""

from __future__ import annotations

from typing import Any

from autofinder.analysis.models import VehicleAnalysis
from autofinder.models.normalized_listing import NormalizedListing
from autofinder.repair.models import RepairEstimate


def build_ai_valuation_evidence(listing: NormalizedListing, analysis: VehicleAnalysis, repair_estimate: RepairEstimate) -> dict[str, Any]:
    """Provide canonical facts plus validated analysis/repair outputs, not raw text."""
    return {
        "listing_identity": {"marketplace": listing.identity.marketplace, "external_listing_id": listing.identity.external_listing_id},
        "normalized_vehicle_facts": {
            "asking_price_eur": listing.price_eur,
            "make": listing.vehicle.make,
            "model": listing.vehicle.model,
            "mileage_km": listing.vehicle.mileage_km,
            "power_ps": listing.vehicle.power_ps,
        },
        "validated_vehicle_analysis": analysis.model_dump(mode="json"),
        "validated_repair_estimate": repair_estimate.model_dump(mode="json"),
    }
