"""Stable data models shared across AutoFinder components."""

from autofinder.models.collection import CollectionResult, RawMarketplaceListing
from autofinder.models.deduplication import DeduplicationResult
from autofinder.models.identity import ListingIdentity

__all__ = ["CollectionResult", "DeduplicationResult", "ListingIdentity", "RawMarketplaceListing"]
