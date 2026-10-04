"""Deterministic Step 9 financial-engine tests with no external dependencies."""

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

from autofinder.core.exceptions import FinancialAnalysisError
from autofinder.financial import FinancialCalculator, FinancialScenarioName
from autofinder.financial.calculator import _scenario
from autofinder.financial.models import FinancialScenario
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.models import AIValuation


RAW_FIXTURE = Path(__file__).parents[1] / "fixtures" / "apify_kleinanzeigen_dataset.json"


def _listing():
    payload = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))[0]
    return ApifyKleinanzeigenNormalizer().normalize(
        RawMarketplaceListing("kleinanzeigen", payload, datetime.now(UTC))
    ).listing


def _estimate(*, totals: tuple[int, int, int] = (120, 190, 290)) -> RepairEstimate:
    item = {
        "item_type": "uncertainty_reserve",
        "component": "documented uncertainty",
        "description": "Bounded Step 8 uncertainty reserve",
        "evidence_basis": "validated_analysis",
        "evidence": "Validated Step 7 missing-information evidence",
        "minimum_eur": totals[0],
        "expected_eur": totals[1],
        "high_eur": totals[2],
        "work_complexity": "unknown",
        "confidence": 0.5,
        "assumption_note": "No definite repair is invented.",
    }
    return RepairEstimate.model_validate(
        {
            "required_repairs": [],
            "near_term_maintenance": [],
            "uncertainty_items": [item],
            "cost_summary": {
                "minimum_total_eur": totals[0],
                "expected_total_eur": totals[1],
                "high_total_eur": totals[2],
                "includes_uncertainty_reserve": True,
            },
            "confidence": 0.5,
        }
    )


def _valuation(
    *,
    as_is: tuple[int, int, int] = (1500, 2000, 2500),
    post_repair: tuple[int, int, int] = (2000, 2600, 3200),
) -> AIValuation:
    return AIValuation.model_validate(
        {
            "source": "AI_ESTIMATE",
            "as_is_value": {
                "conservative_eur": as_is[0],
                "expected_eur": as_is[1],
                "optimistic_eur": as_is[2],
            },
            "post_repair_resale_value": {
                "conservative_eur": post_repair[0],
                "expected_eur": post_repair[1],
                "optimistic_eur": post_repair[2],
            },
            "positive_factors": [],
            "negative_factors": [],
            "uncertainties": ["Sanitized fixture uncertainty."],
            "valuation_basis": ["structured_vehicle_facts"],
            "confidence": 0.5,
        }
    )


def test_fixture_scenarios_use_the_required_repair_and_resale_members() -> None:
    analysis = FinancialCalculator().calculate(_listing(), _estimate(), _valuation())

    assert analysis.conservative.scenario is FinancialScenarioName.CONSERVATIVE
    assert analysis.conservative.repair_cost_eur == 290
    assert analysis.conservative.resale_value_eur == 2000
    assert analysis.expected.scenario is FinancialScenarioName.EXPECTED
    assert analysis.expected.repair_cost_eur == 190
    assert analysis.expected.resale_value_eur == 2600
    assert analysis.optimistic.scenario is FinancialScenarioName.OPTIMISTIC
    assert analysis.optimistic.repair_cost_eur == 120
    assert analysis.optimistic.resale_value_eur == 3200


def test_step8_representative_fixture_calculates_traceable_scenarios() -> None:
    analysis = FinancialCalculator().calculate(_listing(), _estimate(), _valuation())

    assert analysis.conservative.model_dump() == {
        "scenario": "conservative",
        "purchase_price_eur": 2450,
        "repair_cost_eur": 290,
        "additional_costs_eur": 0,
        "total_investment_eur": 2740,
        "resale_value_eur": 2000,
        "expected_profit_eur": -740,
        "roi_percent": Decimal("-27.01"),
    }
    assert analysis.expected.total_investment_eur == 2640
    assert analysis.expected.expected_profit_eur == -40
    assert analysis.expected.roi_percent == Decimal("-1.52")
    assert analysis.optimistic.total_investment_eur == 2570
    assert analysis.optimistic.expected_profit_eur == 630
    assert analysis.optimistic.roi_percent == Decimal("24.51")


def test_roi_uses_full_investment_not_purchase_price() -> None:
    expected = FinancialCalculator().calculate(_listing(), _estimate(), _valuation()).expected
    assert expected.roi_percent == Decimal("-1.52")
    assert expected.roi_percent != Decimal(expected.expected_profit_eur) / Decimal(expected.purchase_price_eur) * 100


