"""Run one sanitized repair estimate and one AI-only valuation through AIManager."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from autofinder.ai.factory import create_ai_manager
from autofinder.analysis.models import VehicleAnalysis
from autofinder.core.config import load_config
from autofinder.core.runtime import load_project_environment
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer
from autofinder.repair import RepairEstimator
from autofinder.valuation import AIValuator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json"


def main() -> int:
    """Use a sanitized completed-repairs analysis fixture; never send raw source text."""
    load_project_environment(PROJECT_ROOT)
    config = load_config(PROJECT_ROOT / "config" / "autofinder.yaml")
    raw = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))[0]
    listing = ApifyKleinanzeigenNormalizer().normalize(RawMarketplaceListing("kleinanzeigen", raw, datetime.now(UTC))).listing
    analysis = VehicleAnalysis.model_validate({
        "vehicle": {"structured_source": {"make": listing.vehicle.make, "model": listing.vehicle.model, "mileage_km": listing.vehicle.mileage_km, "power_ps": listing.vehicle.power_ps}, "interpreted_from_listing": {"make": None, "model": None, "variant": None, "registration_year": None, "engine": None, "fuel_type": None, "transmission": None, "power_kw": None, "engine_cc": None, "tuv_until": None, "accident_free": None}},
        "current_faults": [],
        "completed_repairs": [{"component": "front brakes", "repair": "replaced", "mileage_km": None, "date_or_timeframe": "recently", "evidence": "Sanitized fixture: front brakes replaced.", "confidence": 0.9}, {"component": "battery", "repair": "replaced", "mileage_km": None, "date_or_timeframe": "recently", "evidence": "Sanitized fixture: battery replaced.", "confidence": 0.9}],
        "maintenance_history": [], "seller_claims": [], "positive_signals": [],
        "risk_flags": [{"category": "limited_information", "explanation": "Service and TÜV detail are limited.", "evidence": "Sanitized fixture has no further records.", "confidence": 0.8}],
        "missing_information": [{"topic": "tuv", "reason": "No TÜV date is stated."}, {"topic": "service_history", "reason": "No broader service record is stated."}],
        "condition_summary": "Documented completed brakes and battery, with limited remaining history.", "overall_condition": "average", "risk_level": "medium", "analysis_confidence": 0.7,
    })
    manager = create_ai_manager(config.ai)
    repair = RepairEstimator(manager).estimate(listing, analysis)
    valuation = AIValuator(manager).value(listing, analysis, repair.estimate)
    summary = repair.estimate.cost_summary
    print(f"repair_provider={repair.provider} model={repair.model} latency_seconds={repair.latency_seconds:.3f} usage={repair.usage}")
    print(f"repair_counts=required:{len(repair.estimate.required_repairs)} near_term:{len(repair.estimate.near_term_maintenance)} uncertainty:{len(repair.estimate.uncertainty_items)} totals={summary.minimum_total_eur}/{summary.expected_total_eur}/{summary.high_total_eur} confidence={repair.estimate.confidence:.2f}")
    print(f"valuation_provider={valuation.provider} model={valuation.model} latency_seconds={valuation.latency_seconds:.3f} usage={valuation.usage}")
    print(f"valuation_as_is={valuation.valuation.as_is_value.conservative_eur}/{valuation.valuation.as_is_value.expected_eur}/{valuation.valuation.as_is_value.optimistic_eur} post_repair={valuation.valuation.post_repair_resale_value.conservative_eur}/{valuation.valuation.post_repair_resale_value.expected_eur}/{valuation.valuation.post_repair_resale_value.optimistic_eur} source={valuation.valuation.source.value} confidence={valuation.valuation.confidence:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())