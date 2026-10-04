"""Canonical evidence-grounded repair and maintenance estimation contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RepairItemType(StrEnum):
    REQUIRED_REPAIR = "required_repair"
    NEAR_TERM_MAINTENANCE = "near_term_maintenance"
    UNCERTAINTY_RESERVE = "uncertainty_reserve"


class EstimateBasis(StrEnum):
    LISTING_EVIDENCE = "listing_evidence"
    VALIDATED_ANALYSIS = "validated_analysis"
    GENERAL_AI_KNOWLEDGE = "general_ai_knowledge"


class WorkComplexity(StrEnum):
    BASIC = "basic"
    MODERATE_WORKSHOP = "moderate_workshop"
    MAJOR_SPECIALIST = "major_specialist"
    UNKNOWN = "unknown"


class RepairCostItem(BaseModel):
    """One rounded cost range, tied to disclosed evidence or explicit uncertainty."""

    model_config = ConfigDict(extra="forbid")

    item_type: RepairItemType
    component: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=280)
    evidence_basis: EstimateBasis
    evidence: str = Field(min_length=1, max_length=400)
    minimum_eur: int = Field(ge=0)
    expected_eur: int = Field(ge=0)
    high_eur: int = Field(ge=0)
    work_complexity: WorkComplexity
    confidence: float = Field(ge=0, le=1)
    assumption_note: str | None = Field(max_length=280)

    @model_validator(mode="after")
    def _ordered_cost_range(self) -> "RepairCostItem":
        if not self.minimum_eur <= self.expected_eur <= self.high_eur:
            raise ValueError("repair cost range must satisfy minimum <= expected <= high")
        return self


class RepairCostSummary(BaseModel):
    """Python-verified aggregate of all repair, maintenance, and reserve items."""

    model_config = ConfigDict(extra="forbid")

    minimum_total_eur: int = Field(ge=0)
    expected_total_eur: int = Field(ge=0)
    high_total_eur: int = Field(ge=0)
    includes_uncertainty_reserve: bool

    @model_validator(mode="after")
    def _ordered_total_range(self) -> "RepairCostSummary":
        if not self.minimum_total_eur <= self.expected_total_eur <= self.high_total_eur:
            raise ValueError("repair totals must satisfy minimum <= expected <= high")
        return self


class RepairEstimate(BaseModel):
    """Structured repair inputs with deterministic aggregate total verification."""

    model_config = ConfigDict(extra="forbid")

    required_repairs: tuple[RepairCostItem, ...]
    near_term_maintenance: tuple[RepairCostItem, ...]
    uncertainty_items: tuple[RepairCostItem, ...]
    cost_summary: RepairCostSummary
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _verify_item_types_and_totals(self) -> "RepairEstimate":
        groups = (
            (self.required_repairs, RepairItemType.REQUIRED_REPAIR),
            (self.near_term_maintenance, RepairItemType.NEAR_TERM_MAINTENANCE),
            (self.uncertainty_items, RepairItemType.UNCERTAINTY_RESERVE),
        )
        for items, expected_type in groups:
            if any(item.item_type is not expected_type for item in items):
                raise ValueError("repair item is in the wrong estimate category")
        all_items = self.required_repairs + self.near_term_maintenance + self.uncertainty_items
        expected_totals = (
            sum(item.minimum_eur for item in all_items),
            sum(item.expected_eur for item in all_items),
            sum(item.high_eur for item in all_items),
        )
        actual_totals = (self.cost_summary.minimum_total_eur, self.cost_summary.expected_total_eur, self.cost_summary.high_total_eur)
        if actual_totals != expected_totals:
            raise ValueError("repair cost_summary must equal deterministic sum of item estimates")
        if self.cost_summary.includes_uncertainty_reserve != bool(self.uncertainty_items):
            raise ValueError("uncertainty reserve flag must match uncertainty items")
        return self