"""Stable early listing identity and duplicate-detection layer."""

from autofinder.deduplication.json_repository import JsonSeenListingRepository
from autofinder.deduplication.service import EarlyDeduplicator

__all__ = ["EarlyDeduplicator", "JsonSeenListingRepository"]
