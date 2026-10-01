"""Canonical AutoFinder domain model independent of marketplace payload paths."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from autofinder.models.identity import ListingIdentity


class SellerType(StrEnum):
    """Canonical seller classification supported by verified source values."""

    PRIVATE = "private"
    DEALER = "dealer"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NormalizedLocation:
    """Deterministic source location facts without geocoding or inference."""

    city: str | None
    postal_code: str | None
    raw_text: str | None


@dataclass(frozen=True)
class NormalizedVehicle:
    """Verified structured vehicle facts; unavailable values remain ``None``."""

    make: str | None
    model: str | None
    mileage_km: float | None
    power_ps: float | None


@dataclass(frozen=True)
class NormalizedSeller:
    """Canonical seller classification plus the original deterministic source value."""

    type: SellerType
    raw_type: str | None


@dataclass(frozen=True)
class NormalizedMedia:
    """Source-provided image references without downloads or transformations."""

    primary_image_url: str | None
    image_urls: tuple[str, ...]


@dataclass(frozen=True)
class SourceEvidence:
    """Lossless copied raw source evidence retained for audit and future remapping."""

    provider: str
    marketplace: str
    raw_data: dict[str, Any]


@dataclass(frozen=True)
class NormalizedListing:
    """Canonical listing facts consumed by filters and future downstream modules."""

    identity: ListingIdentity
    title: str | None
    description: str | None
    url: str | None
    price_eur: float | None
    currency: str | None
    location: NormalizedLocation
    vehicle: NormalizedVehicle
    seller: NormalizedSeller
    media: NormalizedMedia
    collected_at: datetime
    normalized_at: datetime
    source: SourceEvidence
