"""Canonical AI-only vehicle market/resale valuation contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ValuationSource(StrEnum):
    AI_ESTIMATE = "AI_ESTIMATE"


class ValuationBasis(StrEnum):
    STRUCTURED_VEHICLE_FACTS = "structured_vehicle_facts"
    LISTING_EVIDENCE = "listing_evidence"
    VALIDATED_ANALYSIS = "validated_analysis"
    GENERAL_AI_MARKET_KNOWLEDGE = "general_ai_market_knowledge"


class ValueRange(BaseModel):
    """An AI estimate range, not verified comparable-market evidence."""

    model_config = ConfigDict(extra="forbid")

    conservative_eur: int = Field(ge=0)
    expected_eur: int = Field(ge=0)
    optimistic_eur: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordered_value_range(self) -> "ValueRange":
        if not self.conservative_eur <= self.expected_eur <= self.optimistic_eur:
            raise ValueError("valuation range must satisfy conservative <= expected <= optimistic")
        return self


class ValuationFactor(BaseModel):
    """A concise positive or negative market-relevant factor with evidence basis."""

    model_config = ConfigDict(extra="forbid")

    factor: str = Field(min_length=1, max_length=280)
    evidence_basis: ValuationBasis
    evidence: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0, le=1)


class AIValuation(BaseModel):
    """Temporary AI-only as-is and post-repair private-market value ranges."""

    model_config = ConfigDict(extra="forbid")

    source: ValuationSource
    as_is_value: ValueRange
    post_repair_resale_value: ValueRange
    positive_factors: tuple[ValuationFactor, ...]
    negative_factors: tuple[ValuationFactor, ...]
    uncertainties: tuple[str, ...]
    valuation_basis: tuple[ValuationBasis, ...]
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ai_source_and_basis_are_explicit(self) -> "AIValuation":
        if self.source is not ValuationSource.AI_ESTIMATE:
            raise ValueError("Step 8 valuation source must be AI_ESTIMATE")
        if not self.valuation_basis:
            raise ValueError("valuation must declare its evidence basis")
        return self