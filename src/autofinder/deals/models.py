"""Canonical deterministic Step 10 deal-evaluation contracts."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from autofinder.analysis.models import RiskLevel
from autofinder.valuation.models import ValuationSource


class DealDecision(StrEnum):
    """Decision-support states; none is an automatic purchase instruction."""

    REJECT = "reject"
    REVIEW = "review"
    STRONG_CANDIDATE = "strong_candidate"


class DealEvaluationCode(StrEnum):
    """Stable machine-readable blocking reasons and non-blocking cautions."""

    EXPECTED_PROFIT_NON_POSITIVE = "expected_profit_non_positive"
    EXPECTED_ROI_BELOW_MINIMUM = "expected_roi_below_minimum"
    VEHICLE_RISK_VERY_HIGH = "vehicle_risk_very_high"
    CONSERVATIVE_ROI_NEGATIVE = "conservative_roi_negative"
    CONSERVATIVE_ROI_BELOW_STRONG_MINIMUM = "conservative_roi_below_strong_minimum"
    VEHICLE_RISK_HIGH = "vehicle_risk_high"
    VEHICLE_RISK_UNKNOWN = "vehicle_risk_unknown"
    ANALYSIS_CONFIDENCE_LOW = "analysis_confidence_low"
    REPAIR_CONFIDENCE_LOW = "repair_confidence_low"
    VALUATION_CONFIDENCE_LOW = "valuation_confidence_low"
    REPAIR_UNCERTAINTY_PRESENT = "repair_uncertainty_present"
    LISTING_INFORMATION_INCOMPLETE = "listing_information_incomplete"
    VALUATION_AI_ONLY = "valuation_ai_only"
    CONSERVATIVE_SCENARIO_POSITIVE = "conservative_scenario_positive"


class DealEvaluation(BaseModel):
    """Explainable classification over already-validated upstream outcomes."""

    model_config = ConfigDict(extra="forbid")

    decision: DealDecision
    financially_eligible: bool
    reasons: tuple[DealEvaluationCode, ...]
    warnings: tuple[DealEvaluationCode, ...]
    expected_roi_percent: Decimal
    conservative_roi_percent: Decimal
    optimistic_roi_percent: Decimal
    expected_profit_eur: int
    expected_total_investment_eur: int = Field(gt=0)
    vehicle_risk_level: RiskLevel
    analysis_confidence: float = Field(ge=0, le=1)
    repair_confidence: float = Field(ge=0, le=1)
    valuation_confidence: float = Field(ge=0, le=1)
    valuation_source: ValuationSource
    rules_version: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _verify_explainable_categories(self) -> "DealEvaluation":
        if len(set(self.reasons)) != len(self.reasons) or len(set(self.warnings)) != len(self.warnings):
            raise ValueError("deal evaluation codes must not be duplicated")
        if set(self.reasons) & set(self.warnings):
            raise ValueError("a decision code cannot be both blocking and warning")
        if self.decision is DealDecision.REJECT and not self.reasons:
            raise ValueError("reject decisions require at least one blocking reason")
        if self.decision is not DealDecision.REJECT and self.reasons:
            raise ValueError("only reject decisions may contain blocking reasons")
        return self
