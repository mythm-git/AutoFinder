"""Stable raw-marketplace collection models.

These models deliberately retain raw source evidence. Normalization and business
rules belong to later stages and must not discard fields collected by Apify.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RawMarketplaceListing:
    """One raw marketplace record with source and collection provenance.

    Attributes:
        marketplace: Source marketplace identifier.
        raw_data: Lossless Apify dataset item for later normalization.
        collected_at: UTC timestamp when AutoFinder received this item.
    """

    marketplace: str
    raw_data: dict[str, Any]
    collected_at: datetime


@dataclass(frozen=True)
class CollectionResult:
    """Immutable summary and raw evidence from a single collector invocation.

    Attributes:
        marketplace: Marketplace requested from the collector.
        requested_count: Dataset item limit supplied to the actor.
        received_count: Number of raw records returned by Apify.
        collected_at: UTC completion timestamp.
        listings: Raw source records, kept intact for later stages.
        actor_run_id: Apify run ID for safe operational correlation.
        actor_status: Terminal Apify actor run status.
    """

    marketplace: str
    requested_count: int
    received_count: int
    collected_at: datetime
    listings: tuple[RawMarketplaceListing, ...]
    actor_run_id: str
    actor_status: str
