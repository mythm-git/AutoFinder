"""Fixture-only tests for configurable deterministic deal filtering."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from autofinder.core.config import FiltersConfig, RangeConfig, load_config
from autofinder.filters.basic import BasicDealFilter
from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.filtering import BasicFilterResult, FilterRejectionReason as Reason, FilterWarning


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json"
FILTERS = load_config(ROOT / "config" / "autofinder.yaml").filters
NOW = datetime(2026, 10, 1, tzinfo=UTC)


def _listing(identifier: str = "3521306041") -> RawMarketplaceListing:
    """Return a fresh valid private listing from the sanitized Apify fixture."""
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    raw["id"] = identifier
    return RawMarketplaceListing("kleinanzeigen", raw, NOW)


def _result(listing: RawMarketplaceListing, config: FiltersConfig = FILTERS) -> BasicFilterResult:
    """Filter one listing with an optionally adjusted typed configuration."""
    return BasicDealFilter(config).filter_listing(listing)


def test_valid_listing_and_price_boundaries_pass() -> None:
    """Valid structured private listings pass at both configured price bounds."""
    for price in (FILTERS.price.minimum, FILTERS.price.maximum):
        listing = _listing(str(price))
        listing.raw_data["price"] = price
        result = _result(listing)
        assert result.passed and not result.rejection_reasons


@pytest.mark.parametrize(("price", "reason"), [
    (49, Reason.PRICE_BELOW_MINIMUM), (3001, Reason.PRICE_ABOVE_MAXIMUM), ("VB", Reason.INVALID_PRICE), (None, Reason.MISSING_PRICE),
])
def test_price_rejections_are_explicit(price: object, reason: Reason) -> None:
    """Missing, free-text, and out-of-range prices do not silently pass."""
    listing = _listing()
    listing.raw_data["price"] = price
    assert reason in _result(listing).rejection_reasons


def test_structured_seller_rules_and_unknown_warning() -> None:
    """Structured dealer rejects, private passes, and unknown remains non-blocking."""
    dealer = _listing("1")
    dealer.raw_data["seller"] = {"type": "commercial"}
    assert Reason.DEALER_SELLER in _result(dealer).rejection_reasons
    private = _listing("2")
    assert _result(private).passed
    unknown = _listing("3")
    unknown.raw_data.pop("seller")
    unknown_result = _result(unknown)
    assert unknown_result.passed and FilterWarning.UNKNOWN_SELLER_TYPE in unknown_result.warnings


@pytest.mark.parametrize("indicator", FILTERS.dealer_text_indicators)
def test_configured_dealer_indicators_are_case_insensitive(indicator: str) -> None:
    """Every configured exact phrase rejects independent of input case."""
    listing = _listing()
    listing.raw_data["description"] = indicator.upper()
    result = _result(listing)
    assert Reason.DEALER_TEXT_INDICATOR in result.rejection_reasons
    assert indicator in result.matched_indicators


def test_dealer_patterns_and_rejection_switch_are_configurable() -> None:
    """Changed configuration alters decisions without filter code changes."""
    listing = _listing()
    listing.raw_data["description"] = "SPECIAL SHOWROOM WORD"
    configured = replace(FILTERS, dealer_text_indicators=("showroom word",))
    assert Reason.DEALER_TEXT_INDICATOR in _result(listing, configured).rejection_reasons
    no_dealer_rejection = replace(configured, reject_dealers=False)
    assert _result(listing, no_dealer_rejection).passed


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("mileage", 200001, Reason.MILEAGE_ABOVE_MAXIMUM),
    ("mileage", "many", Reason.INVALID_MILEAGE),
    ("powerPs", 64, Reason.POWER_BELOW_MINIMUM),
    ("powerPs", 201, Reason.POWER_ABOVE_MAXIMUM),
    ("powerPs", "unknown", Reason.INVALID_POWER),
])
def test_optional_numeric_values_are_checked_when_present(field: str, value: object, reason: Reason) -> None:
    """Present malformed or out-of-range vehicle attributes reject deterministically."""
    listing = _listing()
    listing.raw_data["vehicle"][field] = value
    assert reason in _result(listing).rejection_reasons


def test_missing_optional_vehicle_values_are_warnings_not_rejections() -> None:
    """Missing mileage and power remain available for later AI interpretation."""
    listing = _listing()
    listing.raw_data["vehicle"].pop("mileage")
    listing.raw_data["vehicle"].pop("powerPs")
    result = _result(listing)
    assert result.passed
    assert {FilterWarning.MISSING_MILEAGE, FilterWarning.MISSING_POWER}.issubset(result.warnings)


def test_url_identity_and_unusable_content_reject_defensively() -> None:
    """Unexpected contract violations do not pass the deterministic boundary."""
    listing = _listing()
    # Rebuild the frozen wrapper to model malformed upstream identity input.
    invalid_identity = RawMarketplaceListing("", listing.raw_data, NOW)
    invalid_identity.raw_data["url"] = "not-a-url"
    invalid_identity.raw_data["title"] = ""
    invalid_identity.raw_data["description"] = ""
    reasons = _result(invalid_identity).rejection_reasons
    assert {Reason.INVALID_IDENTITY, Reason.MISSING_OR_INVALID_URL, Reason.UNUSABLE_LISTING}.issubset(reasons)


def test_multiple_reasons_batch_counts_and_raw_evidence_are_preserved() -> None:
    """Batch output retains original objects and counts every stable rejection code."""
    valid = _listing("1")
    expensive = _listing("2")
    expensive.raw_data["price"] = 3001
    dealer = _listing("3")
    dealer.raw_data["seller"] = {"type": "dealer"}
    original = json.dumps(expensive.raw_data, sort_keys=True)
    batch = BasicDealFilter(FILTERS).filter_batch((valid, expensive, dealer))
    assert batch.received_count == 3 and batch.passed_count == 1 and batch.rejected_count == 2
    assert batch.rejection_reason_counts[Reason.PRICE_ABOVE_MAXIMUM] == 1
    assert batch.rejection_reason_counts[Reason.DEALER_SELLER] == 1
    assert batch.passed_listings[0] is valid
    assert json.dumps(expensive.raw_data, sort_keys=True) == original


def test_thresholds_are_configurable_and_logs_do_not_contain_representative_secret(caplog: pytest.LogCaptureFixture) -> None:
    """Changing a typed threshold changes behavior without leaking unrelated values."""
    listing = _listing()
    listing.raw_data["price"] = 3500
    raised_maximum = replace(FILTERS, price=RangeConfig(50, 4000))
    assert _result(listing, raised_maximum).passed
    assert "super-secret" not in caplog.text
