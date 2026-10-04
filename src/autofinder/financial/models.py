"""Canonical deterministic financial scenario models."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from autofinder.valuation.models import ValuationSource, ValueRange


ROI_QUANTUM = Decimal("0.01")


class FinancialScenarioName(StrEnum):
    CONSERVATIVE = "conservative"
    EXPECTED = "expected"
    OPTIMISTIC = "optimistic"


class FinancialScenario(BaseModel):
    """Traceable, local arithmetic for one fixed repair/resale pairing."""

    model_config = ConfigDict(extra="forbid")

    scenario: FinancialScenarioName
    purchase_price_eur: int = Field(gt=0)
    repair_cost_eur: int = Field(ge=0)
    additional_costs_eur: int = Field(ge=0)
    total_investment_eur: int = Field(gt=0)
    resale_value_eur: int = Field(ge=0)
    expected_profit_eur: int
    roi_percent: Decimal

    @model_validator(mode="after")
    def _verify_deterministic_arithmetic(self) -> "FinancialScenario":
        investment = self.purchase_price_eur + self.repair_cost_eur + self.additional_costs_eur
        if self.total_investment_eur != investment:
            raise ValueError("total investment must equal purchase + repair + additional costs")
        profit = self.resale_value_eur - investment
        if self.expected_profit_eur != profit:
            raise ValueError("expected profit must equal resale value - total investment")
        expected_roi = (Decimal(profit) / Decimal(investment) * Decimal("100")).quantize(ROI_QUANTUM, rounding=ROUND_HALF_UP)
        if self.roi_percent != expected_roi:
            raise ValueError("ROI must equal profit / total investment * 100 rounded to two decimals")
        return self


class FinancialAnalysis(BaseModel):
    """Three deterministic post-repair resale scenarios; not a deal decision."""

    model_config = ConfigDict(extra="forbid")

    conservative: FinancialScenario
    expected: FinancialScenario
    optimistic: FinancialScenario
    valuation_source: ValuationSource
    as_is_value_reference: ValueRange

    @model_validator(mode="after")
    def _verify_fixed_scenario_names(self) -> "FinancialAnalysis":
        expected_names = (
            (self.conservative, FinancialScenarioName.CONSERVATIVE),
            (self.expected, FinancialScenarioName.EXPECTED),
            (self.optimistic, FinancialScenarioName.OPTIMISTIC),
        )
        if any(scenario.scenario is not expected for scenario, expected in expected_names):
            raise ValueError("financial scenarios must retain their canonical names")
        return self
