"""Tests for deterministic filtering over canonical AutoFinder listings."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
import inspect
import json
from pathlib import Path

import pytest

from autofinder.core.config import FiltersConfig, RangeConfig
from autofinder.filters.basic import BasicDealFilter
from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.filtering import FilterRejectionReason as Reason, FilterWarning
from autofinder.normalization import ApifyKleinanzeigenNormalizer


FIXTURE = Path(__file__).parents[1] / "fixtures" / "apify_kleinanzeigen_dataset.json"
FILTERS = FiltersConfig(
    price=RangeConfig(50, 3000), mileage=RangeConfig(0, 200000), power=RangeConfig(65, 200),
    reject_dealers=True,
    dealer_text_indicators=("finanzierung ohne anzahlung", "inzahlungnahme", "autohaus", "kfz-handel", "weitere fahrzeuge", "verkaufsteam"),
)


def _raw(identifier: str = "3521306041") -> RawMarketplaceListing:
    """Build an independent sanitized raw listing for one test."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    payload["id"] = identifier
    return RawMarketplaceListing("kleinanzeigen", payload, datetime.now(UTC))


def _normalized(identifier: str = "3521306041"):
    """Normalize a fixture record before passing it to the filter."""
    return ApifyKleinanzeigenNormalizer().normalize(_raw(identifier))


def _result(raw: RawMarketplaceListing, config: FiltersConfig = FILTERS):
    """Normalize then filter a listing, mirroring the production boundary."""
    normalized = ApifyKleinanzeigenNormalizer().normalize(raw)
    return BasicDealFilter(config).filter_listing(normalized.listing, normalized.warnings)


def test_normalized_listing_is_the_filter_contract() -> None:
    """A canonical listing, not raw Apify data, is accepted by the filter."""
    normalized = _normalized()
    result = BasicDealFilter(FILTERS).filter_listing(normalized.listing, normalized.warnings)
    assert result.passed
    assert result.listing is normalized.listing


def test_price_boundaries_and_failures_are_explicit() -> None:
    """Configured inclusive price limits retain stable rejection codes."""
    for price in (50, 3000):
        raw = _raw(str(price)); raw.raw_data["price"] = price
        assert _result(raw).passed
    for price, reason in ((49, Reason.PRICE_BELOW_MINIMUM), (3001, Reason.PRICE_ABOVE_MAXIMUM)):
        raw = _raw(str(price)); raw.raw_data["price"] = price
        assert reason in _result(raw).rejection_reasons
    missing = _raw(); missing.raw_data.pop("price")
    assert Reason.MISSING_PRICE in _result(missing).rejection_reasons
    malformed = _raw(); malformed.raw_data["price"] = "VB"
    assert Reason.INVALID_PRICE in _result(malformed).rejection_reasons


def test_structured_and_text_dealer_rules_are_configurable() -> None:
    """Normalized seller type and title/description indicators remain independent."""
    dealer = _raw("1"); dealer.raw_data["seller"] = {"type": "commercial"}
    assert Reason.DEALER_SELLER in _result(dealer).rejection_reasons
    private = _raw("2"); private.raw_data["seller"] = {"type": "private"}
    assert _result(private).passed
    unknown = _raw("3"); unknown.raw_data["seller"] = {"type": "unverified"}
    unknown_result = _result(unknown)
    assert unknown_result.passed
    assert FilterWarning.UNKNOWN_SELLER_TYPE in unknown_result.warnings
    for index, indicator in enumerate(FILTERS.dealer_text_indicators, start=10):
        advertised = _raw(str(index)); advertised.raw_data["description"] = indicator.upper()
        assert Reason.DEALER_TEXT_INDICATOR in _result(advertised).rejection_reasons
    custom = _raw("20"); custom.raw_data["description"] = "SPECIAL SHOWROOM WORD"
    configured = replace(FILTERS, dealer_text_indicators=("showroom word",))
    assert Reason.DEALER_TEXT_INDICATOR in _result(custom, configured).rejection_reasons
    assert _result(custom).passed
    assert _result(dealer, replace(FILTERS, reject_dealers=False)).passed


