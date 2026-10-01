"""Stable marketplace listing identity model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListingIdentity:
    """Stable identity based only on marketplace and external listing ID.

    Attributes:
        marketplace: Normalized marketplace identifier.
        external_listing_id: Marketplace-assigned stable listing identifier.
    """

    marketplace: str
    external_listing_id: str

    @property
    def canonical_key(self) -> str:
        """Return the repository key, for example ``kleinanzeigen:3521306041``."""
        return f"{self.marketplace}:{self.external_listing_id}"
