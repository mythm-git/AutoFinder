"""Cheap, explainable deterministic filtering before future AI work."""

from __future__ import annotations

import logging
import unicodedata
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from autofinder.core.config import FiltersConfig
from autofinder.core.exceptions import IdentityError
from autofinder.deduplication.identity import extract_listing_identity
from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.filtering import BasicFilterBatchResult, BasicFilterResult, FilterRejectionReason, FilterWarning


class BasicDealFilter:
    """Apply configured structural and numeric eligibility rules to unseen listings."""

    def __init__(self, config: FiltersConfig) -> None:
        """Create a filter using typed configuration rather than hard-coded thresholds."""
        self._config = config
        self._indicators = tuple(_normalize_text(indicator) for indicator in config.dealer_text_indicators)
        self._logger = logging.getLogger("autofinder.filters.basic")

    def filter_listing(self, listing: RawMarketplaceListing) -> BasicFilterResult:
        """Evaluate one listing while retaining every field in its raw evidence.

        Returns:
            A decision containing stable rejection codes and non-blocking warnings.
        """
        reasons: list[FilterRejectionReason] = []
        warnings: list[FilterWarning] = []
        matched_indicators: list[str] = []
        try:
            identity = extract_listing_identity(listing)
            self._logger.debug("Filtering listing identity: %s", identity.canonical_key)
        except IdentityError:
            reasons.append(FilterRejectionReason.INVALID_IDENTITY)
        raw = listing.raw_data
        if not _is_valid_kleinanzeigen_url(raw.get("url")):
            reasons.append(FilterRejectionReason.MISSING_OR_INVALID_URL)
        if not _has_meaningful_content(raw):
            reasons.append(FilterRejectionReason.UNUSABLE_LISTING)
        _apply_price(raw.get("price"), self._config, reasons)
        seller_type = _seller_type(raw)
        if self._config.reject_dealers and seller_type in {"dealer", "commercial", "business", "gewerblich", "handler", "händler"}:
            reasons.append(FilterRejectionReason.DEALER_SELLER)
        elif not seller_type:
            warnings.append(FilterWarning.UNKNOWN_SELLER_TYPE)
        if self._config.reject_dealers:
            text = _normalize_text(f"{_text(raw.get('title'))} {_text(raw.get('description'))}")
            matched_indicators = [indicator for indicator in self._indicators if indicator in text]
            if matched_indicators:
                reasons.append(FilterRejectionReason.DEALER_TEXT_INDICATOR)
        _apply_optional_range(raw.get("vehicle", {}), "mileage", self._config.mileage.minimum, self._config.mileage.maximum, FilterWarning.MISSING_MILEAGE, FilterRejectionReason.INVALID_MILEAGE, FilterRejectionReason.MILEAGE_BELOW_MINIMUM, FilterRejectionReason.MILEAGE_ABOVE_MAXIMUM, warnings, reasons)
        _apply_optional_range(raw.get("vehicle", {}), "powerPs", self._config.power.minimum, self._config.power.maximum, FilterWarning.MISSING_POWER, FilterRejectionReason.INVALID_POWER, FilterRejectionReason.POWER_BELOW_MINIMUM, FilterRejectionReason.POWER_ABOVE_MAXIMUM, warnings, reasons)
        result = BasicFilterResult(listing, not reasons, tuple(reasons), tuple(warnings), tuple(matched_indicators))
        if reasons:
            self._logger.debug("Listing rejected: reasons=%s", ",".join(reason.value for reason in reasons))
        return result

    def filter_batch(self, listings: tuple[RawMarketplaceListing, ...]) -> BasicFilterBatchResult:
        """Filter deduplicated raw listings and return explicit batch statistics."""
        self._logger.info("Basic filtering started: received_count=%s", len(listings))
        results = tuple(self.filter_listing(listing) for listing in listings)
        passed = tuple(result.listing for result in results if result.passed)
        reason_counts = Counter(reason for result in results for reason in result.rejection_reasons)
        batch = BasicFilterBatchResult(len(listings), len(passed), len(results) - len(passed), passed, results, dict(reason_counts))
        self._logger.info("Basic filtering completed: passed_count=%s rejected_count=%s", batch.passed_count, batch.rejected_count)
        return batch


def _apply_price(value: Any, config: FiltersConfig, reasons: list[FilterRejectionReason]) -> None:
    """Validate numeric structured EUR price without guessing from free text."""
    if value is None:
        reasons.append(FilterRejectionReason.MISSING_PRICE)
    elif isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        reasons.append(FilterRejectionReason.INVALID_PRICE)
    elif value < config.price.minimum:
        reasons.append(FilterRejectionReason.PRICE_BELOW_MINIMUM)
    elif value > config.price.maximum:
        reasons.append(FilterRejectionReason.PRICE_ABOVE_MAXIMUM)


def _apply_optional_range(container: Any, field: str, minimum: int, maximum: int, missing_warning: FilterWarning, invalid_reason: FilterRejectionReason, below_reason: FilterRejectionReason, above_reason: FilterRejectionReason, warnings: list[FilterWarning], reasons: list[FilterRejectionReason]) -> None:
    """Apply bounds only when a structured optional numeric field is present."""
    if not isinstance(container, dict) or field not in container or container[field] is None:
        warnings.append(missing_warning)
        return
    value = container[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        reasons.append(invalid_reason)
    elif value < minimum:
        reasons.append(below_reason)
    elif value > maximum:
        reasons.append(above_reason)


def _seller_type(raw: dict[str, Any]) -> str:
    """Read structured seller type when available, preferring source data to heuristics."""
    seller = raw.get("seller")
    return _normalize_text(seller.get("type")) if isinstance(seller, dict) else ""


def _has_meaningful_content(raw: dict[str, Any]) -> bool:
    """Require title or description while allowing incomplete otherwise-valid ads."""
    return bool(_text(raw.get("title")) or _text(raw.get("description")))


def _is_valid_kleinanzeigen_url(value: Any) -> bool:
    """Perform structural URL validation without a network request."""
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and parsed.netloc.endswith("kleinanzeigen.de")


def _text(value: Any) -> str:
    """Return a stripped string or an empty value for non-text source fields."""
    return value.strip() if isinstance(value, str) else ""


def _normalize_text(value: Any) -> str:
    """Casefold and normalize Unicode text for deterministic phrase matching."""
    return unicodedata.normalize("NFKC", _text(value)).casefold()
