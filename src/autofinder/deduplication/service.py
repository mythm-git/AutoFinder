"""Early, cheap identity-based duplicate rejection for collected listings."""

from __future__ import annotations

import logging

from autofinder.deduplication.base import SeenListingRepository
from autofinder.deduplication.identity import extract_listing_identity
from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.deduplication import DeduplicationResult
from autofinder.core.exceptions import IdentityError


class EarlyDeduplicator:
    """Mark valid unseen listings immediately and return only those raw records."""

    def __init__(self, repository: SeenListingRepository) -> None:
        """Attach the persistence abstraction used for seen-state checks."""
        self._repository = repository
        self._logger = logging.getLogger("autofinder.deduplication.service")

    def filter_new(self, listings: tuple[RawMarketplaceListing, ...]) -> DeduplicationResult:
        """Classify one collected batch while preventing same-batch duplicates.

        Valid unseen listings are persisted before they reach later business stages.
        Listings without a stable identity fail closed and are not returned.
        """
        self._logger.info("Early deduplication started: received_count=%s", len(listings))
        new_listings: list[RawMarketplaceListing] = []
        batch_keys: set[str] = set()
        previously_seen = invalid_identity = duplicate_batch = 0
        for listing in listings:
            try:
                identity = extract_listing_identity(listing)
            except IdentityError:
                invalid_identity += 1
                self._logger.warning("Skipping listing with invalid stable identity.")
                continue
            if identity.canonical_key in batch_keys:
                duplicate_batch += 1
                self._logger.warning("Skipping duplicate listing within batch: %s", identity.canonical_key)
                continue
            batch_keys.add(identity.canonical_key)
            if self._repository.contains(identity):
                previously_seen += 1
                self._logger.debug("Skipping previously seen listing: %s", identity.canonical_key)
                continue
            self._repository.mark_seen(identity, listing.collected_at)
            new_listings.append(listing)
        result = DeduplicationResult(len(listings), len(new_listings), previously_seen, invalid_identity, duplicate_batch, tuple(new_listings))
        self._logger.info("Early deduplication completed: new_count=%s previously_seen=%s invalid_identity=%s duplicate_within_batch=%s", result.new_count, result.previously_seen_count, result.invalid_identity_count, result.duplicate_within_batch_count)
        return result
