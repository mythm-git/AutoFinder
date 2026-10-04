"""Apify/Kleinanzeigen payload adapter producing canonical AutoFinder listings."""

from __future__ import annotations

import copy
import logging
from datetime import UTC, datetime
from typing import Any

from autofinder.core.exceptions import NormalizationError
from autofinder.deduplication.identity import extract_listing_identity
from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.normalization import NormalizationBatchResult, NormalizationResult, NormalizationWarning
from autofinder.models.normalized_listing import NormalizedListing, NormalizedLocation, NormalizedMedia, NormalizedSeller, NormalizedVehicle, SellerType, SourceEvidence
from autofinder.normalization.base import ListingNormalizer


class ApifyKleinanzeigenNormalizer(ListingNormalizer):
    """Map verified Apify fields to canonical models after early deduplication."""

    def __init__(self) -> None:
        """Create a stateless source adapter with central application logging."""
        self._logger = logging.getLogger("autofinder.normalization.apify_kleinanzeigen")

    def normalize(self, listing: RawMarketplaceListing) -> NormalizationResult:
        """Normalize one raw Apify/Kleinanzeigen listing without inference.

        Raises:
            NormalizationError: If a required post-dedup identity cannot be rebuilt.
        """
        try:
            identity = extract_listing_identity(listing)
        except Exception as error:
            self._logger.error("Cannot normalize listing with invalid identity: %s", type(error).__name__)
            raise NormalizationError("Cannot normalize listing without a valid stable identity.") from error
        raw = listing.raw_data
        if not isinstance(raw, dict):
            raise NormalizationError("Cannot normalize malformed raw listing structure.")
        warnings: list[NormalizationWarning] = []
        price = _optional_number(raw.get("price"), NormalizationWarning.MISSING_PRICE, NormalizationWarning.INVALID_PRICE, warnings)
        currency = _currency(raw.get("currency"), warnings)
        location = _location(raw, warnings)
        vehicle = _vehicle(raw, warnings)
        seller = _seller(raw, warnings)
        media = _media(raw.get("images", raw.get("imageUrls")))
        normalized = NormalizedListing(
            identity=identity,
            title=_optional_text(raw.get("title")),
            description=_optional_text(raw.get("description")),
            url=_optional_text(raw.get("url")),
            price_eur=price,
            currency=currency,
            location=location,
            vehicle=vehicle,
            seller=seller,
            media=media,
            collected_at=listing.collected_at,
            normalized_at=datetime.now(UTC),
            source=SourceEvidence(provider="apify", marketplace=identity.marketplace, raw_data=copy.deepcopy(raw)),
        )
        self._logger.debug("Normalized listing identity: %s", identity.canonical_key)
        return NormalizationResult(normalized, tuple(warnings))

    def normalize_batch(self, listings: tuple[RawMarketplaceListing, ...]) -> NormalizationBatchResult:
        """Normalize deduplicated records and report non-fatal mapping warning totals."""
        self._logger.info("Normalization started: received_count=%s", len(listings))
        results = tuple(self.normalize(listing) for listing in listings)
        batch = NormalizationBatchResult(len(listings), len(results), sum(len(result.warnings) for result in results), results, tuple(result.listing for result in results))
        self._logger.info("Normalization completed: normalized_count=%s warning_count=%s", batch.normalized_count, batch.warning_count)
        return batch


def _optional_text(value: Any) -> str | None:
    """Return stripped source text or explicit ``None`` for unavailable values."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_number(value: Any, missing: NormalizationWarning, invalid: NormalizationWarning, warnings: list[NormalizationWarning], allow_zero: bool = False) -> float | None:
    """Map structured positive numeric source values without parsing free text."""
    if value is None:
        warnings.append(missing)
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or (value == 0 and not allow_zero):
        warnings.append(invalid)
        return None
    return float(value)



def _structured_number(value: Any, missing: NormalizationWarning, invalid: NormalizationWarning, warnings: list[NormalizationWarning], allow_zero: bool = False) -> float | None:
    """Accept numeric actor values or digit-only structured strings, never prose."""
    if isinstance(value, str):
        value = int(value) if value.strip().isdigit() else value
    return _optional_number(value, missing, invalid, warnings, allow_zero)


def _vehicle(raw_listing: dict[str, Any], warnings: list[NormalizationWarning]) -> NormalizedVehicle:
    """Map verified legacy or current actor vehicle fields without title inference."""
    raw = raw_listing.get("vehicle")
    if not isinstance(raw, dict):
        raw = raw_listing.get("attributes") if isinstance(raw_listing.get("attributes"), dict) else {}
    mileage = _structured_number(raw.get("mileage"), NormalizationWarning.MISSING_MILEAGE, NormalizationWarning.INVALID_MILEAGE, warnings, allow_zero=True)
    power = _structured_number(raw.get("powerPs", raw.get("power")), NormalizationWarning.MISSING_POWER, NormalizationWarning.INVALID_POWER, warnings)
    return NormalizedVehicle(
        _optional_text(raw.get("make", raw.get("brand"))),
        _optional_text(raw.get("model")),
        mileage,
        power,
    )


def _location(raw_listing: dict[str, Any], warnings: list[NormalizationWarning]) -> NormalizedLocation:
    """Map verified legacy nested or current flat source location without geocoding."""
    value = raw_listing.get("location")
    if isinstance(value, dict):
        city = _optional_text(value.get("city"))
        postal_code = _optional_text(value.get("postalCode"))
    else:
        city = _optional_text(value)
        postal_code = _optional_text(raw_listing.get("postalCode"))
    if city is None and postal_code is None:
        warnings.append(NormalizationWarning.MISSING_LOCATION)
    return NormalizedLocation(city, postal_code, None)


def _seller(raw_listing: dict[str, Any], warnings: list[NormalizationWarning]) -> NormalizedSeller:
    """Map known legacy nested or current flat structured seller values."""
    value = raw_listing.get("seller")
    raw_type = _optional_text(value.get("type")) if isinstance(value, dict) else _optional_text(raw_listing.get("sellerType"))
    normalized = raw_type.casefold() if raw_type else ""
    if normalized == "private":
        return NormalizedSeller(SellerType.PRIVATE, raw_type)
    if normalized in {"dealer", "commercial", "business", "gewerblich", "handler", "händler"}:
        return NormalizedSeller(SellerType.DEALER, raw_type)
    warnings.append(NormalizationWarning.UNKNOWN_SELLER_TYPE)
    return NormalizedSeller(SellerType.UNKNOWN, raw_type)


def _currency(value: Any, warnings: list[NormalizationWarning]) -> str | None:
    """Standardize verified EUR source currency; retain unknown as explicit absence."""
    currency = _optional_text(value)
    if currency is None:
        return None
    if currency.upper() == "EUR":
        return "EUR"
    warnings.append(NormalizationWarning.UNKNOWN_CURRENCY)
    return None


def _media(value: Any) -> NormalizedMedia:
    """Retain valid source image URL strings without downloading them."""
    urls = tuple(item.strip() for item in value if isinstance(item, str) and item.strip()) if isinstance(value, list) else ()
    return NormalizedMedia(urls[0] if urls else None, urls)
