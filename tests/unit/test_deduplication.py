"""Tests for stable identity and atomic persistent early deduplication."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from autofinder.core.exceptions import IdentityError, SeenStateError
from autofinder.deduplication.identity import extract_listing_identity
from autofinder.deduplication.json_repository import JsonSeenListingRepository
from autofinder.deduplication.service import EarlyDeduplicator
from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.identity import ListingIdentity


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "apify_kleinanzeigen_dataset.json"
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _listing(external_id: str = "3521306041", collected_at: datetime = NOW) -> RawMarketplaceListing:
    """Build a raw listing from the sanitized representative Apify structure."""
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    raw["id"] = external_id
    raw["url"] = f"https://www.kleinanzeigen.de/s-anzeige/example/{external_id}"
    return RawMarketplaceListing("kleinanzeigen", raw, collected_at)


def _deduplicator(tmp_path: Path) -> tuple[EarlyDeduplicator, Path]:
    """Create isolated state-backed deduplication for one test."""
    state_file = tmp_path / "state" / "seen_listings.json"
    return EarlyDeduplicator(JsonSeenListingRepository(state_file)), state_file


def test_extracts_fixture_id_and_canonical_key() -> None:
    """The verified raw Apify ``id`` field yields the stable canonical identity."""
    identity = extract_listing_identity(_listing())
    assert identity.external_listing_id == "3521306041"
    assert identity.canonical_key == "kleinanzeigen:3521306041"


def test_missing_or_malformed_identity_fails_closed() -> None:
    """Title, URL, price, and description never substitute for a missing source ID."""
    missing = _listing()
    missing.raw_data.pop("id")
    malformed = _listing("not-a-marketplace-id")
    with pytest.raises(IdentityError):
        extract_listing_identity(missing)
    with pytest.raises(IdentityError):
        extract_listing_identity(malformed)


def test_empty_repository_creates_state_on_first_new_listing(tmp_path: Path) -> None:
    """First discovery is new and creates minimal state only when persisted."""
    deduplicator, state_file = _deduplicator(tmp_path)
    assert not state_file.exists()
    result = deduplicator.filter_new((_listing(),))
    assert result.new_count == 1
    assert state_file.exists()


def test_new_then_second_pass_is_successful_zero_new(tmp_path: Path) -> None:
    """Persisted identities are rejected on later runs without error."""
    deduplicator, state_file = _deduplicator(tmp_path)
    first = deduplicator.filter_new((_listing(),))
    second = deduplicator.filter_new((_listing(),))
    assert first.new_count == 1 and state_file.exists()
    assert second.new_count == 0 and second.previously_seen_count == 1
    assert second.invalid_identity_count == 0


def test_mixed_and_same_batch_duplicates_are_classified(tmp_path: Path) -> None:
    """Existing, same-batch, and invalid records cannot reach later stages."""
    deduplicator, _ = _deduplicator(tmp_path)
    deduplicator.filter_new((_listing("1"),))
    missing = _listing("4")
    missing.raw_data.pop("id")
    result = deduplicator.filter_new((_listing("1"), _listing("2"), _listing("2"), _listing("3"), missing))
    assert result.received_count == 5
    assert result.new_count == 2
    assert result.previously_seen_count == 1
    assert result.duplicate_within_batch_count == 1
    assert result.invalid_identity_count == 1
    assert [item.raw_data["id"] for item in result.new_listings] == ["2", "3"]


def test_state_survives_reconstruction_and_preserves_first_seen(tmp_path: Path) -> None:
    """A new repository instance retains durable identity and original timestamp."""
    state_file = tmp_path / "state" / "seen_listings.json"
    identity = ListingIdentity("kleinanzeigen", "77")
    first = NOW - timedelta(days=1)
    repository = JsonSeenListingRepository(state_file)
    repository.mark_seen(identity, first)
    JsonSeenListingRepository(state_file).mark_seen(identity, NOW)
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    assert payload["listings"][identity.canonical_key]["first_seen_at"] == "2026-09-30T12:00:00Z"
    assert JsonSeenListingRepository(state_file).contains(identity)


def test_corrupted_or_malformed_state_fails_closed(tmp_path: Path) -> None:
    """Existing invalid state is preserved rather than reset to empty history."""
    state_file = tmp_path / "seen_listings.json"
    state_file.write_text("{broken", encoding="utf-8")
    repository = JsonSeenListingRepository(state_file)
    with pytest.raises(SeenStateError, match="preserved"):
        repository.contains(ListingIdentity("kleinanzeigen", "1"))
    assert state_file.read_text(encoding="utf-8") == "{broken"
    state_file.write_text(json.dumps({"version": 1, "listings": []}), encoding="utf-8")
    with pytest.raises(SeenStateError, match="schema"):
        repository.contains(ListingIdentity("kleinanzeigen", "1"))


def test_atomic_write_leaves_no_temp_files_and_only_lightweight_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """State uses a sibling atomic replace and stores no raw payload or secrets."""
    state_file = tmp_path / "state" / "seen_listings.json"
    observed: list[tuple[Path, Path]] = []
    original_replace = os.replace

    def recording_replace(source: str | Path, destination: str | Path) -> None:
        observed.append((Path(source), Path(destination)))
        original_replace(source, destination)

    monkeypatch.setattr("autofinder.deduplication.json_repository.os.replace", recording_replace)
    JsonSeenListingRepository(state_file).mark_seen(ListingIdentity("kleinanzeigen", "9"), NOW)
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    entry = payload["listings"]["kleinanzeigen:9"]
    assert observed and observed[0][0].parent == state_file.parent and observed[0][1] == state_file
    assert not list(state_file.parent.glob("*.tmp"))
    assert set(entry) == {"marketplace", "external_listing_id", "first_seen_at"}
    assert "description" not in state_file.read_text(encoding="utf-8")


def test_raw_listing_is_not_mutated_and_no_secrets_are_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Dedup returns the original raw object and representative secret text is absent."""
    listing = _listing("12")
    before = json.dumps(listing.raw_data, sort_keys=True)
    result = _deduplicator(tmp_path)[0].filter_new((listing,))
    assert result.new_listings[0] is listing
    assert json.dumps(listing.raw_data, sort_keys=True) == before
    assert "super-secret" not in caplog.text
