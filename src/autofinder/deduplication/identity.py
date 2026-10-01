"""Minimal identity extraction from raw Apify/Kleinanzeigen records."""

from __future__ import annotations

from typing import Any

from autofinder.core.exceptions import IdentityError
from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.identity import ListingIdentity


def extract_listing_identity(listing: RawMarketplaceListing) -> ListingIdentity:
    """Extract the stable Kleinanzeigen listing ID from the verified raw ``id`` field.

    Args:
        listing: Raw record received from the marketplace collector.

    Returns:
        Marketplace plus external listing ID identity.

    Raises:
        IdentityError: If the listing lacks a usable source ``id`` field.
    """
    external_id = listing.raw_data.get("id")
    if isinstance(external_id, int):
        external_id = str(external_id)
    if not isinstance(external_id, str) or not external_id.strip():
        raise IdentityError("Listing has no usable external listing ID.")
    normalized_id = external_id.strip()
    marketplace = listing.marketplace.strip().lower()
    if not normalized_id.isdigit() or not marketplace:
        raise IdentityError("Listing external listing ID or marketplace is malformed.")
    return ListingIdentity(marketplace, normalized_id)
