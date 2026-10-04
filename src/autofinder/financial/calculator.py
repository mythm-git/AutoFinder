"""Pure local financial arithmetic over validated Step 8 monetary inputs."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import logging
import math

from autofinder.core.exceptions import FinancialAnalysisError
from autofinder.financial.models import FinancialAnalysis, FinancialScenario, FinancialScenarioName, ROI_QUANTUM
from autofinder.models.normalized_listing import NormalizedListing
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.models import AIValuation


class FinancialCalculator:
    """Calculate fixed scenario pairings; no network, AI, or deal decision logic."""

    def __init__(self, additional_costs_eur: int = 0) -> None:
        if isinstance(additional_costs_eur, bool) or not isinstance(additional_costs_eur, int) or additional_costs_eur < 0:
            raise FinancialAnalysisError("Additional deterministic costs must be a non-negative integer euro amount.")
        self._additional_costs_eur = additional_costs_eur
        self._logger = logging.getLogger("autofinder.financial.calculator")

    def calculate(self, listing: NormalizedListing, repair_estimate: RepairEstimate, valuation: AIValuation) -> FinancialAnalysis:
        """Return conservative/expected/optimistic post-repair financial scenarios."""
        purchase = _integer_euros(listing.price_eur, "purchase price")
        if purchase <= 0:
            raise FinancialAnalysisError("Purchase price must be positive for financial analysis.")
        _validate_inputs(repair_estimate, valuation)
        identity = listing.identity.canonical_key
        self._logger.info("Financial calculation started: listing=%s", identity)
        summary = repair_estimate.cost_summary
        resale = valuation.post_repair_resale_value
        analysis = FinancialAnalysis(
            conservative=_scenario(FinancialScenarioName.CONSERVATIVE, purchase, summary.high_total_eur, self._additional_costs_eur, resale.conservative_eur),
            expected=_scenario(FinancialScenarioName.EXPECTED, purchase, summary.expected_total_eur, self._additional_costs_eur, resale.expected_eur),
            optimistic=_scenario(FinancialScenarioName.OPTIMISTIC, purchase, summary.minimum_total_eur, self._additional_costs_eur, resale.optimistic_eur),
            valuation_source=valuation.source,
            as_is_value_reference=valuation.as_is_value,
        )
        self._logger.info("Financial calculation completed: listing=%s conservative_roi=%s expected_roi=%s optimistic_roi=%s", identity, analysis.conservative.roi_percent, analysis.expected.roi_percent, analysis.optimistic.roi_percent)
        return analysis


def _scenario(name: FinancialScenarioName, purchase: int, repair: int, additional: int, resale: int) -> FinancialScenario:
    """Construct one traceable scenario with one deterministic rounding policy."""
    investment = purchase + repair + additional
    if investment <= 0:
        raise FinancialAnalysisError("Total investment must be positive for ROI calculation.")
    profit = resale - investment
    roi = (Decimal(profit) / Decimal(investment) * Decimal("100")).quantize(ROI_QUANTUM, rounding=ROUND_HALF_UP)
    return FinancialScenario(scenario=name, purchase_price_eur=purchase, repair_cost_eur=repair, additional_costs_eur=additional, total_investment_eur=investment, resale_value_eur=resale, expected_profit_eur=profit, roi_percent=roi)


def _integer_euros(value: float | None, label: str) -> int:
    """Accept current normalized whole-euro values without binary-float arithmetic."""
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value:
        raise FinancialAnalysisError(f"{label.capitalize()} must be a whole-euro numeric value.")
    return int(value)


def _validate_inputs(repair_estimate: RepairEstimate, valuation: AIValuation) -> None:
    """Defend against model-constructed invalid upstream values without altering them."""
    repair = repair_estimate.cost_summary
    if min(repair.minimum_total_eur, repair.expected_total_eur, repair.high_total_eur) < 0 or not repair.minimum_total_eur <= repair.expected_total_eur <= repair.high_total_eur:
        raise FinancialAnalysisError("Repair totals must be non-negative and ordered.")
    value = valuation.post_repair_resale_value
    if min(value.conservative_eur, value.expected_eur, value.optimistic_eur) < 0 or not value.conservative_eur <= value.expected_eur <= value.optimistic_eur:
        raise FinancialAnalysisError("Post-repair resale values must be non-negative and ordered.")
