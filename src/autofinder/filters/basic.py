"""Cheap, explainable deterministic filtering over canonical domain listings."""

from __future__ import annotations

import logging
import unicodedata
from collections import Counter
from urllib.parse import urlparse

from autofinder.core.config import FiltersConfig
from autofinder.models.filtering import BasicFilterBatchResult, BasicFilterResult, FilterRejectionReason, FilterWarning
from autofinder.models.normalization import NormalizationWarning
from autofinder.models.normalized_listing import NormalizedListing, SellerType


class BasicDealFilter:
    """Apply configured structural and numeric rules to normalized unseen listings."""

    def __init__(self, config: FiltersConfig) -> None:
        """Create a filter using typed configuration rather than hard-coded thresholds."""
        self._config = config
        self._indicators = tuple(_normalize_text(indicator) for indicator in config.dealer_text_indicators)
        self._logger = logging.getLogger("autofinder.filters.basic")

    def filter_listing(self, listing: NormalizedListing, normalization_warnings: tuple[NormalizationWarning, ...] = ()) -> BasicFilterResult:
        """Evaluate one normalized listing without reading marketplace raw payload paths.

        Args:
            listing: Canonical domain model produced after early deduplication.
            normalization_warnings: Mapping diagnostics used to distinguish absent
                optional values from malformed source values.
        """
        reasons: list[FilterRejectionReason] = []
        warnings: list[FilterWarning] = []
        matched_indicators: list[str] = []
        if not listing.identity.marketplace or not listing.identity.external_listing_id:
            reasons.append(FilterRejectionReason.INVALID_IDENTITY)
        else:
            self._logger.debug("Filtering listing identity: %s", listing.identity.canonical_key)
        if not _is_valid_kleinanzeigen_url(listing.url):
            reasons.append(FilterRejectionReason.MISSING_OR_INVALID_URL)
        if not (listing.title or listing.description):
            reasons.append(FilterRejectionReason.UNUSABLE_LISTING)
        _apply_price(listing.price_eur, normalization_warnings, self._config, reasons)
        if self._config.reject_dealers and listing.seller.type is SellerType.DEALER:
            reasons.append(FilterRejectionReason.DEALER_SELLER)
        elif listing.seller.type is SellerType.UNKNOWN:
            warnings.append(FilterWarning.UNKNOWN_SELLER_TYPE)
        if self._config.reject_dealers:
            text = _normalize_text(f"{listing.title or ''} {listing.description or ''}")
            matched_indicators = [indicator for indicator in self._indicators if indicator in text]
            if matched_indicators:
                reasons.append(FilterRejectionReason.DEALER_TEXT_INDICATOR)
        _apply_optional_range(listing.vehicle.mileage_km, normalization_warnings, NormalizationWarning.MISSING_MILEAGE, NormalizationWarning.INVALID_MILEAGE, self._config.mileage.minimum, self._config.mileage.maximum, FilterWarning.MISSING_MILEAGE, FilterRejectionReason.INVALID_MILEAGE, FilterRejectionReason.MILEAGE_BELOW_MINIMUM, FilterRejectionReason.MILEAGE_ABOVE_MAXIMUM, warnings, reasons)
        _apply_optional_range(listing.vehicle.power_ps, normalization_warnings, NormalizationWarning.MISSING_POWER, NormalizationWarning.INVALID_POWER, self._config.power.minimum, self._config.power.maximum, FilterWarning.MISSING_POWER, FilterRejectionReason.INVALID_POWER, FilterRejectionReason.POWER_BELOW_MINIMUM, FilterRejectionReason.POWER_ABOVE_MAXIMUM, warnings, reasons)
        result = BasicFilterResult(listing, not reasons, tuple(reasons), tuple(warnings), tuple(matched_indicators))
        if reasons:
            self._logger.debug("Listing rejected: reasons=%s", ",".join(reason.value for reason in reasons))
        return result

    def filter_batch(self, listings: tuple[NormalizedListing, ...], warning_sets: tuple[tuple[NormalizationWarning, ...], ...] | None = None) -> BasicFilterBatchResult:
        """Filter normalized listings and return explicit batch statistics."""
        if warning_sets is not None and len(warning_sets) != len(listings):
            raise ValueError("warning_sets must align one-to-one with listings")
        self._logger.info("Basic filtering started: received_count=%s", len(listings))
        results = tuple(self.filter_listing(listing, warning_sets[index] if warning_sets else ()) for index, listing in enumerate(listings))
        passed = tuple(result.listing for result in results if result.passed)
        reason_counts = Counter(reason for result in results for reason in result.rejection_reasons)
        batch = BasicFilterBatchResult(len(listings), len(passed), len(results) - len(passed), passed, results, dict(reason_counts))
        self._logger.info("Basic filtering completed: passed_count=%s rejected_count=%s", batch.passed_count, batch.rejected_count)
        return batch


def _apply_price(value: float | None, normalization_warnings: tuple[NormalizationWarning, ...], config: FiltersConfig, reasons: list[FilterRejectionReason]) -> None:
    """Apply bounds to canonical EUR price while preserving mapping diagnostics."""
    if value is None:
        reasons.append(FilterRejectionReason.INVALID_PRICE if NormalizationWarning.INVALID_PRICE in normalization_warnings else FilterRejectionReason.MISSING_PRICE)
    elif value < config.price.minimum:
        reasons.append(FilterRejectionReason.PRICE_BELOW_MINIMUM)
    elif value > config.price.maximum:
        reasons.append(FilterRejectionReason.PRICE_ABOVE_MAXIMUM)


def _apply_optional_range(value: float | None, normalization_warnings: tuple[NormalizationWarning, ...], missing_source_warning: NormalizationWarning, invalid_source_warning: NormalizationWarning, minimum: int, maximum: int, missing_filter_warning: FilterWarning, invalid_reason: FilterRejectionReason, below_reason: FilterRejectionReason, above_reason: FilterRejectionReason, warnings: list[FilterWarning], reasons: list[FilterRejectionReason]) -> None:
    """Apply canonical bounds while keeping missing optional values non-blocking."""
    if value is None:
        if invalid_source_warning in normalization_warnings:
            reasons.append(invalid_reason)
        else:
            warnings.append(missing_filter_warning)
        return
    if value < minimum:
        reasons.append(below_reason)
    elif value > maximum:
        reasons.append(above_reason)


def _is_valid_kleinanzeigen_url(value: str | None) -> bool:
    """Perform structural URL validation without a network request."""
    if value is None:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and parsed.netloc.endswith("kleinanzeigen.de")


def _normalize_text(value: str) -> str:
    """Casefold and normalize text for deterministic configured phrase matching."""
    return unicodedata.normalize("NFKC", value.strip()).casefold()
