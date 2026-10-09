"""Typed YAML configuration loading and validation.

Only non-secret operational settings belong in YAML. Credentials are read from
local environment variables by the integrations that need them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from autofinder.analysis.models import RiskLevel

import yaml

from autofinder.core.exceptions import ConfigurationError


@dataclass(frozen=True)
class SchedulerConfig:
    """Controls how often an external scheduler should launch AutoFinder."""

    interval_minutes: int


@dataclass(frozen=True)
class SearchConfig:
    """Marketplace search scope, kept outside business logic."""

    marketplace: str
    postal_code: str
    radius_km: int
    search_url: str


@dataclass(frozen=True)
class CollectionConfig:
    """Controls the bounded newest-listings request for AutoFinder v0.1."""

    listings_per_run: int


@dataclass(frozen=True)
class ApifyConfig:
    """Non-secret Apify actor configuration for marketplace acquisition."""

    actor_id: str
    timeout_seconds: int


@dataclass(frozen=True)
class DeduplicationConfig:
    """Project-relative persistent state location for v0.1 seen-listing memory."""

    state_file: str


@dataclass(frozen=True)
class RangeConfig:
    """Inclusive numeric bounds used by future deterministic filters."""

    minimum: int
    maximum: int


@dataclass(frozen=True)
class FiltersConfig:
    """Configurable deterministic eligibility criteria before AI work."""

    price: RangeConfig
    mileage: RangeConfig
    power: RangeConfig
    reject_dealers: bool
    dealer_text_indicators: tuple[str, ...]


@dataclass(frozen=True)
class TelegramReportingConfig:
    """Non-secret Step 11 delivery and bounded-presentation settings."""

    runtime_summary_enabled: bool
    candidate_alerts_enabled: bool
    max_list_items: int


@dataclass(frozen=True)
class DailyReportingConfig:
    """Non-secret daily local audit and document-delivery settings."""

    enabled: bool
    timezone: str
    report_time: str
    report_directory: str
    audit_directory: str
    state_file: str
    send_to_telegram: bool
    include_basic_filter_rejections: bool


@dataclass(frozen=True)
class DealEvaluationConfig:
    """Explicit, non-secret deterministic policy settings for Step 10."""

    minimum_expected_roi_percent: Decimal
    minimum_conservative_roi_for_strong_percent: Decimal
    minimum_analysis_confidence: float
    minimum_repair_confidence: float
    minimum_valuation_confidence: float
    maximum_risk_for_strong: RiskLevel
    reject_very_high_risk: bool


@dataclass(frozen=True)
class AIProviderConfig:
    """Non-secret provider model selection."""

    model: str


@dataclass(frozen=True)
class AIConfig:
    """Bounded provider selection and delivery settings for structured AI work."""

    primary_provider: str
    fallback_provider: str
    timeout_seconds: int
    max_retries_per_provider: int
    groq: AIProviderConfig
    gemini: AIProviderConfig


@dataclass(frozen=True)
class AppConfig:
    """Validated, non-secret application configuration."""

    scheduler: SchedulerConfig
    search: SearchConfig
    collection: CollectionConfig
    apify: ApifyConfig
    deduplication: DeduplicationConfig
    filters: FiltersConfig
    telegram: TelegramReportingConfig
    deal_evaluation: DealEvaluationConfig
    ai: AIConfig
    daily_reporting: DailyReportingConfig | None = None


def load_config(path: Path) -> AppConfig:
    """Load and validate an AutoFinder YAML configuration file.

    Args:
        path: Absolute or relative path to the YAML file.

    Returns:
        A validated immutable application configuration.

    Raises:
        ConfigurationError: If the file is missing, malformed, or invalid.
    """
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigurationError(f"Could not read configuration: {path}") from error
    except yaml.YAMLError as error:
        raise ConfigurationError("Configuration YAML is malformed.") from error
    if not isinstance(payload, dict):
        raise ConfigurationError("Configuration root must be a mapping.")

    try:
        return _build_config(payload)
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigurationError(f"Invalid configuration: {error}") from error


def _build_config(payload: dict[str, Any]) -> AppConfig:
    """Construct and validate typed configuration from parsed YAML."""
    scheduler = payload["scheduler"]
    search = payload["search"]
    collection = payload["collection"]
    apify = payload["apify"]
    deduplication = payload["deduplication"]
    filters = payload["filters"]
    telegram = payload["telegram"]
    deal_evaluation = payload["deal_evaluation"]
    ai = payload["ai"]
    daily_reporting = payload.get("daily_reporting")
    config = AppConfig(
        scheduler=SchedulerConfig(interval_minutes=_positive_int(scheduler["interval_minutes"], "scheduler.interval_minutes")),
        search=SearchConfig(
            marketplace=_nonempty_string(search["marketplace"], "search.marketplace"),
            postal_code=_nonempty_string(search["postal_code"], "search.postal_code"),
            radius_km=_positive_int(search["radius_km"], "search.radius_km"),
            search_url=_http_url(search["search_url"], "search.search_url"),
        ),
        collection=CollectionConfig(
            listings_per_run=_positive_int(collection["listings_per_run"], "collection.listings_per_run"),
        ),
        apify=ApifyConfig(
            actor_id=_nonempty_string(apify["actor_id"], "apify.actor_id"),
            timeout_seconds=_positive_int(apify["timeout_seconds"], "apify.timeout_seconds"),
        ),
        deduplication=DeduplicationConfig(
            state_file=_relative_file_path(deduplication["state_file"], "deduplication.state_file"),
        ),
        filters=FiltersConfig(
            price=_range(filters["price"], "filters.price", "min_eur", "max_eur"),
            mileage=_range_allowing_zero(filters["mileage"], "filters.mileage", "min_km", "max_km"),
            power=_range(filters["power"], "filters.power", "min_ps", "max_ps"),
            reject_dealers=_bool(filters["reject_dealers"], "filters.reject_dealers"),
            dealer_text_indicators=_nonempty_string_tuple(filters["dealer_text_indicators"], "filters.dealer_text_indicators"),
        ),
        telegram=_telegram_reporting_config(telegram),
        deal_evaluation=_deal_evaluation_config(deal_evaluation),
        ai=_ai_config(ai),
        daily_reporting=_daily_reporting_config(daily_reporting) if daily_reporting is not None else None,
    )
    if config.filters.price.minimum > config.filters.price.maximum:
        raise ValueError("filters.price minimum cannot exceed maximum")
    return config


def _telegram_reporting_config(value: Any) -> TelegramReportingConfig:
    """Validate concise runtime Telegram reporting policy."""
    if not isinstance(value, dict):
        raise ValueError("telegram must be a mapping")
    max_items = _positive_int(value["max_list_items"], "telegram.max_list_items")
    if max_items > 10:
        raise ValueError("telegram.max_list_items must not exceed 10")
    return TelegramReportingConfig(
        runtime_summary_enabled=_bool(value["runtime_summary_enabled"], "telegram.runtime_summary_enabled"),
        candidate_alerts_enabled=_bool(value["candidate_alerts_enabled"], "telegram.candidate_alerts_enabled"),
        max_list_items=max_items,
    )


def _daily_reporting_config(value: Any) -> DailyReportingConfig:
    """Validate local-only daily reporting paths and scheduling metadata."""
    if not isinstance(value, dict):
        raise ValueError("daily_reporting must be a mapping")
    timezone = _nonempty_string(value["timezone"], "daily_reporting.timezone")
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(timezone)
    except Exception as error:
        raise ValueError("daily_reporting.timezone must be an IANA timezone") from error
    report_time = _nonempty_string(value["report_time"], "daily_reporting.report_time")
    if len(report_time) != 5 or report_time[2] != ":":
        raise ValueError("daily_reporting.report_time must use HH:MM")
    return DailyReportingConfig(
        enabled=_bool(value["enabled"], "daily_reporting.enabled"),
        timezone=timezone,
        report_time=report_time,
        report_directory=_relative_file_path(value["report_directory"], "daily_reporting.report_directory"),
        audit_directory=_relative_file_path(value["audit_directory"], "daily_reporting.audit_directory"),
        state_file=_relative_file_path(value["state_file"], "daily_reporting.state_file"),
        send_to_telegram=_bool(value["send_to_telegram"], "daily_reporting.send_to_telegram"),
        include_basic_filter_rejections=_bool(value["include_basic_filter_rejections"], "daily_reporting.include_basic_filter_rejections"),
    )


def _deal_evaluation_config(value: Any) -> DealEvaluationConfig:
    """Validate bounded, explicit Step 10 policy without secret settings."""
    if not isinstance(value, dict):
        raise ValueError("deal_evaluation must be a mapping")
    maximum_risk = _risk_level(value["maximum_risk_for_strong"], "deal_evaluation.maximum_risk_for_strong")
    if maximum_risk not in {RiskLevel.LOW, RiskLevel.MEDIUM}:
        raise ValueError("deal_evaluation.maximum_risk_for_strong must be low or medium")
    return DealEvaluationConfig(
        minimum_expected_roi_percent=_decimal(value["minimum_expected_roi_percent"], "deal_evaluation.minimum_expected_roi_percent"),
        minimum_conservative_roi_for_strong_percent=_decimal(value["minimum_conservative_roi_for_strong_percent"], "deal_evaluation.minimum_conservative_roi_for_strong_percent"),
        minimum_analysis_confidence=_confidence(value["minimum_analysis_confidence"], "deal_evaluation.minimum_analysis_confidence"),
        minimum_repair_confidence=_confidence(value["minimum_repair_confidence"], "deal_evaluation.minimum_repair_confidence"),
        minimum_valuation_confidence=_confidence(value["minimum_valuation_confidence"], "deal_evaluation.minimum_valuation_confidence"),
        maximum_risk_for_strong=maximum_risk,
        reject_very_high_risk=_bool(value["reject_very_high_risk"], "deal_evaluation.reject_very_high_risk"),
    )


def _ai_config(value: Any) -> AIConfig:
    """Validate the supported providers and bounded request settings."""
    if not isinstance(value, dict):
        raise ValueError("ai must be a mapping")
    primary = _nonempty_string(value["primary_provider"], "ai.primary_provider").lower()
    fallback = _nonempty_string(value["fallback_provider"], "ai.fallback_provider").lower()
    supported = {"groq", "gemini"}
    if primary not in supported or fallback not in supported:
        raise ValueError("ai providers must be groq or gemini")
    if primary == fallback:
        raise ValueError("ai primary_provider and fallback_provider must differ")
    return AIConfig(
        primary_provider=primary,
        fallback_provider=fallback,
        timeout_seconds=_positive_int(value["timeout_seconds"], "ai.timeout_seconds"),
        max_retries_per_provider=_nonnegative_int(value["max_retries_per_provider"], "ai.max_retries_per_provider"),
        groq=AIProviderConfig(model=_nonempty_string(value["groq"]["model"], "ai.groq.model")),
        gemini=AIProviderConfig(model=_nonempty_string(value["gemini"]["model"], "ai.gemini.model")),
    )


def _decimal(value: Any, field: str) -> Decimal:
    """Accept a finite non-boolean YAML number without binary-float comparison."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field} must be a finite number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field} must be a finite number") from error
    if not result.is_finite():
        raise ValueError(f"{field} must be a finite number")
    return result


