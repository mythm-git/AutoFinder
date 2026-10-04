"""Fixture-only tests for Step 8 repair estimation and AI-only valuation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from autofinder.ai.models import StructuredAIRequest, StructuredAIResult
from autofinder.analysis.models import VehicleAnalysis
from autofinder.core.exceptions import AIAllProvidersFailed, AIValuationError, RepairEstimationError
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer
from autofinder.repair.estimator import RepairEstimator
from autofinder.repair.input_builder import build_repair_estimation_evidence
from autofinder.repair.models import RepairEstimate, RepairItemType
from autofinder.valuation.ai_valuator import AIValuator
from autofinder.valuation.input_builder import build_ai_valuation_evidence
from autofinder.valuation.models import AIValuation


RAW_FIXTURE = Path(__file__).parents[1] / "fixtures" / "apify_kleinanzeigen_dataset.json"


class FakeManager:
    """In-memory AIManager double that cannot make a network request."""

    def __init__(self, outcome, provider: str = "groq", fallback_used: bool = False) -> None:
        self.outcome = outcome
        self.provider = provider
        self.fallback_used = fallback_used
        self.requests: list[StructuredAIRequest] = []

    def generate_structured(self, request: StructuredAIRequest) -> StructuredAIResult:
        self.requests.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return StructuredAIResult(self.outcome, self.provider, f"{self.provider}-model", 0.01, None, self.fallback_used, (), "safe-request", "stop")


def _listing():
    payload = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))[0]
    payload["apiKey"] = "must-not-reach-step8"
    return ApifyKleinanzeigenNormalizer().normalize(RawMarketplaceListing("kleinanzeigen", payload, datetime.now(UTC))).listing


def _analysis(listing, *, faults: list[dict] | None = None, repairs: list[dict] | None = None, maintenance: list[dict] | None = None, missing: list[dict] | None = None) -> VehicleAnalysis:
    return VehicleAnalysis.model_validate({
        "vehicle": {"structured_source": {"make": listing.vehicle.make, "model": listing.vehicle.model, "mileage_km": listing.vehicle.mileage_km, "power_ps": listing.vehicle.power_ps}, "interpreted_from_listing": {"make": None, "model": None, "variant": None, "registration_year": None, "engine": None, "fuel_type": None, "transmission": None, "power_kw": None, "engine_cc": None, "tuv_until": None, "accident_free": None}},
        "current_faults": faults or [], "completed_repairs": repairs or [], "maintenance_history": maintenance or [], "seller_claims": [], "positive_signals": [], "risk_flags": [], "missing_information": missing or [],
        "condition_summary": "Sanitized evidence has documented limits.", "overall_condition": "average", "risk_level": "medium", "analysis_confidence": 0.6,
    })


def _item(item_type: str, component: str, costs: tuple[int, int, int] = (100, 200, 300)) -> dict:
    return {"item_type": item_type, "component": component, "description": f"{component} work", "evidence_basis": "validated_analysis", "evidence": "Validated upstream evidence", "minimum_eur": costs[0], "expected_eur": costs[1], "high_eur": costs[2], "work_complexity": "moderate_workshop", "confidence": 0.7, "assumption_note": None}


def _estimate(required: list[dict] | None = None, near: list[dict] | None = None, reserve: list[dict] | None = None, confidence: float = 0.6) -> RepairEstimate:
    required, near, reserve = required or [], near or [], reserve or []
    items = required + near + reserve
    return RepairEstimate.model_validate({"required_repairs": required, "near_term_maintenance": near, "uncertainty_items": reserve, "cost_summary": {"minimum_total_eur": sum(item["minimum_eur"] for item in items), "expected_total_eur": sum(item["expected_eur"] for item in items), "high_total_eur": sum(item["high_eur"] for item in items), "includes_uncertainty_reserve": bool(reserve)}, "confidence": confidence})


def _valuation(as_is: tuple[int, int, int] = (1800, 2200, 2600), post: tuple[int, int, int] = (2400, 2800, 3200), confidence: float = 0.55) -> AIValuation:
    return AIValuation.model_validate({"source": "AI_ESTIMATE", "as_is_value": {"conservative_eur": as_is[0], "expected_eur": as_is[1], "optimistic_eur": as_is[2]}, "post_repair_resale_value": {"conservative_eur": post[0], "expected_eur": post[1], "optimistic_eur": post[2]}, "positive_factors": [], "negative_factors": [], "uncertainties": ["Registration year is unknown."], "valuation_basis": ["structured_vehicle_facts", "validated_analysis", "general_ai_market_knowledge"], "confidence": confidence})


def test_repair_evidence_boundary_uses_validated_analysis_and_preserves_raw_source() -> None:
    listing = _listing(); analysis = _analysis(listing)
    before = deepcopy(listing.source.raw_data)
    evidence = build_repair_estimation_evidence(listing, analysis)
    assert evidence["normalized_vehicle_facts"]["mileage_km"] == listing.vehicle.mileage_km  # type: ignore[index]
    assert "must-not-reach-step8" not in json.dumps(evidence)
    assert listing.source.raw_data == before


def test_current_fault_becomes_required_repair_but_completed_repairs_are_not_charged() -> None:
    listing = _listing()
    analysis = _analysis(listing, faults=[{"component": "clutch", "issue": "slips", "severity": "high", "evidence": "Clutch slips", "confidence": 0.9}], repairs=[{"component": "front brakes", "repair": "replaced", "mileage_km": None, "date_or_timeframe": "recently", "evidence": "New brakes", "confidence": 0.9}, {"component": "battery", "repair": "replaced", "mileage_km": None, "date_or_timeframe": "recently", "evidence": "New battery", "confidence": 0.9}])
    estimate = _estimate(required=[_item("required_repair", "clutch", (400, 650, 1000))])
    result = RepairEstimator(FakeManager(estimate)).estimate(listing, analysis)
    assert [item.component for item in result.estimate.required_repairs] == ["clutch"]
    assert all(item.component not in {"front brakes", "battery"} for item in result.estimate.required_repairs)


def test_maintenance_and_missing_information_stay_separate_from_definite_repairs() -> None:
    listing = _listing()
    analysis = _analysis(listing, maintenance=[{"service": "oil service documented", "mileage_km": None, "date_or_timeframe": None, "evidence": "Service documented", "confidence": 0.8}], missing=[{"topic": "tuv", "reason": "No TÜV date stated."}])
    estimate = _estimate(near=[_item("near_term_maintenance", "oil service", (80, 120, 180))], reserve=[_item("uncertainty_reserve", "unknown TÜV", (0, 100, 300))], confidence=0.45)
    result = RepairEstimator(FakeManager(estimate)).estimate(listing, analysis).estimate
    assert not result.required_repairs
    assert result.near_term_maintenance[0].item_type is RepairItemType.NEAR_TERM_MAINTENANCE
    assert result.uncertainty_items[0].item_type is RepairItemType.UNCERTAINTY_RESERVE
    assert result.cost_summary.includes_uncertainty_reserve and result.confidence == 0.45


def test_repair_ranges_totals_and_invalid_contracts_are_rejected() -> None:
    estimate = _estimate(required=[_item("required_repair", "clutch", (400, 650, 1000))], reserve=[_item("uncertainty_reserve", "unknown history", (0, 100, 300))])
    assert estimate.cost_summary.expected_total_eur == 750
    broken = estimate.model_dump(); broken["cost_summary"]["expected_total_eur"] = 999
    with pytest.raises(ValidationError): RepairEstimate.model_validate(broken)
    broken_item = _item("required_repair", "bad", (400, 100, 300))
    with pytest.raises(ValidationError): _estimate(required=[broken_item])
    negative = _item("required_repair", "bad", (-1, 1, 2))
    with pytest.raises(ValidationError): _estimate(required=[negative])


@pytest.mark.parametrize("provider", ["groq", "gemini"])
def test_repair_service_is_provider_neutral_and_preserves_fallback_metadata(provider: str) -> None:
    listing = _listing(); analysis = _analysis(listing); estimate = _estimate()
    result = RepairEstimator(FakeManager(estimate, provider, provider == "gemini")).estimate(listing, analysis)
    assert result.provider == provider and result.fallback_used is (provider == "gemini")


def test_repair_failure_propagates_safely_and_contract_has_no_valuation_fields() -> None:
    listing = _listing(); analysis = _analysis(listing)
    with pytest.raises(RepairEstimationError): RepairEstimator(FakeManager(AIAllProvidersFailed("safe"))).estimate(listing, analysis)
    schema = json.dumps(RepairEstimate.model_json_schema()).lower()
    for forbidden in ("market_value", "resale_value", "profit", "roi", "comparable"): assert forbidden not in schema


def test_valuation_receives_repair_estimate_and_does_not_anchor_to_listing_price() -> None:
    listing = _listing(); analysis = _analysis(listing); repair = _estimate(required=[_item("required_repair", "clutch")])
    valuation = _valuation()
    manager = FakeManager(valuation)
    result = AIValuator(manager).value(listing, analysis, repair)
    assert result.valuation.source.value == "AI_ESTIMATE"
    assert result.valuation.as_is_value.expected_eur != listing.price_eur
    assert "validated_repair_estimate" in manager.requests[0].user_content


def test_valuation_ranges_source_confidence_and_post_repair_relationship_validate() -> None:
    listing = _listing(); analysis = _analysis(listing); repair = _estimate(required=[_item("required_repair", "clutch")])
    with pytest.raises(ValidationError): _valuation(as_is=(2600, 2200, 2800))
    invalid = _valuation().model_dump(); invalid["as_is_value"]["expected_eur"] = -1
    with pytest.raises(ValidationError): AIValuation.model_validate(invalid)
    with pytest.raises(AIValuationError): AIValuator(FakeManager(_valuation(as_is=(2400, 2600, 2800), post=(1800, 2200, 2500)))).value(listing, analysis, repair)


def test_valuation_contract_has_no_fake_comparables_profit_or_roi_and_failure_is_safe() -> None:
    listing = _listing(); analysis = _analysis(listing); repair = _estimate()
    with pytest.raises(AIValuationError): AIValuator(FakeManager(AIAllProvidersFailed("safe"))).value(listing, analysis, repair)
    properties = AIValuation.model_json_schema()["properties"]
    for forbidden in ("comparables", "profit", "roi", "candidate", "repair_total", "listing_url"):
        assert forbidden not in properties


def test_step8_services_do_not_bypass_ai_manager_or_log_sensitive_description(caplog: pytest.LogCaptureFixture) -> None:
    for implementation in (RepairEstimator, AIValuator):
        source = inspect.getsource(implementation)
        assert "GroqProvider" not in source and "GeminiProvider" not in source
    listing = _listing(); listing.source.raw_data["description"] = "secret-text"
    analysis = _analysis(listing); repair = _estimate()
    RepairEstimator(FakeManager(repair)).estimate(listing, analysis)
    AIValuator(FakeManager(_valuation())).value(listing, analysis, repair)
    assert "secret-text" not in caplog.text


def test_valuation_evidence_and_step7_analysis_remain_immutable() -> None:
    listing = _listing(); analysis = _analysis(listing); repair = _estimate()
    before = (deepcopy(listing.source.raw_data), analysis.model_dump())
    evidence = build_ai_valuation_evidence(listing, analysis, repair)
    assert evidence["validated_vehicle_analysis"]["vehicle"]["structured_source"]["mileage_km"] == listing.vehicle.mileage_km  # type: ignore[index]
    assert (listing.source.raw_data, analysis.model_dump()) == before
