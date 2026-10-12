"""Fixture-only Step 11 runtime Telegram reporting tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
import inspect
import json
from pathlib import Path
from urllib.request import Request

import pytest
from pydantic import ValidationError

from autofinder.analysis.models import VehicleAnalysis
from autofinder.core.config import load_config
from autofinder.deals.models import DealDecision, DealEvaluation
from autofinder.financial.models import FinancialAnalysis, FinancialScenario
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer
from autofinder.notifications.development_reporter import DevelopmentReport, DevelopmentReporter
from autofinder.notifications.runtime_models import RuntimeRunStatus, RuntimeRunSummary
from autofinder.notifications.runtime_reporter import TELEGRAM_TEXT_LIMIT, RuntimeReporter, _bound_message, reason_text
from autofinder.notifications.telegram import TelegramClient, TelegramSettings
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.models import AIValuation


PROJECT_ROOT = Path(__file__).parents[2]
RAW_FIXTURE = Path(__file__).parents[1] / "fixtures" / "apify_kleinanzeigen_dataset.json"


def _config(**changes):
    return replace(load_config(PROJECT_ROOT / "config" / "autofinder.yaml").telegram, **changes)


def _listing():
    payload = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))[0]
    return ApifyKleinanzeigenNormalizer().normalize(
        RawMarketplaceListing("kleinanzeigen", payload, datetime.now(UTC))
    ).listing


def _analysis() -> VehicleAnalysis:
    return VehicleAnalysis.model_validate({
        "vehicle": {"structured_source": {"make": "Volkswagen", "model": "Golf", "mileage_km": 174000, "power_ps": 100}, "interpreted_from_listing": {"make": None, "model": None, "variant": "1.6", "registration_year": 2008, "engine": None, "fuel_type": "petrol", "transmission": "manual", "power_kw": None, "engine_cc": None, "tuv_until": None, "accident_free": None}},
        "current_faults": [{"component": "air conditioning", "issue": "not working", "severity": "medium", "evidence": "Sanitized", "confidence": 0.9}],
        "completed_repairs": [{"component": "front brakes", "repair": "recently replaced", "mileage_km": None, "date_or_timeframe": "recently", "evidence": "Sanitized", "confidence": 0.9}],
        "maintenance_history": [{"service": "oil service documented", "mileage_km": None, "date_or_timeframe": None, "evidence": "Sanitized", "confidence": 0.8}],
        "seller_claims": [], "positive_signals": [],
        "risk_flags": [{"category": "limited_information", "explanation": "Service history is incomplete.", "evidence": "Sanitized", "confidence": 0.8}],
        "missing_information": [{"topic": "tuv", "reason": "Not stated."}],
        "condition_summary": "Sanitized fixture.", "overall_condition": "good", "risk_level": "medium", "analysis_confidence": 0.9,
    })


def _repair() -> RepairEstimate:
    item = {"item_type": "uncertainty_reserve", "component": "history", "description": "bounded uncertainty", "evidence_basis": "validated_analysis", "evidence": "Sanitized", "minimum_eur": 120, "expected_eur": 190, "high_eur": 290, "work_complexity": "unknown", "confidence": 0.6, "assumption_note": None}
    return RepairEstimate.model_validate({"required_repairs": [], "near_term_maintenance": [], "uncertainty_items": [item], "cost_summary": {"minimum_total_eur": 120, "expected_total_eur": 190, "high_total_eur": 290, "includes_uncertainty_reserve": True}, "confidence": 0.6})


def _valuation() -> AIValuation:
    return AIValuation.model_validate({"source": "AI_ESTIMATE", "as_is_value": {"conservative_eur": 1500, "expected_eur": 2000, "optimistic_eur": 2400}, "post_repair_resale_value": {"conservative_eur": 2200, "expected_eur": 2600, "optimistic_eur": 3200}, "positive_factors": [], "negative_factors": [], "uncertainties": [], "valuation_basis": ["structured_vehicle_facts"], "confidence": 0.7})


def _scenario(name: str, purchase: int, repair: int, resale: int) -> FinancialScenario:
    investment = purchase + repair
    profit = resale - investment
    return FinancialScenario(scenario=name, purchase_price_eur=purchase, repair_cost_eur=repair, additional_costs_eur=0, total_investment_eur=investment, resale_value_eur=resale, expected_profit_eur=profit, roi_percent=(Decimal(profit) / Decimal(investment) * 100).quantize(Decimal("0.01")))


def _financial() -> FinancialAnalysis:
    return FinancialAnalysis(
        conservative=_scenario("conservative", 1850, 290, 2070),
        expected=_scenario("expected", 1850, 190, 2600),
        optimistic=_scenario("optimistic", 1850, 120, 2950),
        valuation_source="AI_ESTIMATE", as_is_value_reference={"conservative_eur": 1500, "expected_eur": 2000, "optimistic_eur": 2400},
    )


def _evaluation(*, decision: str = "review") -> DealEvaluation:
    return DealEvaluation.model_validate({
        "decision": decision, "financially_eligible": True, "reasons": [],
        "warnings": ["conservative_roi_negative", "repair_uncertainty_present", "valuation_ai_only"],
        "expected_roi_percent": "27.45", "conservative_roi_percent": "-3.27", "optimistic_roi_percent": "49.75",
        "expected_profit_eur": 560, "expected_total_investment_eur": 2040,
        "vehicle_risk_level": "medium", "analysis_confidence": 0.9, "repair_confidence": 0.6,
        "valuation_confidence": 0.7, "valuation_source": "AI_ESTIMATE", "rules_version": "v0.1",
    })


def _summary(*, status: str = "success", new: int = 3, passed: int = 2) -> RuntimeRunSummary:
    return RuntimeRunSummary(
        status=status, listings_collected=5, invalid_identity_count=0, previously_seen_count=2,
        same_batch_duplicate_count=0, new_listings_count=new, normalization_success_count=new,
        normalization_failure_count=0, basic_filter_passed_count=passed, basic_filter_rejected_count=new - passed,
        ai_analysis_attempted_count=passed, ai_analysis_failed_count=0, deals_evaluated_count=passed,
        rejected_deals_count=1 if passed else 0, review_candidates_count=1 if passed else 0,
        strong_candidates_count=0, duration_seconds=12.8,
    )


def test_zero_new_summary_is_successful_noop_without_ai_or_candidate_counts() -> None:
    text = RuntimeReporter.format_summary(_summary(new=0, passed=0))
    assert "AutoFinder Run" in text and "✅ SUCCESS" in text
    assert "Analyzed: 0" in text and "Candidates: 0" in text
    assert "AUTOFINDER DEAL FOUND" not in text and "STRONG DEAL" not in text


def test_filtered_out_normal_partial_and_failed_summaries_render_safely() -> None:
    filtered = RuntimeReporter.format_summary(_summary(new=3, passed=0))
    normal = RuntimeReporter.format_summary(_summary())
    partial = RuntimeReporter.format_summary(_summary(status="partial_success"))
    failed = RuntimeReporter.format_summary(_summary(status="failed", new=0, passed=0))
    assert "New: 3" in filtered and "Candidates: 0" in filtered
    assert "Analyzed: 2" in normal and "Evaluated: 2" in normal
    assert "⚠️ PARTIAL_SUCCESS" in partial and "❌ FAILED" in failed
    assert "Next run: ~45 min" in normal


def test_runtime_summary_validates_counts_and_duration() -> None:
    with pytest.raises(ValidationError):
        RuntimeRunSummary.model_validate({**_summary().model_dump(), "new_listings_count": 6})
    with pytest.raises(ValidationError):
        RuntimeRunSummary.model_validate({**_summary().model_dump(), "duration_seconds": float("inf")})


def test_review_and_strong_candidates_include_upstream_values_without_recalculation() -> None:
    review = RuntimeReporter.format_candidate(_listing(), _analysis(), _repair(), _valuation(), _financial(), _evaluation(), 4)
    strong = RuntimeReporter.format_candidate(_listing(), _analysis(), _repair(), _valuation(), _financial(), _evaluation(decision="strong_candidate"), 4)
    assert review is not None and "AUTOFINDER DEAL FOUND" in review and "⭐ DECISION: REVIEW" in review
    assert "FINANCIALS" in review and "Purchase        €1,850" in review and "Expected profit +€560" in review
    assert "Estimated repairs:" in review and "€120 – €190 – €290" in review
    assert "⚠️ WATCH OUT" in review and "Confidence:" in review
    assert _listing().url in review
    assert strong is not None and strong.startswith("🚨 STRONG DEAL 🚨") and "AUTOFINDER HIGH-PRIORITY FIND" in strong
    assert "✅ STRONG_CANDIDATE" in strong and "CHECK THIS CAR NOW" in strong
    for label in ("PRICE:", "EXPECTED ROI:", "EXPECTED PROFIT:"):
        assert review.index(label) < review.index("FINANCIALS")


def test_rejected_deal_never_formats_or_sends_candidate_alert() -> None:
    captured: list[Request] = []
    client = TelegramClient(TelegramSettings("fake-token", "1"), transport=lambda request, timeout: captured.append(request))
    reporter = RuntimeReporter(client, _config())
    reject = _evaluation().model_copy(update={"decision": DealDecision.REJECT, "financially_eligible": False, "reasons": ("expected_roi_below_minimum",), "warnings": ()})
    assert RuntimeReporter.format_candidate(_listing(), _analysis(), _repair(), _valuation(), _financial(), reject) is None
    assert not reporter.send_candidate(_listing(), _analysis(), _repair(), _valuation(), _financial(), reject)
    assert not captured


def test_candidate_watch_out_uses_validated_missing_information_and_risks() -> None:
    text = RuntimeReporter.format_candidate(_listing(), _analysis(), _repair(), _valuation(), _financial(), _evaluation(), 5)
    assert text is not None
    assert "Service history is incomplete." in text
    assert "Missing: tuv" in text


def test_candidate_rendering_handles_missing_optional_listing_fields() -> None:
    listing = replace(_listing(), url=None, location=replace(_listing().location, city=None, postal_code=None, raw_text=None))
    text = RuntimeReporter.format_candidate(listing, _analysis(), _repair(), _valuation(), _financial(), _evaluation())
    assert text is not None
    assert "Location unavailable" in text and "Listing URL unavailable." in text


def test_reason_mapping_unknown_codes_bounded_lists_and_message_length() -> None:
    assert reason_text("conservative_roi_negative") == "Conservative scenario is still loss-making."
    assert "unknown_future_code" in reason_text("unknown_future_code")
    repair = _repair().model_copy(update={"uncertainty_items": _repair().uncertainty_items * 30})
    listing = replace(_listing(), title="*[]<>_& " * 200, url=None)
    text = RuntimeReporter.format_candidate(listing, _analysis(), repair, _valuation(), _financial(), _evaluation(), 2)
    assert text is not None and "+28 more" in text and "Listing URL unavailable." in text
    assert len(text) <= TELEGRAM_TEXT_LIMIT
    title_listing = replace(_listing(), title="x" * 500, vehicle=replace(_listing().vehicle, make=None, model=None))
    bare_analysis = _analysis().model_copy(update={"vehicle": _analysis().vehicle.model_copy(update={"interpreted_from_listing": _analysis().vehicle.interpreted_from_listing.model_copy(update={"variant": None})})})
    title_text = RuntimeReporter.format_candidate(title_listing, bare_analysis, _repair(), _valuation(), _financial(), _evaluation())
    assert title_text is not None and ("x" * 119) in title_text and "…" in title_text
    assert len(_bound_message("x" * (TELEGRAM_TEXT_LIMIT + 100))) == TELEGRAM_TEXT_LIMIT
    assert _bound_message("x" * (TELEGRAM_TEXT_LIMIT + 100)).endswith("… [message truncated]")


def test_plain_text_transport_needs_no_markdown_escaping_or_parse_mode() -> None:
    captured: list[Request] = []
    client = TelegramClient(TelegramSettings("fake-token", "1"), transport=lambda request, timeout: captured.append(request))
    reporter = RuntimeReporter(client, _config())
    listing = replace(_listing(), title="[*] <vehicle> & _text_")
    assert reporter.send_candidate(listing, _analysis(), _repair(), _valuation(), _financial(), _evaluation())
    payload = json.loads(captured[0].data.decode("utf-8"))
    assert "parse_mode" not in payload and "Verify car physically before buying" in payload["text"]


def test_summary_and_candidate_delivery_respect_configuration_and_keep_inputs_immutable(caplog: pytest.LogCaptureFixture) -> None:
    captured: list[Request] = []
    client = TelegramClient(TelegramSettings("secret-token", "1"), transport=lambda request, timeout: captured.append(request))
    disabled = RuntimeReporter(client, _config(runtime_summary_enabled=False, candidate_alerts_enabled=False))
    assert not disabled.send_summary(_summary())
    assert not disabled.send_candidate(_listing(), _analysis(), _repair(), _valuation(), _financial(), _evaluation())
    listing, analysis, repair, valuation, financial, evaluation = _listing(), _analysis(), _repair(), _valuation(), _financial(), _evaluation()
    listing.source.raw_data["description"] = "runtime-secret-text"
    before = (deepcopy(listing.source.raw_data), analysis.model_dump(), repair.model_dump(), valuation.model_dump(), financial.model_dump(), evaluation.model_dump())
    reporter = RuntimeReporter(client, _config())
    assert reporter.send_summary(_summary())
    assert reporter.send_candidate(listing, analysis, repair, valuation, financial, evaluation)
    assert (listing.source.raw_data, analysis.model_dump(), repair.model_dump(), valuation.model_dump(), financial.model_dump(), evaluation.model_dump()) == before
    assert "secret-token" not in caplog.text and "runtime-secret-text" not in caplog.text


def test_runtime_reporter_has_no_ai_network_or_business_calculation_dependency() -> None:
    source = inspect.getsource(RuntimeReporter)
    for forbidden in ("AIManager", "GroqProvider", "GeminiProvider", "FinancialCalculator", "DealEvaluator", "requests"):
        assert forbidden not in source
    development = DevelopmentReporter.format(DevelopmentReport("Step", "✅", ("Existing report",), 1, 0, "abc", "Next"))
    assert "AutoFinder Development" in development