def _confidence(value: Any, field: str) -> float:
    """Validate an inclusive confidence threshold."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"{field} must be a number from 0.0 to 1.0")
    return float(value)


def _risk_level(value: Any, field: str) -> RiskLevel:
    """Validate configuration against the existing controlled risk enum."""
    try:
        return RiskLevel(_nonempty_string(value, field).lower())
    except ValueError as error:
        raise ValueError(f"{field} must be a recognized risk level") from error


def _positive_int(value: Any, field: str) -> int:
    """Validate a positive integer while excluding booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    """Validate a non-negative integer while excluding booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _nonempty_string(value: Any, field: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _relative_file_path(value: Any, field: str) -> str:
    """Validate a non-empty project-relative state file path."""
    text = _nonempty_string(value, field)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must be a project-relative path without '..'")
    return path.as_posix()


def _http_url(value: Any, field: str) -> str:
    """Validate a basic HTTP(S) URL without making network calls."""
    text = _nonempty_string(value, field)
    if not text.startswith(("http://", "https://")):
        raise ValueError(f"{field} must start with http:// or https://")
    return text


def _bool(value: Any, field: str) -> bool:
    """Validate a strict boolean."""
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _nonempty_string_tuple(value: Any, field: str) -> tuple[str, ...]:
    """Validate a non-empty sequence of configurable normalized text indicators."""
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    return tuple(_nonempty_string(item, field) for item in value)


def _range_allowing_zero(value: Any, field: str, min_key: str, max_key: str) -> RangeConfig:
    """Validate non-negative inclusive bounds, allowing zero mileage."""
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")
    minimum = value[min_key]
    maximum = value[max_key]
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in (minimum, maximum)):
        raise ValueError(f"{field} bounds must be non-negative integers")
    if minimum > maximum:
        raise ValueError(f"{field} minimum cannot exceed maximum")
    return RangeConfig(minimum, maximum)


def _range(value: Any, field: str, min_key: str, max_key: str) -> RangeConfig:
    """Validate a mapping containing inclusive positive numeric bounds."""
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")
    result = RangeConfig(_positive_int(value[min_key], f"{field}.{min_key}"), _positive_int(value[max_key], f"{field}.{max_key}"))
    if result.minimum > result.maximum:
        raise ValueError(f"{field} minimum cannot exceed maximum")
    return result
