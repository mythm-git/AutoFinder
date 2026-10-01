"""Verify early deduplication locally using only the sanitized fixture data."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from autofinder.core.logging import configure_logging
from autofinder.deduplication.json_repository import JsonSeenListingRepository
from autofinder.deduplication.service import EarlyDeduplicator
from autofinder.models.collection import RawMarketplaceListing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json"


def _listing(identifier: str) -> RawMarketplaceListing:
    """Build one safe fixture-derived listing with a unique source ID."""
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    raw["id"] = identifier
    raw["url"] = f"https://www.kleinanzeigen.de/s-anzeige/fixture/{identifier}"
    return RawMarketplaceListing("kleinanzeigen", raw, datetime.now(UTC))


def main() -> int:
    """Demonstrate 5-new, 0-new, then 2-new behavior without external calls."""
    configure_logging(PROJECT_ROOT / "logs")
    cache_directory = PROJECT_ROOT / "data" / "cache"
    cache_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache_directory, prefix="dedup-verification-") as directory:
        deduplicator = EarlyDeduplicator(JsonSeenListingRepository(Path(directory) / "seen_listings.json"))
        first = deduplicator.filter_new(tuple(_listing(str(index)) for index in range(1, 6)))
        second = deduplicator.filter_new(tuple(_listing(str(index)) for index in range(1, 6)))
        mixed = deduplicator.filter_new(tuple(_listing(str(index)) for index in (1, 2, 3, 6, 7)))
    print(f"First pass: received={first.received_count} new={first.new_count}")
    print(f"Second pass: received={second.received_count} new={second.new_count}")
    print(f"Mixed pass: received={mixed.received_count} new={mixed.new_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
