"""Canonical, provider-neutral structured vehicle-listing analysis models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConditionLevel(StrEnum):
    """Listing-evidence condition category, never a valuation."""

    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    VERY_POOR = "very_poor"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    """Evidence-based listing risk category."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    UNKNOWN = "unknown"


class FaultSeverity(StrEnum):
    """Reported fault severity inferred only from listing evidence."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class RiskCategory(StrEnum):
    """Controlled classes for evidence-based listing risks."""

    CONTRADICTORY_INFORMATION = "contradictory_information"
    WARNING_LIGHT = "warning_light"
    STATED_MECHANICAL_FAULT = "stated_mechanical_fault"
    RUST = "rust"
    FLUID_LEAK = "fluid_leak"
    ELECTRICAL_ISSUE = "electrical_issue"
    OVERHEATING = "overheating"
    MECHANICAL_NOISE = "mechanical_noise"
    SELLER_ACKNOWLEDGED_DEFECT = "seller_acknowledged_defect"
    LIMITED_INFORMATION = "limited_information"
    MISSING_MAINTENANCE_HISTORY = "missing_maintenance_history"
    OTHER_LISTING_EVIDENCE = "other_listing_evidence"


class MissingInformationTopic(StrEnum):
    """Important listing facts that may be relevant yet absent."""

    ACCIDENT_HISTORY = "accident_history"
    TUV = "tuv"
    SERVICE_HISTORY = "service_history"
    TIMING_BELT_HISTORY = "timing_belt_history"
    OWNER_COUNT = "owner_count"
    AIR_CONDITIONING = "air_conditioning"
    WARNING_LIGHTS = "warning_lights"
    RECENT_MAINTENANCE = "recent_maintenance"
    REGISTRATION_YEAR = "registration_year"
    ENGINE = "engine"
    TRANSMISSION = "transmission"
    FUEL_TYPE = "fuel_type"
    CONDITION_DETAILS = "condition_details"
    OTHER_RELEVANT_DETAIL = "other_relevant_detail"


class StructuredVehicleFacts(BaseModel):
    """Canonical normalized facts that the analyzer must reproduce exactly."""

    model_config = ConfigDict(extra="forbid")

    make: str | None
    model: str | None
    mileage_km: float | None
    power_ps: float | None


class TextSupportedVehicleFacts(BaseModel):
    """Facts interpreted only from explicit title/description evidence."""

    model_config = ConfigDict(extra="forbid")

    make: str | None
    model: str | None
    variant: str | None
    registration_year: int | None
    engine: str | None
    fuel_type: str | None
    transmission: str | None
    power_kw: float | None
    engine_cc: int | None
    tuv_until: str | None
    accident_free: bool | None


class VehicleIdentityAnalysis(BaseModel):
    """Keep structured source facts distinct from text-supported interpretation."""

    model_config = ConfigDict(extra="forbid")

    structured_source: StructuredVehicleFacts
    interpreted_from_listing: TextSupportedVehicleFacts


class CurrentFault(BaseModel):
    """An unresolved issue explicitly supported by listing evidence."""

    model_config = ConfigDict(extra="forbid")

    component: str = Field(min_length=1, max_length=120)
    issue: str = Field(min_length=1, max_length=280)
    severity: FaultSeverity
    evidence: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0, le=1)


class CompletedRepair(BaseModel):
    """Work stated as completed, never treated as a present fault."""

    model_config = ConfigDict(extra="forbid")

    component: str = Field(min_length=1, max_length=120)
    repair: str = Field(min_length=1, max_length=280)
    mileage_km: float | None = Field(ge=0)
    date_or_timeframe: str | None = Field(max_length=100)
    evidence: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0, le=1)


class MaintenanceRecord(BaseModel):
    """Routine or scheduled servicing stated by the listing."""

    model_config = ConfigDict(extra="forbid")

    service: str = Field(min_length=1, max_length=280)
    mileage_km: float | None = Field(ge=0)
    date_or_timeframe: str | None = Field(max_length=100)
    evidence: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0, le=1)


class SellerClaim(BaseModel):
    """A seller statement, explicitly not a verified vehicle fact."""

    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, max_length=280)
    evidence: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0, le=1)


class PositiveSignal(BaseModel):
    """A restrained evidence-backed positive signal."""

    model_config = ConfigDict(extra="forbid")

    signal: str = Field(min_length=1, max_length=280)
    evidence: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0, le=1)


class RiskFlag(BaseModel):
    """A risk with its short listing-evidence explanation."""

    model_config = ConfigDict(extra="forbid")

    category: RiskCategory
    explanation: str = Field(min_length=1, max_length=280)
    evidence: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0, le=1)


class MissingInformation(BaseModel):
    """A concise, listing-specific unknown relevant to condition assessment."""

    model_config = ConfigDict(extra="forbid")

    topic: MissingInformationTopic
    reason: str = Field(min_length=1, max_length=240)


class VehicleAnalysis(BaseModel):
    """Validated listing-specific condition and uncertainty analysis; no money logic."""

    model_config = ConfigDict(extra="forbid")

    vehicle: VehicleIdentityAnalysis
    current_faults: tuple[CurrentFault, ...]
    completed_repairs: tuple[CompletedRepair, ...]
    maintenance_history: tuple[MaintenanceRecord, ...]
    seller_claims: tuple[SellerClaim, ...]
    positive_signals: tuple[PositiveSignal, ...]
    risk_flags: tuple[RiskFlag, ...]
    missing_information: tuple[MissingInformation, ...]
    condition_summary: str = Field(min_length=1, max_length=420)
    overall_condition: ConditionLevel
    risk_level: RiskLevel
    analysis_confidence: float = Field(ge=0, le=1)


    @model_validator(mode="after")
    def _high_risk_requires_evidence(self) -> "VehicleAnalysis":
        """Prevent an unexplained high-risk assessment."""
        if self.risk_level in {RiskLevel.HIGH, RiskLevel.VERY_HIGH} and not self.risk_flags:
            raise ValueError("high risk requires at least one evidence-based risk flag")
        return self
