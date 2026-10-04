"""Fixture-only tests for structured vehicle/listing analysis."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from autofinder.ai.models import StructuredAIRequest, StructuredAIResult
from autofinder.analysis.analyzer import VehicleAnalyzer
from autofinder.analysis.input_builder import build_vehicle_analysis_evidence
from autofinder.analysis.models import VehicleAnalysis
from autofinder.core.exceptions import AIAllProvidersFailed, VehicleAnalysisError
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer


RAW_FIXTURE = Path(__file__).parents[1] / "fixtures" / "apify_kleinanzeigen_dataset.json"
CASES_FIXTURE = Path(__file__).parents[1] / "fixtures" / "vehicle_analysis_cases.json"


class FakeManager:
    """In-memory manager double; it cannot issue a provider request."""

    def __init__(self, outcome: VehicleAnalysis | Exception, provider: str = "groq", fallback_used: bool = False) -> None:
        self.outcome = outcome
        self.provider = provider
        self.fallback_used = fallback_used
        self.requests: list[StructuredAIRequest] = []

    def generate_structured(self, request: StructuredAIRequest) -> StructuredAIResult:
        self.requests.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return StructuredAIResult(self.outcome, self.provider, f"{self.provider}-model", 0.01, None, self.fallback_used, (), "safe-request", "stop")


def _listing(title: str = "Sanitized compact", description: str = "Documented service."):
    payload = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))[0]
    payload["title"] = title
    payload["description"] = description
    payload["unrelatedMetadata"] = {"token": "must-not-reach-ai"}
    payload["apiKey"] = "must-not-reach-ai"
    payload["vehicle"]["registrationYear"] = 2010
    return ApifyKleinanzeigenNormalizer().normalize(RawMarketplaceListing("kleinanzeigen", payload, datetime.now(UTC))).listing


def _payload(listing, **overrides: object) -> dict[str, object]:
    vehicle = {
        "structured_source": {"make": listing.vehicle.make, "model": listing.vehicle.model, "mileage_km": listing.vehicle.mileage_km, "power_ps": listing.vehicle.power_ps},
        "interpreted_from_listing": {"make": None, "model": None, "variant": None, "registration_year": None, "engine": None, "fuel_type": None, "transmission": None, "power_kw": None, "engine_cc": None, "tuv_until": None, "accident_free": None},
    }
    payload: dict[str, object] = {
        "vehicle": vehicle,
        "current_faults": [],
        "completed_repairs": [],
        "maintenance_history": [],
        "seller_claims": [],
        "positive_signals": [],
        "risk_flags": [],
        "missing_information": [],
        "condition_summary": "Listing evidence is limited but internally consistent.",
        "overall_condition": "unknown",
        "risk_level": "unknown",
        "analysis_confidence": 0.5,
    }
    payload.update(overrides)
    return payload


def _analysis(listing, **overrides: object) -> VehicleAnalysis:
    return VehicleAnalysis.model_validate(_payload(listing, **overrides))


def test_input_builder_uses_canonical_facts_and_excludes_irrelevant_raw_data() -> None:
    listing = _listing()
    raw_before = deepcopy(listing.source.raw_data)
    evidence = build_vehicle_analysis_evidence(listing)
    assert evidence["structured_source"]["vehicle"]["mileage_km"] == listing.vehicle.mileage_km  # type: ignore[index]
    assert evidence["structured_source"]["seller_type"] == "private"  # type: ignore[index]
    assert evidence["selected_raw_vehicle_attributes"]["vehicle"]["registrationYear"] == 2010  # type: ignore[index]
    serialized = json.dumps(evidence)
    assert "must-not-reach-ai" not in serialized
    assert "image" not in serialized.lower()
    assert listing.source.raw_data == raw_before


@pytest.mark.parametrize("case", json.loads(CASES_FIXTURE.read_text(encoding="utf-8")), ids=lambda item: item["name"])
def test_sanitized_analysis_fixtures_remain_listing_specific(case: dict[str, str]) -> None:
    listing = _listing(case["title"], case["description"])
    evidence = build_vehicle_analysis_evidence(listing)
    assert evidence["listing_text"]["description"] == case["description"]  # type: ignore[index]
    assert evidence["structured_source"]["vehicle"]["mileage_km"] == listing.vehicle.mileage_km  # type: ignore[index]


def test_analyzer_uses_manager_and_preserves_structured_source_values() -> None:
    listing = _listing()
    manager = FakeManager(_analysis(listing))
    result = VehicleAnalyzer(manager).analyze(listing)
    assert result.analysis.vehicle.structured_source.mileage_km == listing.vehicle.mileage_km
    assert manager.requests[0].response_model is VehicleAnalysis
    assert manager.requests[0].purpose == "vehicle_listing_analysis"
    assert "repair cost" in manager.requests[0].system_instructions.lower()


def test_text_interpretation_is_separate_and_unknown_accident_tuv_are_permitted() -> None:
    listing = _listing()
    payload = _payload(listing)
    payload["vehicle"]["interpreted_from_listing"]["make"] = "Example"  # type: ignore[index]
    payload["vehicle"]["interpreted_from_listing"]["variant"] = "Comfort"  # type: ignore[index]
    analysis = VehicleAnalysis.model_validate(payload)
    assert analysis.vehicle.structured_source.make == listing.vehicle.make
    assert analysis.vehicle.interpreted_from_listing.accident_free is None
    assert analysis.vehicle.interpreted_from_listing.tuv_until is None


def test_semantic_categories_and_controlled_risk_condition_validate() -> None:
    listing = _listing()
    analysis = _analysis(
        listing,
        current_faults=[{"component": "clutch", "issue": "slips under load", "severity": "high", "evidence": "Clutch slips under load", "confidence": 0.9}],
        completed_repairs=[{"component": "front brakes", "repair": "replaced", "mileage_km": None, "date_or_timeframe": "recently", "evidence": "Front brakes new", "confidence": 0.9}],
        maintenance_history=[{"service": "timing belt replaced", "mileage_km": 95000, "date_or_timeframe": None, "evidence": "Timing belt at 95,000 km", "confidence": 0.9}],
        seller_claims=[{"claim": "technically perfect", "evidence": "Technically perfect", "confidence": 0.8}],
        missing_information=[{"topic": "tuv", "reason": "No TÜV date is stated."}],
        risk_flags=[{"category": "stated_mechanical_fault", "explanation": "Unresolved clutch issue.", "evidence": "Clutch slips", "confidence": 0.9}],
        overall_condition="poor",
        risk_level="high",
        analysis_confidence=0.95,
    )
    assert analysis.current_faults[0].component == "clutch"
    assert analysis.completed_repairs[0].component == "front brakes"
    assert analysis.seller_claims[0].claim == "technically perfect"


@pytest.mark.parametrize("provider", ["groq", "gemini"])
def test_same_vehicle_analysis_model_is_provider_neutral(provider: str) -> None:
    listing = _listing()
    result = VehicleAnalyzer(FakeManager(_analysis(listing), provider=provider, fallback_used=provider == "gemini")).analyze(listing)
    assert result.provider == provider
    assert result.fallback_used is (provider == "gemini")


def test_invalid_analysis_contracts_are_rejected() -> None:
    listing = _listing()
    for changes in ({"analysis_confidence": 1.1}, {"risk_level": "unbounded"}, {"risk_level": "high", "risk_flags": []}):
        with pytest.raises(ValidationError):
            VehicleAnalysis.model_validate(_payload(listing, **changes))
    invalid = _payload(listing)
    invalid.pop("missing_information")
    with pytest.raises(ValidationError):
        VehicleAnalysis.model_validate(invalid)


def test_analyzer_rejects_silent_structured_source_overwrite_and_propagates_failure() -> None:
    listing = _listing()
    altered = _payload(listing)
    altered["vehicle"]["structured_source"]["mileage_km"] = 120000  # type: ignore[index]
    with pytest.raises(VehicleAnalysisError, match="alter canonical"):
        VehicleAnalyzer(FakeManager(VehicleAnalysis.model_validate(altered))).analyze(listing)
    with pytest.raises(VehicleAnalysisError, match="did not produce"):
        VehicleAnalyzer(FakeManager(AIAllProvidersFailed("safe"))).analyze(listing)


def test_analysis_contains_no_monetary_or_roi_contract_fields_and_logs_are_safe(caplog: pytest.LogCaptureFixture) -> None:
    listing = _listing(description="secret-listing-description")
    VehicleAnalyzer(FakeManager(_analysis(listing))).analyze(listing)
    schema = VehicleAnalysis.model_json_schema()
    serialized = json.dumps(schema).lower()
    for forbidden in ("repair_cost", "market_value", "resale_value", "profit", "roi", "labor_cost", "parts_cost"):
        assert forbidden not in serialized
    assert "secret-listing-description" not in caplog.text
