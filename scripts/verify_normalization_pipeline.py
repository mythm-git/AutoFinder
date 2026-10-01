"""Verify the fixture-only deduplication, normalization, and filtering order.

This development script never calls Apify, AI providers, or the network. It uses
temporary state so production seen-listing history is not altered.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from autofinder.core.config import load_config
from autofinder.deduplication import EarlyDeduplicator, JsonSeenListingRepository
from autofinder.filters.basic import BasicDealFilter
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json"


def _representative_batch() -> tuple[RawMarketplaceListing, ...]:
    """Create five local examples with one pass and four deterministic rejections.

    Returns:
        A tuple of raw records with unique stable marketplace IDs.
    """
    template = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[0]
    records: list[RawMarketplaceListing] = []
    for number in range(1, 6):
        payload = deepcopy(template)
        payload["id"] = f"35213061{number}"
        records.append(RawMarketplaceListing("kleinanzeigen", payload, datetime.now(UTC)))
    records[1].raw_data["price"] = 3001
    records[2].raw_data["seller"] = {"type": "commercial"}
    records[3].raw_data["description"] = "AUTOHAUS inventory"
    records[4].raw_data["vehicle"]["mileage"] = 200001
    return tuple(records)


def _normalize_and_filter(
    listings: tuple[RawMarketplaceListing, ...],
    filter_: BasicDealFilter,
) -> tuple[int, int]:
    """Normalize a raw batch and return normalized and passed counts.

    Args:
        listings: Deduplicated raw listings eligible for normalization.
        filter_: Configured deterministic filter.

    Returns:
        Tuple containing normalized and passed listing counts.
    """
    normalized = ApifyKleinanzeigenNormalizer().normalize_batch(listings)
    filtered = filter_.filter_batch(
        normalized.listings,
        tuple(result.warnings for result in normalized.results),
    )
    return normalized.normalized_count, filtered.passed_count


def main() -> None:
    """Run both fixture passes and print safe count-only verification output."""
    config = load_config(PROJECT_ROOT / "config" / "autofinder.yaml")
    raw = _representative_batch()
    with TemporaryDirectory(prefix="autofinder-normalization-") as directory:
        repository = JsonSeenListingRepository(Path(directory) / "seen_listings.json")
        deduplicator = EarlyDeduplicator(repository)
        filter_ = BasicDealFilter(config.filters)
        first = deduplicator.filter_new(raw)
        first_normalized, first_passed = _normalize_and_filter(first.new_listings, filter_)
        second = deduplicator.filter_new(raw)
        second_normalized, second_passed = _normalize_and_filter(second.new_listings, filter_)
    print(
        "first_pass raw=5 unseen=%s normalized=%s passed=%s rejected=%s"
        % (first.new_count, first_normalized, first_passed, first_normalized - first_passed)
    )
    print(
        "second_pass raw=5 unseen=%s normalized=%s passed=%s"
        % (second.new_count, second_normalized, second_passed)
    )


if __name__ == "__main__":
    main()
