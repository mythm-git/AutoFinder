"""Pure, configurable decision-support rules over validated AutoFinder inputs."""

from __future__ import annotations

from decimal import Decimal
import logging

from autofinder.analysis.models import RiskLevel, VehicleAnalysis
from autofinder.core.config import DealEvaluationConfig
from autofinder.core.exceptions import DealEvaluationError
from autofinder.deals.models import DealDecision, DealEvaluation, DealEvaluationCode
from autofinder.financial.models import FinancialAnalysis
from autofinder.models.normalized_listing import NormalizedListing
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.models import AIValuation, ValuationSource


_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1}


class DealEvaluator:
    """Classify a deal with fixed, documented rules and no hidden score."""

    RULES_VERSION = "v0.1"

    def __init__(self, config: DealEvaluationConfig) -> None:
        _validate_policy(config)
        self._config = config
        self._logger = logging.getLogger("autofinder.deals.evaluator")

    def evaluate(
        self,
        listing: NormalizedListing,
        vehicle_analysis: VehicleAnalysis,
        repair_estimate: RepairEstimate,
        valuation: AIValuation,
        financial_analysis: FinancialAnalysis,
    ) -> DealEvaluation:
        """Return a deterministic decision-support result without mutating inputs."""
        expected = financial_analysis.expected
        conservative = financial_analysis.conservative
        optimistic = financial_analysis.optimistic
        self._logger.info("Deal evaluation started: listing=%s", listing.identity.canonical_key)

        reasons: list[DealEvaluationCode] = []
        if expected.expected_profit_eur <= 0:
            reasons.append(DealEvaluationCode.EXPECTED_PROFIT_NON_POSITIVE)
        if expected.roi_percent < self._config.minimum_expected_roi_percent:
            reasons.append(DealEvaluationCode.EXPECTED_ROI_BELOW_MINIMUM)
        financially_eligible = not reasons
        if vehicle_analysis.risk_level is RiskLevel.VERY_HIGH and self._config.reject_very_high_risk:
            reasons.append(DealEvaluationCode.VEHICLE_RISK_VERY_HIGH)

        warnings = _warnings(
            vehicle_analysis,
            repair_estimate,
            valuation,
            conservative.roi_percent,
            self._config,
        )
        if reasons:
            decision = DealDecision.REJECT
        elif _qualifies_for_strong(vehicle_analysis, repair_estimate, valuation, conservative.roi_percent, self._config):
            decision = DealDecision.STRONG_CANDIDATE
        else:
            decision = DealDecision.REVIEW

        result = DealEvaluation(
            decision=decision,
            financially_eligible=financially_eligible,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
            expected_roi_percent=expected.roi_percent,
            conservative_roi_percent=conservative.roi_percent,
            optimistic_roi_percent=optimistic.roi_percent,
            expected_profit_eur=expected.expected_profit_eur,
            expected_total_investment_eur=expected.total_investment_eur,
            vehicle_risk_level=vehicle_analysis.risk_level,
            analysis_confidence=vehicle_analysis.analysis_confidence,
            repair_confidence=repair_estimate.confidence,
            valuation_confidence=valuation.confidence,
            valuation_source=valuation.source,
            rules_version=self.RULES_VERSION,
        )
        self._logger.info(
            "Deal evaluation completed: listing=%s decision=%s expected_roi=%s conservative_roi=%s "
            "expected_profit=%s blocking_reasons=%d warnings=%d",
            listing.identity.canonical_key,
            result.decision.value,
            result.expected_roi_percent,
            result.conservative_roi_percent,
            result.expected_profit_eur,
            len(result.reasons),
            len(result.warnings),
        )
        return result


def _validate_policy(config: DealEvaluationConfig) -> None:
    """Defend service construction when callers bypass YAML loading."""
    confidences = (
        config.minimum_analysis_confidence,
        config.minimum_repair_confidence,
        config.minimum_valuation_confidence,
    )
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1 for value in confidences):
        raise DealEvaluationError("Deal-evaluation confidence thresholds must be numbers from 0.0 to 1.0.")
    if config.maximum_risk_for_strong not in _RISK_ORDER:
        raise DealEvaluationError("Maximum risk for a strong candidate must be low or medium.")
    roi_thresholds = (
        config.minimum_expected_roi_percent,
        config.minimum_conservative_roi_for_strong_percent,
    )
    if any(not isinstance(value, Decimal) or not value.is_finite() for value in roi_thresholds):
        raise DealEvaluationError("Deal-evaluation ROI thresholds must be finite Decimal values.")


def _warnings(
    vehicle_analysis: VehicleAnalysis,
    repair_estimate: RepairEstimate,
    valuation: AIValuation,
    conservative_roi: Decimal,
    config: DealEvaluationConfig,
) -> list[DealEvaluationCode]:
    """Collect factual cautions without changing their upstream interpretation."""
    warnings: list[DealEvaluationCode] = []
    if conservative_roi < config.minimum_conservative_roi_for_strong_percent:
        warnings.append(
            DealEvaluationCode.CONSERVATIVE_ROI_NEGATIVE
            if conservative_roi < 0
            else DealEvaluationCode.CONSERVATIVE_ROI_BELOW_STRONG_MINIMUM
        )
    else:
        warnings.append(DealEvaluationCode.CONSERVATIVE_SCENARIO_POSITIVE)
    risk = vehicle_analysis.risk_level
    if risk is RiskLevel.HIGH:
        warnings.append(DealEvaluationCode.VEHICLE_RISK_HIGH)
    elif risk is RiskLevel.VERY_HIGH and not config.reject_very_high_risk:
        warnings.append(DealEvaluationCode.VEHICLE_RISK_VERY_HIGH)
    elif risk is RiskLevel.UNKNOWN:
        warnings.append(DealEvaluationCode.VEHICLE_RISK_UNKNOWN)
    if vehicle_analysis.analysis_confidence < config.minimum_analysis_confidence:
        warnings.append(DealEvaluationCode.ANALYSIS_CONFIDENCE_LOW)
    if repair_estimate.confidence < config.minimum_repair_confidence:
        warnings.append(DealEvaluationCode.REPAIR_CONFIDENCE_LOW)
    if valuation.confidence < config.minimum_valuation_confidence:
        warnings.append(DealEvaluationCode.VALUATION_CONFIDENCE_LOW)
    if repair_estimate.uncertainty_items:
        warnings.append(DealEvaluationCode.REPAIR_UNCERTAINTY_PRESENT)
    if vehicle_analysis.missing_information:
        warnings.append(DealEvaluationCode.LISTING_INFORMATION_INCOMPLETE)
    if valuation.source is ValuationSource.AI_ESTIMATE:
        warnings.append(DealEvaluationCode.VALUATION_AI_ONLY)
    return warnings


def _qualifies_for_strong(
    vehicle_analysis: VehicleAnalysis,
    repair_estimate: RepairEstimate,
    valuation: AIValuation,
    conservative_roi: Decimal,
    config: DealEvaluationConfig,
) -> bool:
    """Require every explicit strong-candidate criterion; never average confidence."""
    risk = vehicle_analysis.risk_level
    return (
        conservative_roi >= config.minimum_conservative_roi_for_strong_percent
        and risk in _RISK_ORDER
        and _RISK_ORDER[risk] <= _RISK_ORDER[config.maximum_risk_for_strong]
        and vehicle_analysis.analysis_confidence >= config.minimum_analysis_confidence
        and repair_estimate.confidence >= config.minimum_repair_confidence
        and valuation.confidence >= config.minimum_valuation_confidence
    )
