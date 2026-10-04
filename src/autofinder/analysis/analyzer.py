"""Provider-independent structured vehicle/listing analysis orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from autofinder.ai.manager import AIManager
from autofinder.ai.models import AIUsageMetadata, StructuredAIRequest, StructuredAIResult
from autofinder.analysis.input_builder import build_vehicle_analysis_evidence
from autofinder.analysis.models import RiskCategory, StructuredVehicleFacts, VehicleAnalysis
from autofinder.analysis.prompts import SYSTEM_INSTRUCTIONS, vehicle_analysis_user_content
from autofinder.core.exceptions import AIError, VehicleAnalysisError
from autofinder.models.normalized_listing import NormalizedListing


@dataclass(frozen=True)
class VehicleAnalysisResult:
    """Validated analysis plus safe provider metadata selected by ``AIManager``."""

    analysis: VehicleAnalysis
    provider: str
    model: str
    latency_seconds: float
    usage: AIUsageMetadata | None
    fallback_used: bool
    request_id: str | None


class VehicleAnalyzer:
    """Analyze one already-filtered normalized listing through ``AIManager`` only."""

    def __init__(self, ai_manager: AIManager) -> None:
        self._ai_manager = ai_manager
        self._logger = logging.getLogger("autofinder.analysis.vehicle")

    def analyze(self, listing: NormalizedListing) -> VehicleAnalysisResult:
        """Build deterministic evidence and obtain a canonical validated analysis."""
        identity = listing.identity.canonical_key
        self._logger.info("Vehicle analysis started: listing=%s", identity)
        evidence = build_vehicle_analysis_evidence(listing)
        request = StructuredAIRequest(
            purpose="vehicle_listing_analysis",
            system_instructions=SYSTEM_INSTRUCTIONS,
            user_content=vehicle_analysis_user_content(evidence),
            response_model=VehicleAnalysis,
            max_output_tokens=1800,
        )
        try:
            result = self._ai_manager.generate_structured(request)
        except AIError as error:
            self._logger.error("Vehicle analysis failed after AI providers: listing=%s error_type=%s", identity, type(error).__name__)
            raise VehicleAnalysisError("Vehicle analysis did not produce a validated result.") from error
        analysis = _validated_analysis(result, listing)
        if result.fallback_used:
            self._logger.warning("Vehicle analysis used fallback provider: listing=%s provider=%s", identity, result.provider)
        if len(analysis.missing_information) >= 5:
            self._logger.warning("Vehicle analysis has limited listing information: listing=%s missing_count=%s", identity, len(analysis.missing_information))
        if any(flag.category is RiskCategory.CONTRADICTORY_INFORMATION for flag in analysis.risk_flags):
            self._logger.warning("Vehicle analysis identified contradiction: listing=%s", identity)
        self._logger.info("Vehicle analysis succeeded: listing=%s provider=%s risk_level=%s confidence=%.2f", identity, result.provider, analysis.risk_level.value, analysis.analysis_confidence)
        return VehicleAnalysisResult(analysis, result.provider, result.model, result.latency_seconds, result.usage, result.fallback_used, result.request_id)


def _validated_analysis(result: StructuredAIResult, listing: NormalizedListing) -> VehicleAnalysis:
    """Ensure the provider response is the canonical model and preserves source facts."""
    if not isinstance(result.data, VehicleAnalysis):
        raise VehicleAnalysisError("AI manager returned an unexpected analysis model.")
    expected = StructuredVehicleFacts(
        make=listing.vehicle.make,
        model=listing.vehicle.model,
        mileage_km=listing.vehicle.mileage_km,
        power_ps=listing.vehicle.power_ps,
    )
    if result.data.vehicle.structured_source != expected:
        raise VehicleAnalysisError("Vehicle analysis attempted to alter canonical structured source facts.")
    return result.data