def test_vehicle_ranges_and_missing_optional_values() -> None:
    """Canonical mileage and power retain prior range and warning semantics."""
    high_mileage = _raw("1"); high_mileage.raw_data["vehicle"]["mileage"] = 200001
    assert Reason.MILEAGE_ABOVE_MAXIMUM in _result(high_mileage).rejection_reasons
    low_power = _raw("2"); low_power.raw_data["vehicle"]["powerPs"] = 64
    assert Reason.POWER_BELOW_MINIMUM in _result(low_power).rejection_reasons
    high_power = _raw("3"); high_power.raw_data["vehicle"]["powerPs"] = 201
    assert Reason.POWER_ABOVE_MAXIMUM in _result(high_power).rejection_reasons
    optional_missing = _raw("4")
    optional_missing.raw_data["vehicle"].pop("mileage"); optional_missing.raw_data["vehicle"].pop("powerPs")
    result = _result(optional_missing)
    assert result.passed
    assert FilterWarning.MISSING_MILEAGE in result.warnings
    assert FilterWarning.MISSING_POWER in result.warnings
    invalid = _raw("5")
    invalid.raw_data["vehicle"]["mileage"] = "many"; invalid.raw_data["vehicle"]["powerPs"] = "fast"
    invalid_result = _result(invalid)
    assert Reason.INVALID_MILEAGE in invalid_result.rejection_reasons
    assert Reason.INVALID_POWER in invalid_result.rejection_reasons


def test_url_identity_and_multiple_reasons_are_defensive() -> None:
    """Structural contract failures are explicit and can coexist with price failures."""
    raw = _raw(); raw.raw_data["url"] = "not a URL"; raw.raw_data["price"] = 3001
    result = _result(raw)
    assert Reason.MISSING_OR_INVALID_URL in result.rejection_reasons
    assert Reason.PRICE_ABOVE_MAXIMUM in result.rejection_reasons
    normalized = _normalized().listing
    invalid_identity = replace(normalized, identity=replace(normalized.identity, external_listing_id=""))
    assert Reason.INVALID_IDENTITY in BasicDealFilter(FILTERS).filter_listing(invalid_identity).rejection_reasons


def test_batch_counts_raw_evidence_and_thresholds_are_preserved() -> None:
    """Batch results keep normalized objects and configuration controls behavior."""
    valid = _raw("1")
    expensive = _raw("2"); expensive.raw_data["price"] = 3500
    raw_snapshot = deepcopy(expensive.raw_data)
    normalizer = ApifyKleinanzeigenNormalizer()
    normalizations = tuple(normalizer.normalize(item) for item in (valid, expensive))
    batch = BasicDealFilter(FILTERS).filter_batch(tuple(item.listing for item in normalizations), tuple(item.warnings for item in normalizations))
    assert (batch.received_count, batch.passed_count, batch.rejected_count) == (2, 1, 1)
    assert batch.rejection_reason_counts[Reason.PRICE_ABOVE_MAXIMUM] == 1
    assert expensive.raw_data == raw_snapshot
    assert _result(expensive, replace(FILTERS, price=RangeConfig(50, 4000))).passed


def test_safe_logs_never_contain_representative_secret(caplog: pytest.LogCaptureFixture) -> None:
    """Filter diagnostics do not disclose unrelated sensitive strings."""
    secret = "apify_secret_should_not_appear"
    raw = _raw(); raw.raw_data["description"] = secret
    _result(raw)
    assert secret not in caplog.text


def test_filter_implementation_has_no_apify_payload_path_dependency() -> None:
    """Business filtering cannot regress to direct source-payload field access."""
    implementation = inspect.getsource(BasicDealFilter)
    for source_specific_path in ("raw_data", "powerPs", "postalCode", "seller["):
        assert source_specific_path not in implementation
