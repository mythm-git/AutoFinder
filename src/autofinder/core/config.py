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
    """Controls collection breadth and unseen-listing throughput."""

    max_new_listings_per_run: int
    acquisition_batch_size: int


@dataclass(frozen=True)
class ApifyConfig:
    """Non-secret Apify actor configuration for marketplace acquisition."""

    actor_id: str
    timeout_seconds: int


@dataclass(frozen=True)
class RangeConfig:
    """Inclusive numeric bounds used by future deterministic filters."""

    minimum: int
    maximum: int


@dataclass(frozen=True)
class FiltersConfig:
    """Future inexpensive eligibility criteria."""

    price: RangeConfig
    mileage_max_km: int
    power: RangeConfig
    reject_dealers: bool


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
            max_new_listings_per_run=_positive_int(collection["max_new_listings_per_run"], "collection.max_new_listings_per_run"),
            acquisition_batch_size=_positive_int(collection["acquisition_batch_size"], "collection.acquisition_batch_size"),
        ),
        apify=ApifyConfig(
            actor_id=_nonempty_string(apify["actor_id"], "apify.actor_id"),
            timeout_seconds=_positive_int(apify["timeout_seconds"], "apify.timeout_seconds"),
        ),
        filters=FiltersConfig(
            price=_range(filters["price"], "filters.price", "min_eur", "max_eur"),
            mileage_max_km=_positive_int(filters["mileage"]["max_km"], "filters.mileage.max_km"),
            power=_range(filters["power"], "filters.power", "min_ps", "max_ps"),
            reject_dealers=_bool(filters["reject_dealers"], "filters.reject_dealers"),
        ),
        ai=AIConfig(
            primary_provider=_nonempty_string(ai["primary_provider"], "ai.primary_provider"),
            fallback_provider=_nonempty_string(ai["fallback_provider"], "ai.fallback_provider"),
        ),
    )
    if config.collection.acquisition_batch_size < config.collection.max_new_listings_per_run:
        raise ValueError("collection.acquisition_batch_size must be at least max_new_listings_per_run")
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


def _range(value: Any, field: str, min_key: str, max_key: str) -> RangeConfig:
    """Validate a mapping containing inclusive positive numeric bounds."""
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")
    result = RangeConfig(_positive_int(value[min_key], f"{field}.{min_key}"), _positive_int(value[max_key], f"{field}.{max_key}"))
    if result.minimum > result.maximum:
        raise ValueError(f"{field} minimum cannot exceed maximum")
    return result