def test_negative_profit_and_negative_roi_remain_visible() -> None:
    conservative = FinancialCalculator().calculate(_listing(), _estimate(), _valuation()).conservative
    assert conservative.expected_profit_eur == -740
    assert conservative.roi_percent == Decimal("-27.01")


def test_zero_repair_and_zero_default_additional_costs_are_supported() -> None:
    zero = _estimate(totals=(0, 0, 0))
    analysis = FinancialCalculator().calculate(_listing(), zero, _valuation())
    assert analysis.expected.repair_cost_eur == 0
    assert analysis.expected.additional_costs_eur == 0
    assert analysis.expected.total_investment_eur == 2450


def test_explicit_future_additional_cost_is_included_without_hidden_costs() -> None:
    analysis = FinancialCalculator(additional_costs_eur=50).calculate(_listing(), _estimate(), _valuation())
    assert analysis.expected.additional_costs_eur == 50
    assert analysis.expected.total_investment_eur == 2690
    assert analysis.expected.expected_profit_eur == -90


@pytest.mark.parametrize("price", [None, 0, -1, 1.5])
def test_invalid_purchase_price_is_rejected(price: float | None) -> None:
    with pytest.raises(FinancialAnalysisError):
        FinancialCalculator().calculate(replace(_listing(), price_eur=price), _estimate(), _valuation())


def test_negative_additional_cost_and_zero_investment_are_rejected() -> None:
    with pytest.raises(FinancialAnalysisError):
        FinancialCalculator(additional_costs_eur=-1)
    with pytest.raises(FinancialAnalysisError):
        _scenario(FinancialScenarioName.EXPECTED, 0, 0, 0, 0)


def test_defensive_rejection_of_invalid_upstream_ranges() -> None:
    repair = _estimate().model_copy(
        update={"cost_summary": _estimate().cost_summary.model_copy(update={"minimum_total_eur": -1})}
    )
    with pytest.raises(FinancialAnalysisError):
        FinancialCalculator().calculate(_listing(), repair, _valuation())

    valuation = _valuation().model_copy(
        update={
            "post_repair_resale_value": _valuation().post_repair_resale_value.model_copy(
                update={"conservative_eur": -1}
            )
        }
    )
    with pytest.raises(FinancialAnalysisError):
        FinancialCalculator().calculate(_listing(), _estimate(), valuation)


def test_financial_scenario_rejects_inconsistent_arithmetic() -> None:
    with pytest.raises(ValidationError):
        FinancialScenario.model_validate(
            {
                "scenario": "expected",
                "purchase_price_eur": 1000,
                "repair_cost_eur": 100,
                "additional_costs_eur": 0,
                "total_investment_eur": 1000,
                "resale_value_eur": 1500,
                "expected_profit_eur": 500,
                "roi_percent": "50.00",
            }
        )


def test_roi_rounds_once_to_two_decimal_places_half_up() -> None:
    listing = replace(_listing(), price_eur=1300)
    result = FinancialCalculator().calculate(listing, _estimate(totals=(0, 0, 0)), _valuation(post_repair=(1800, 1800, 1800)))
    assert result.expected.roi_percent == Decimal("38.46")


def test_as_is_value_is_carried_for_reference_but_not_used_for_roi() -> None:
    result = FinancialCalculator().calculate(
        _listing(), _estimate(), _valuation(as_is=(9000, 9500, 10000))
    )
    assert result.as_is_value_reference.expected_eur == 9500
    assert result.expected.resale_value_eur == 2600


def test_inputs_are_unchanged_and_logging_excludes_raw_source(caplog: pytest.LogCaptureFixture) -> None:
    listing, repair, valuation = _listing(), _estimate(), _valuation()
    listing.source.raw_data["description"] = "financial-secret-text"
    before = (deepcopy(listing.source.raw_data), repair.model_dump(), valuation.model_dump())

    FinancialCalculator().calculate(listing, repair, valuation)

    assert (listing.source.raw_data, repair.model_dump(), valuation.model_dump()) == before
    assert "financial-secret-text" not in caplog.text


def test_financial_calculator_has_no_provider_network_or_decision_dependencies() -> None:
    source = inspect.getsource(FinancialCalculator)
    for forbidden in ("AIManager", "GroqProvider", "GeminiProvider", "requests", "http"):
        assert forbidden not in source.lower() if forbidden == "http" else forbidden not in source
    properties = __import__("autofinder.financial.models", fromlist=["FinancialAnalysis"]).FinancialAnalysis.model_json_schema()["properties"]
    for forbidden in ("candidate", "decision", "threshold", "profit_target", "roi_minimum"):
        assert forbidden not in properties
