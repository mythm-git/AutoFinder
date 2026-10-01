"""Tests for the Apify-to-domain normalization boundary."""
from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from autofinder.core.exceptions import NormalizationError
from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.normalization import NormalizationWarning
from autofinder.models.normalized_listing import SellerType
from autofinder.normalization import ApifyKleinanzeigenNormalizer


FIXTURE = Path(__file__).parents[1] / "fixtures" / "apify_kleinanzeigen_dataset.json"


def _raw() -> RawMarketplaceListing:
    """Create an independent raw fixture listing with an aware collection time."""
    return RawMarketplaceListing(
        marketplace="kleinanzeigen",
        raw_data=json.loads(FIXTURE.read_text(encoding="utf-8"))[0],
        collected_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
    )


def test_representative_fixture_maps_verified_fields_and_identity() -> None:
    """Known structured Apify fields map to their canonical counterparts."""
    result = ApifyKleinanzeigenNormalizer().normalize(_raw())
    listing = result.listing
    assert listing.identity.canonical_key == "kleinanzeigen:3521306041"
    assert listing.title == "Sanitized example vehicle"
    assert listing.description == "Service history documented."
    assert listing.url == "https://www.kleinanzeigen.de/s-anzeige/sanitized-example/3521306041"
    assert listing.price_eur == 2450
    assert listing.currency == "EUR"
    assert listing.location.city == "Sanitized town"
    assert listing.location.postal_code == "27449"
    assert listing.vehicle.make == "Example"
    assert listing.vehicle.model == "Compact"
    assert listing.vehicle.mileage_km == 155000
    assert listing.vehicle.power_ps == 90
    assert listing.seller.type is SellerType.PRIVATE
    assert listing.media.primary_image_url == "https://example.invalid/image-1.jpg"
    assert listing.media.image_urls == ("https://example.invalid/image-1.jpg",)
    assert not result.warnings


def test_missing_optional_values_and_unknown_seller_emit_warnings() -> None:
    """Unavailable optional source facts remain None instead of fabricated values."""
    raw = _raw()
    raw.raw_data.pop("price")
    raw.raw_data.pop("location")
    raw.raw_data["vehicle"].pop("mileage")
    raw.raw_data["vehicle"].pop("powerPs")
    raw.raw_data["seller"] = {"type": "unverified"}
    result = ApifyKleinanzeigenNormalizer().normalize(raw)
    assert result.listing.price_eur is None
    assert result.listing.location.city is None
    assert result.listing.vehicle.mileage_km is None
    assert result.listing.vehicle.power_ps is None
    assert result.listing.seller.type is SellerType.UNKNOWN
    assert set(result.warnings) == {
        NormalizationWarning.MISSING_PRICE,
        NormalizationWarning.MISSING_LOCATION,
        NormalizationWarning.MISSING_MILEAGE,
        NormalizationWarning.MISSING_POWER,
        NormalizationWarning.UNKNOWN_SELLER_TYPE,
    }


def test_invalid_values_and_raw_evidence_are_handled_without_mutation() -> None:
    """Malformed values are warnings and the normalizer never mutates its input."""
    raw = _raw()
    raw.raw_data["price"] = "VB"
    raw.raw_data["vehicle"]["mileage"] = "many"
    raw.raw_data["vehicle"]["powerPs"] = 0
    before = json.loads(json.dumps(raw.raw_data))
    result = ApifyKleinanzeigenNormalizer().normalize(raw)
    assert result.listing.price_eur is None
    assert result.listing.vehicle.mileage_km is None
    assert result.listing.vehicle.power_ps is None
    assert set(result.warnings) >= {
        NormalizationWarning.INVALID_PRICE,
        NormalizationWarning.INVALID_MILEAGE,
        NormalizationWarning.INVALID_POWER,
    }
    assert raw.raw_data == before
    raw.raw_data["extraStructuredAttribute"]["sourceField"] = "mutated later"
    assert result.listing.source.raw_data["extraStructuredAttribute"]["sourceField"] == "preserved"


def test_collection_timestamp_is_preserved_and_normalization_time_is_aware() -> None:
    """Source provenance keeps collection time and records aware normalization time."""
    result = ApifyKleinanzeigenNormalizer().normalize(_raw()).listing
    assert result.collected_at == datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    assert result.normalized_at.tzinfo is not None


def test_malformed_root_source_fails_safely() -> None:
    """Unsupported raw structures cannot silently create corrupted domain objects."""
    malformed = RawMarketplaceListing("kleinanzeigen", [], datetime.now(UTC))  # type: ignore[arg-type]
    with pytest.raises(NormalizationError):
        ApifyKleinanzeigenNormalizer().normalize(malformed)


def test_normalize_batch_keeps_counts_and_is_local() -> None:
    """Batch normalization counts records and warnings with no network dependency."""
    second = _raw()
    second.raw_data["id"] = "3521306042"
    second.raw_data["vehicle"].pop("mileage")
    batch = ApifyKleinanzeigenNormalizer().normalize_batch((_raw(), second))
    assert batch.received_count == 2
    assert batch.normalized_count == 2
    assert batch.warning_count == 1
    assert len(batch.listings) == 2
