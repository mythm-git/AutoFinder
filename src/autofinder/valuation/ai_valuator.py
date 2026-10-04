"""Provider-neutral temporary AI-only vehicle valuation service."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from autofinder.ai.manager import AIManager
from autofinder.ai.models import AIUsageMetadata, StructuredAIRequest, StructuredAIResult
from autofinder.analysis.models import VehicleAnalysis
from autofinder.core.exceptions import AIError, AIValuationError
from autofinder.models.normalized_listing import NormalizedListing
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.input_builder import build_ai_valuation_evidence
from autofinder.valuation.models import AIValuation
from autofinder.valuation.prompts import SYSTEM_INSTRUCTIONS, ai_valuation_user_content


@dataclass(frozen=True)
class AIValuationResult:
    valuation: AIValuation
    provider: str
    model: str
    latency_seconds: float
    usage: AIUsageMetadata | None
    fallback_used: bool
    request_id: str | None


class AIValuator:
    """Value a listing through ``AIManager`` after repair estimation is validated."""

    def __init__(self, ai_manager: AIManager) -> None:
        self._ai_manager = ai_manager
        self._logger = logging.getLogger("autofinder.valuation.ai")

    def value(self, listing: NormalizedListing, analysis: VehicleAnalysis, repair_estimate: RepairEstimate) -> AIValuationResult:
        identity = listing.identity.canonical_key
        self._logger.info("AI valuation started: listing=%s", identity)
        request = StructuredAIRequest(
            purpose="ai_vehicle_market_valuation",
            system_instructions=SYSTEM_INSTRUCTIONS,
            user_content=ai_valuation_user_content(build_ai_valuation_evidence(listing, analysis, repair_estimate)),
            response_model=AIValuation,
            max_output_tokens=1600,
        )
        try:
            result = self._ai_manager.generate_structured(request)
        except AIError as error:
            self._logger.error("AI valuation failed after AI providers: listing=%s error_type=%s", identity, type(error).__name__)
            raise AIValuationError("AI valuation did not produce a validated result.") from error
        valuation = _validated_valuation(result, repair_estimate)
        if result.fallback_used:
            self._logger.warning("AI valuation used fallback provider: listing=%s provider=%s", identity, result.provider)
        self._logger.info("AI valuation completed: listing=%s provider=%s source=%s as_is_expected_eur=%s post_repair_expected_eur=%s confidence=%.2f", identity, result.provider, valuation.source.value, valuation.as_is_value.expected_eur, valuation.post_repair_resale_value.expected_eur, valuation.confidence)
        return AIValuationResult(valuation, result.provider, result.model, result.latency_seconds, result.usage, result.fallback_used, result.request_id)


def _validated_valuation(result: StructuredAIResult, repair_estimate: RepairEstimate) -> AIValuation:
    if not isinstance(result.data, AIValuation):
        raise AIValuationError("AI manager returned an unexpected valuation model.")
    valuation = result.data
    if repair_estimate.required_repairs and valuation.post_repair_resale_value.expected_eur < valuation.as_is_value.expected_eur:
        raise AIValuationError("Post-repair expected value cannot be lower when required repairs are assumed complete.")
    return valuation
