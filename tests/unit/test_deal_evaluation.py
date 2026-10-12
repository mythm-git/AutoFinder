"""Fixture-only tests for deterministic Step 10 deal evaluation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
import inspect
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from autofinder.analysis.models import RiskLevel, VehicleAnalysis
from autofinder.core.config import DealEvaluationConfig, load_config
from autofinder.core.exceptions import DealEvaluationError
from autofinder.deals import DealDecision, DealEvaluationCode, DealEvaluator
from autofinder.deals.models import DealEvaluation
from autofinder.financial import FinancialScenarioName
from autofinder.financial.models import FinancialAnalysis, FinancialScenario
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.models import AIValuation


PROJECT_ROOT = Path(__file__).parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "autofinder.yaml"
RAW_FIXTURE = Path(__file__).parents[1] / "fixtures" / "apify_kleinanzeigen_dataset.json"


def _listing():
    payload = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))[0]
    return ApifyKleinanzeigenNormalizer().normalize(
        RawMarketplaceListing("kleinanzeigen", payload, datetime.now(UTC))
    ).listing


def _analysis(*, risk: str = "medium", confidence: float = 0.85, missing: bool = False) -> VehicleAnalysis:
    flags = [] if risk not in {"high", "very_high"} else [{
        "category": "limited_information",
        "explanation": "Evidence-backed risk.",
        "evidence": "Sanitized fixture evidence.",
        "confidence": 0.8,
    }]
    return VehicleAnalysis.model_validate({
        "vehicle": {
            "structured_source": {"make": "Volkswagen", "model": "Golf", "mileage_km": 150000, "power_ps": 100},
            "interpreted_from_listing": {
                "make": None, "model": None, "variant": None, "registration_year": None, "engine": None,
                "fuel_type": None, "transmission": None, "power_kw": None, "engine_cc": None,
                "tuv_until": None, "accident_free": None,
            },
        },
        "current_faults": [], "completed_repairs": [], "maintenance_history": [], "seller_claims": [],
        "positive_signals": [], "risk_flags": flags,
        "missing_information": [{"topic": "tuv", "reason": "Not stated."}] if missing else [],
        "condition_summary": "Sanitized deterministic input.", "overall_condition": "average",
        "risk_level": risk, "analysis_confidence": confidence,
    })


def _repair(*, confidence: float = 0.75, uncertainty: bool = False) -> RepairEstimate:
    items = [] if not uncertainty else [{
        "item_type": "uncertainty_reserve", "component": "unknown history",
        "description": "Bounded uncertainty", "evidence_basis": "validated_analysis",
        "evidence": "Sanitized fixture evidence", "minimum_eur": 0, "expected_eur": 50, "high_eur": 100,
        "work_complexity": "unknown", "confidence": 0.5, "assumption_note": None,
    }]
    return RepairEstimate.model_validate({
        "required_repairs": [], "near_term_maintenance": [], "uncertainty_items": items,
        "cost_summary": {
            "minimum_total_eur": 0, "expected_total_eur": 50 if uncertainty else 0,
            "high_total_eur": 100 if uncertainty else 0, "includes_uncertainty_reserve": uncertainty,
        }, "confidence": confidence,
    })


def _valuation(*, confidence: float = 0.78) -> AIValuation:
    return AIValuation.model_validate({
        "source": "AI_ESTIMATE",
        "as_is_value": {"conservative_eur": 1000, "expected_eur": 1200, "optimistic_eur": 1400},
        "post_repair_resale_value": {"conservative_eur": 1200, "expected_eur": 1400, "optimistic_eur": 1600},
        "positive_factors": [], "negative_factors": [], "uncertainties": [],
        "valuation_basis": ["structured_vehicle_facts"], "confidence": confidence,
    })


def _scenario(name: FinancialScenarioName, roi: int) -> FinancialScenario:
    investment = 1000
    profit = roi * 10
    return FinancialScenario(
        scenario=name, purchase_price_eur=1000, repair_cost_eur=0, additional_costs_eur=0,
        total_investment_eur=investment, resale_value_eur=investment + profit,
        expected_profit_eur=profit, roi_percent=Decimal(str(roi)),
    )


def _financial(*, conservative: int = 8, expected: int = 31, optimistic: int = 55) -> FinancialAnalysis:
    return FinancialAnalysis(
        conservative=_scenario(FinancialScenarioName.CONSERVATIVE, conservative),
        expected=_scenario(FinancialScenarioName.EXPECTED, expected),
        optimistic=_scenario(FinancialScenarioName.OPTIMISTIC, optimistic),
        valuation_source="AI_ESTIMATE",
        as_is_value_reference={"conservative_eur": 1000, "expected_eur": 1200, "optimistic_eur": 1400},
    )


def _config(**changes) -> DealEvaluationConfig:
    return replace(load_config(CONFIG_PATH).deal_evaluation, **changes)


def _evaluate(*, financial: FinancialAnalysis | None = None, risk: str = "medium", analysis_confidence: float = 0.85, repair_confidence: float = 0.75, valuation_confidence: float = 0.78, config: DealEvaluationConfig | None = None, uncertainty: bool = False, missing: bool = False):
    return DealEvaluator(config or _config()).evaluate(
        _listing(), _analysis(risk=risk, confidence=analysis_confidence, missing=missing),
        _repair(confidence=repair_confidence, uncertainty=uncertainty), _valuation(confidence=valuation_confidence),
        financial or _financial(),
    )


def test_current_step9_fixture_rejects_for_both_expected_financial_gates() -> None:
    financial = FinancialAnalysis(
        conservative=FinancialScenario(scenario="conservative", purchase_price_eur=2450, repair_cost_eur=290, additional_costs_eur=0, total_investment_eur=2740, resale_value_eur=2000, expected_profit_eur=-740, roi_percent=Decimal("-27.01")),
        expected=FinancialScenario(scenario="expected", purchase_price_eur=2450, repair_cost_eur=190, additional_costs_eur=0, total_investment_eur=2640, resale_value_eur=2600, expected_profit_eur=-40, roi_percent=Decimal("-1.52")),
        optimistic=FinancialScenario(scenario="optimistic", purchase_price_eur=2450, repair_cost_eur=120, additional_costs_eur=0, total_investment_eur=2570, resale_value_eur=3200, expected_profit_eur=630, roi_percent=Decimal("24.51")),
        valuation_source="AI_ESTIMATE",
        as_is_value_reference={"conservative_eur": 1500, "expected_eur": 2000, "optimistic_eur": 2500},
    )
    result = _evaluate(financial=financial)
    assert result.decision is DealDecision.REJECT
    assert result.reasons == (
        DealEvaluationCode.EXPECTED_PROFIT_NON_POSITIVE,
        DealEvaluationCode.EXPECTED_ROI_BELOW_MINIMUM,
    )


@pytest.mark.parametrize(("roi", "eligible"), [
    (Decimal("16.99"), False), (Decimal("17.00"), True), (Decimal("17.01"), True),
    (Decimal("19.05"), True), (Decimal("20.00"), True),
])
def test_expected_roi_gate_uses_configured_seventeen_percent_boundary(roi: Decimal, eligible: bool) -> None:
    financial = _financial(conservative=0, expected=17, optimistic=80)
    financial = financial.model_copy(update={"expected": financial.expected.model_copy(update={"roi_percent": roi, "expected_profit_eur": 170})})
    result = _evaluate(financial=financial)
    assert result.financially_eligible is eligible
    assert (DealEvaluationCode.EXPECTED_ROI_BELOW_MINIMUM in result.reasons) is not eligible


def test_optimistic_roi_never_rescues_failing_expected_roi() -> None:
    result = _evaluate(financial=_financial(conservative=0, expected=16, optimistic=80))
    assert result.decision is DealDecision.REJECT
    assert DealEvaluationCode.EXPECTED_ROI_BELOW_MINIMUM in result.reasons


def test_expected_roi_at_threshold_and_conservative_threshold_can_be_strong() -> None:
    result = _evaluate(financial=_financial(conservative=0, expected=17, optimistic=55))
    assert result.financially_eligible
    assert result.decision is DealDecision.STRONG_CANDIDATE
    assert DealEvaluationCode.CONSERVATIVE_SCENARIO_POSITIVE in result.warnings


def test_negative_conservative_roi_with_good_expected_roi_requires_review() -> None:
    result = _evaluate(financial=_financial(conservative=-4, expected=32, optimistic=61))
    assert result.decision is DealDecision.REVIEW
    assert DealEvaluationCode.CONSERVATIVE_ROI_NEGATIVE in result.warnings


@pytest.mark.parametrize(
    ("risk", "expected_decision"),
    [("low", DealDecision.STRONG_CANDIDATE), ("medium", DealDecision.STRONG_CANDIDATE), ("high", DealDecision.REVIEW), ("unknown", DealDecision.REVIEW)],
)
def test_risk_controls_are_deterministic(risk: str, expected_decision: DealDecision) -> None:
    result = _evaluate(risk=risk)
    assert result.decision is expected_decision


def test_very_high_risk_is_a_configurable_hard_reject() -> None:
    result = _evaluate(risk="very_high")
    assert result.decision is DealDecision.REJECT
    assert result.reasons == (DealEvaluationCode.VEHICLE_RISK_VERY_HIGH,)

    relaxed = _evaluate(risk="very_high", config=_config(reject_very_high_risk=False))
    assert relaxed.decision is DealDecision.REVIEW
    assert DealEvaluationCode.VEHICLE_RISK_VERY_HIGH in relaxed.warnings


@pytest.mark.parametrize(
    ("keyword", "kwargs"),
    [
        (DealEvaluationCode.ANALYSIS_CONFIDENCE_LOW, {"analysis_confidence": 0.59}),
        (DealEvaluationCode.REPAIR_CONFIDENCE_LOW, {"repair_confidence": 0.54}),
        (DealEvaluationCode.VALUATION_CONFIDENCE_LOW, {"valuation_confidence": 0.59}),
    ],
)
def test_low_confidence_prevents_strong_but_does_not_reject(keyword: DealEvaluationCode, kwargs: dict) -> None:
    result = _evaluate(**kwargs)
    assert result.decision is DealDecision.REVIEW
    assert keyword in result.warnings


def test_confidence_exactly_at_threshold_passes_strong_requirements() -> None:
    result = _evaluate(analysis_confidence=0.60, repair_confidence=0.55, valuation_confidence=0.60)
    assert result.decision is DealDecision.STRONG_CANDIDATE


def test_ai_estimate_is_preserved_as_context_not_a_rejection() -> None:
    result = _evaluate()
    assert result.decision is DealDecision.STRONG_CANDIDATE
    assert DealEvaluationCode.VALUATION_AI_ONLY in result.warnings
    assert result.valuation_source.value == "AI_ESTIMATE"


def test_uncertainty_and_missing_information_are_warnings_not_count_based_rejections() -> None:
    result = _evaluate(uncertainty=True, missing=True)
    assert result.decision is DealDecision.STRONG_CANDIDATE
    assert DealEvaluationCode.REPAIR_UNCERTAINTY_PRESENT in result.warnings
    assert DealEvaluationCode.LISTING_INFORMATION_INCOMPLETE in result.warnings


def test_configuration_changes_roi_confidence_and_maximum_risk_behavior() -> None:
    assert _evaluate(financial=_financial(expected=22), config=_config(minimum_expected_roi_percent=Decimal("25"))).decision is DealDecision.REJECT
    assert _evaluate(config=_config(minimum_analysis_confidence=0.9)).decision is DealDecision.REVIEW
    assert _evaluate(risk="medium", config=_config(maximum_risk_for_strong=RiskLevel.LOW)).decision is DealDecision.REVIEW


def test_programmatic_invalid_policy_fails_with_a_clear_domain_error() -> None:
    with pytest.raises(DealEvaluationError, match="Maximum risk"):
        DealEvaluator(_config(maximum_risk_for_strong=RiskLevel.HIGH))


def test_configuration_validation_rejects_invalid_confidence_and_risk(tmp_path: Path) -> None:
    config = CONFIG_PATH.read_text(encoding="utf-8")
    invalid_confidence = tmp_path / "bad-confidence.yaml"
    invalid_confidence.write_text(config.replace("minimum_analysis_confidence: 0.60", "minimum_analysis_confidence: 1.1"), encoding="utf-8")
    with pytest.raises(Exception, match="minimum_analysis_confidence"):
        load_config(invalid_confidence)
    invalid_risk = tmp_path / "bad-risk.yaml"
    invalid_risk.write_text(config.replace('maximum_risk_for_strong: "medium"', 'maximum_risk_for_strong: "high"'), encoding="utf-8")
    with pytest.raises(Exception, match="maximum_risk_for_strong"):
        load_config(invalid_risk)


def test_result_contract_requires_stable_nonoverlapping_codes() -> None:
    result = _evaluate()
    payload = result.model_dump()
    payload["decision"] = "reject"
    payload["reasons"] = ["expected_roi_below_minimum"]
    payload["warnings"] = [*payload["warnings"], "expected_roi_below_minimum"]
    with pytest.raises(ValidationError):
        DealEvaluation.model_validate(payload)


def test_upstream_inputs_remain_immutable_and_safe_logging_avoids_description(caplog: pytest.LogCaptureFixture) -> None:
    listing, analysis, repair, valuation, financial = _listing(), _analysis(), _repair(), _valuation(), _financial()
    listing.source.raw_data["description"] = "decision-secret-text"
    before = (deepcopy(listing.source.raw_data), analysis.model_dump(), repair.model_dump(), valuation.model_dump(), financial.model_dump())
    DealEvaluator(_config()).evaluate(listing, analysis, repair, valuation, financial)
    assert (listing.source.raw_data, analysis.model_dump(), repair.model_dump(), valuation.model_dump(), financial.model_dump()) == before
    assert "decision-secret-text" not in caplog.text


def test_evaluator_has_no_ai_network_or_hidden_weighted_score_dependency() -> None:
    source = inspect.getsource(DealEvaluator)
    for forbidden in ("AIManager", "GroqProvider", "GeminiProvider", "requests", "http", "*"):
        assert forbidden not in source
    assert "score" not in DealEvaluation.model_json_schema()["properties"]
