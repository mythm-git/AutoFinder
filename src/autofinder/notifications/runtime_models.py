"""Typed, provider-independent runtime-reporting inputs."""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuntimeRunStatus(StrEnum):
    """Outcome of one future AutoFinder runtime attempt."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class RuntimeRunSummary(BaseModel):
    """Safe aggregate counts emitted by a future orchestrated run."""

    model_config = ConfigDict(extra="forbid")

    status: RuntimeRunStatus
    listings_collected: int = Field(ge=0)
    invalid_identity_count: int = Field(ge=0)
    previously_seen_count: int = Field(ge=0)
    same_batch_duplicate_count: int = Field(ge=0)
    new_listings_count: int = Field(ge=0)
    normalization_success_count: int = Field(ge=0)
    normalization_failure_count: int = Field(ge=0)
    basic_filter_passed_count: int = Field(ge=0)
    basic_filter_rejected_count: int = Field(ge=0)
    ai_analysis_attempted_count: int = Field(ge=0)
    ai_analysis_failed_count: int = Field(ge=0)
    deals_evaluated_count: int = Field(ge=0)
    rejected_deals_count: int = Field(ge=0)
    review_candidates_count: int = Field(ge=0)
    strong_candidates_count: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def _verify_aggregate_relationships(self) -> "RuntimeRunSummary":
        if not math.isfinite(self.duration_seconds):
            raise ValueError("runtime duration must be finite")
        if self.new_listings_count > self.listings_collected:
            raise ValueError("new listing count cannot exceed collected listings")
        if self.normalization_success_count + self.normalization_failure_count > self.new_listings_count:
            raise ValueError("normalization counts cannot exceed new listings")
        if self.basic_filter_passed_count + self.basic_filter_rejected_count > self.normalization_success_count:
            raise ValueError("filter counts cannot exceed normalized listings")
        if self.ai_analysis_failed_count > self.ai_analysis_attempted_count:
            raise ValueError("AI analysis failures cannot exceed attempts")
        if self.deals_evaluated_count > self.ai_analysis_attempted_count:
            raise ValueError("deals evaluated cannot exceed AI analysis attempts")
        if self.rejected_deals_count + self.review_candidates_count + self.strong_candidates_count > self.deals_evaluated_count:
            raise ValueError("deal decision counts cannot exceed deals evaluated")
        return self
