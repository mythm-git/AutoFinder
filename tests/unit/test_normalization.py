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
LIVE_FIXTURE = Path(__file__).parents[1] / "fixtures" / "apify_kleinanzeigen_live_schema.json"


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



def test_current_actor_shape_uses_listing_id_and_structured_attributes() -> None:
    """The verified flat actor shape maps without falling back to free text."""
    raw = RawMarketplaceListing(
        "kleinanzeigen",
        {
            "listingId": "3521306042", "title": "Sanitized", "description": "Sanitized",
            "price": 1900, "currency": "EUR", "url": "https://example.invalid/3521306042",
            "location": "Sanitized town", "postalCode": "27449", "sellerType": "private",
            "imageUrls": ["https://example.invalid/image.jpg"],
            "attributes": {"brand": "Example", "model": "Current", "mileage": "155000", "power": "90"},
        },
        datetime.now(UTC),
    )
    listing = ApifyKleinanzeigenNormalizer().normalize(raw).listing
    assert listing.identity.canonical_key == "kleinanzeigen:3521306042"
    assert (listing.location.city, listing.location.postal_code) == ("Sanitized town", "27449")
    assert (listing.vehicle.make, listing.vehicle.model, listing.vehicle.mileage_km, listing.vehicle.power_ps) == ("Example", "Current", 155000, 90)
    assert listing.seller.type is SellerType.PRIVATE
    assert listing.media.image_urls == ("https://example.invalid/image.jpg",)


def test_live_actor_fixture_parses_unit_bearing_structured_attributes() -> None:
    """Current Apify attributes use explicit German km and PS unit strings."""
    raw = RawMarketplaceListing("kleinanzeigen", json.loads(LIVE_FIXTURE.read_text(encoding="utf-8")), datetime.now(UTC))
    listing = ApifyKleinanzeigenNormalizer().normalize(raw).listing
    assert (listing.vehicle.mileage_km, listing.vehicle.power_ps) == (126500, 109)


@pytest.mark.parametrize(("mileage", "power", "expected_mileage", "expected_power", "warning"), [
    (126500, 109, 126500, 109, None), ("126500", "109", 126500, 109, None),
    ("126.500", "109 PS", 126500, 109, None), ("126.500 km", "71 PS", 126500, 71, None),
    ("111.846 km", "80 PS", 111846, 80, None), ("190.000 km", "70 PS", 190000, 70, None),
    (None, None, None, None, NormalizationWarning.MISSING_MILEAGE), ("", "PS", None, None, NormalizationWarning.INVALID_MILEAGE),
    ("unknown", "abc km", None, None, NormalizationWarning.INVALID_MILEAGE),
])
def test_structured_vehicle_unit_parsing(mileage: object, power: object, expected_mileage: float | None, expected_power: float | None, warning: NormalizationWarning | None) -> None:
    """Known structured formats parse; malformed values retain existing warnings."""
    raw = _raw()
    raw.raw_data["vehicle"]["mileage"] = mileage
    raw.raw_data["vehicle"]["powerPs"] = power
    result = ApifyKleinanzeigenNormalizer().normalize(raw)
    assert (result.listing.vehicle.mileage_km, result.listing.vehicle.power_ps) == (expected_mileage, expected_power)
    if warning:
        assert warning in result.warnings
    if power is None:
        assert NormalizationWarning.MISSING_POWER in result.warnings
    elif expected_power is None:
        assert NormalizationWarning.INVALID_POWER in result.warnings


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
