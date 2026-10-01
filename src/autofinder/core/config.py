"""Typed YAML configuration loading and validation.

Only non-secret operational settings belong in YAML. Credentials are read from
local environment variables by the integrations that need them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
class AIConfig:
    """Provider preference for future interchangeable AI integrations."""

    primary_provider: str
    fallback_provider: str


@dataclass(frozen=True)
class AppConfig:
    """Validated, non-secret application configuration."""

    scheduler: SchedulerConfig
    search: SearchConfig
    collection: CollectionConfig
    apify: ApifyConfig
    deduplication: DeduplicationConfig
    filters: FiltersConfig
    ai: AIConfig


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
    ai = payload["ai"]
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
        ai=AIConfig(
            primary_provider=_nonempty_string(ai["primary_provider"], "ai.primary_provider"),
            fallback_provider=_nonempty_string(ai["fallback_provider"], "ai.fallback_provider"),
        ),
    )
    if config.filters.price.minimum > config.filters.price.maximum:
        raise ValueError("filters.price minimum cannot exceed maximum")
    return config


def _positive_int(value: Any, field: str) -> int:
    """Validate a positive integer while excluding booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
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
