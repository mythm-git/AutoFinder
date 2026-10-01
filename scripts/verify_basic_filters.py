"""Verify deterministic filtering locally with sanitized fixture-derived listings."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from autofinder.core.config import load_config
from autofinder.core.logging import configure_logging
from autofinder.filters.basic import BasicDealFilter
from autofinder.models.collection import RawMarketplaceListing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json"


def _listing(identifier: str) -> RawMarketplaceListing:
    """Build a fresh safe listing that retains the representative raw structure."""
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    raw["id"] = identifier
    return RawMarketplaceListing("kleinanzeigen", raw, datetime.now(UTC))


def main() -> int:
    """Run a five-record deterministic fixture demonstration without network access."""
    config = load_config(PROJECT_ROOT / "config" / "autofinder.yaml")
    configure_logging(PROJECT_ROOT / "logs")
    valid = _listing("1")
    expensive = _listing("2")
    expensive.raw_data["price"] = config.filters.price.maximum + 1
    dealer = _listing("3")
    dealer.raw_data["seller"] = {"type": "dealer"}
    dealer_text = _listing("4")
    dealer_text.raw_data["description"] = config.filters.dealer_text_indicators[0]
    high_mileage = _listing("5")
    high_mileage.raw_data["vehicle"]["mileage"] = config.filters.mileage.maximum + 1
    batch = BasicDealFilter(config.filters).filter_batch((valid, expensive, dealer, dealer_text, high_mileage))
    print(f"Fixture filter verification: received={batch.received_count} passed={batch.passed_count} rejected={batch.rejected_count}")
    print("Reasons: " + ", ".join(f"{reason.value}={count}" for reason, count in sorted(batch.rejection_reason_counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
