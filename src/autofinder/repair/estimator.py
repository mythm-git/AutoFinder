"""Provider-neutral repair estimation built on validated vehicle analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from autofinder.ai.manager import AIManager
from autofinder.ai.models import AIUsageMetadata, StructuredAIRequest, StructuredAIResult
from autofinder.analysis.models import VehicleAnalysis
from autofinder.core.exceptions import AIError, RepairEstimationError
from autofinder.models.normalized_listing import NormalizedListing
from autofinder.repair.input_builder import build_repair_estimation_evidence
from autofinder.repair.models import RepairEstimate
from autofinder.repair.prompts import SYSTEM_INSTRUCTIONS, repair_estimation_user_content


@dataclass(frozen=True)
class RepairEstimationResult:
    estimate: RepairEstimate
    provider: str
    model: str
    latency_seconds: float
    usage: AIUsageMetadata | None
    fallback_used: bool
    request_id: str | None


class RepairEstimator:
    """Estimate repair inputs through ``AIManager`` without valuation dependency."""

    def __init__(self, ai_manager: AIManager) -> None:
        self._ai_manager = ai_manager
        self._logger = logging.getLogger("autofinder.repair.estimator")

    def estimate(self, listing: NormalizedListing, analysis: VehicleAnalysis) -> RepairEstimationResult:
        identity = listing.identity.canonical_key
        self._logger.info("Repair estimation started: listing=%s", identity)
        request = StructuredAIRequest(
            purpose="repair_maintenance_estimation",
            system_instructions=SYSTEM_INSTRUCTIONS,
            user_content=repair_estimation_user_content(build_repair_estimation_evidence(listing, analysis)),
            response_model=RepairEstimate,
            max_output_tokens=1800,
        )
        try:
            result = self._ai_manager.generate_structured(request)
        except AIError as error:
            self._logger.error("Repair estimation failed after AI providers: listing=%s error_type=%s", identity, type(error).__name__)
            raise RepairEstimationError("Repair estimation did not produce a validated result.") from error
        estimate = _validated_estimate(result)
        if result.fallback_used:
            self._logger.warning("Repair estimation used fallback provider: listing=%s provider=%s", identity, result.provider)
        self._logger.info("Repair estimation completed: listing=%s provider=%s expected_total_eur=%s confidence=%.2f", identity, result.provider, estimate.cost_summary.expected_total_eur, estimate.confidence)
        return RepairEstimationResult(estimate, result.provider, result.model, result.latency_seconds, result.usage, result.fallback_used, result.request_id)


def _validated_estimate(result: StructuredAIResult) -> RepairEstimate:
    if not isinstance(result.data, RepairEstimate):
        raise RepairEstimationError("AI manager returned an unexpected repair estimate model.")
    return result.data
