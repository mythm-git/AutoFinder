"""Apify-backed Kleinanzeigen acquisition with raw-evidence preservation.

The actor payload is intentionally limited to the actor's verified input schema:
``searchUrl`` and ``maxItems``. Returned marketplace fields remain untouched for
later normalization, validation, and duplicate detection.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from autofinder.collectors.base import ListingCollector
from autofinder.core.config import ApifyConfig, CollectionConfig, SearchConfig
from autofinder.core.exceptions import ApifyConfigurationError, ApifyTransportError, CollectorError
from autofinder.models.collection import CollectionResult, RawMarketplaceListing


class ApifyTransport(Protocol):
    """Small JSON transport boundary for Apify, enabling network-free tests."""

    def request(self, method: str, path: str, payload: dict[str, Any] | None, timeout_seconds: float) -> Any:
        """Return decoded JSON from an Apify API request."""


class UrllibApifyTransport:
    """Apify JSON transport that keeps the credential in an authorization header."""

    def __init__(self, token: str) -> None:
        """Store a non-empty token for use only in HTTP request headers."""
        self._token = token

    def request(self, method: str, path: str, payload: dict[str, Any] | None, timeout_seconds: float) -> Any:
        """Execute one JSON Apify request without logging secret-bearing details.

        Raises:
            ApifyTransportError: If networking, HTTP status, or JSON decoding fails.
        """
        request = Request(
            f"https://api.apify.com/v2{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json", "Accept": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 -- fixed Apify API origin
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise ApifyTransportError(f"Apify request failed: {type(error).__name__}") from error


class ApifyKleinanzeigenCollector(ListingCollector):
    """Collect raw Kleinanzeigen items from one verified configurable Apify actor."""

    def __init__(self, search: SearchConfig, collection: CollectionConfig, apify: ApifyConfig, transport: ApifyTransport | None = None) -> None:
        """Create a collector with non-secret configuration and injectable transport.

        Args:
            search: Configured marketplace search scope and exact search URL.
            collection: Configured future throughput and acquisition batch limits.
            apify: Actor ID and end-to-end collection timeout.
            transport: Optional test transport; production loads APIFY_API_TOKEN.

        Raises:
            ApifyConfigurationError: If used with a non-Kleinanzeigen search or a
                required local credential is unavailable.
        """
        if search.marketplace != "kleinanzeigen":
            raise ApifyConfigurationError("ApifyKleinanzeigenCollector requires marketplace 'kleinanzeigen'.")
        self._search = search
        self._collection = collection
        self._apify = apify
        self._transport = transport or UrllibApifyTransport(_load_apify_token())
        self._logger = logging.getLogger("autofinder.collectors.apify_kleinanzeigen")

    def collect(self) -> CollectionResult:
        """Run the configured actor and retrieve its raw default dataset.

        Returns:
            Raw listing evidence and validated safe run metadata.

        Raises:
            CollectorError: If the request is invalid, the actor fails/times out, or
                its run/dataset response cannot be validated.
        """
        limit = self._collection.listings_per_run
        self._logger.info("Apify collection started: marketplace=%s requested_count=%s postal_code=%s radius_km=%s", self._search.marketplace, limit, self._search.postal_code, self._search.radius_km)
        run = self._start_and_wait(limit)
        run_data = _mapping(run, "Apify run response")
        status = _nonempty_text(run_data.get("status"), "Apify run status")
        run_id = _nonempty_text(run_data.get("id"), "Apify run ID")
        if status != "SUCCEEDED":
            self._logger.error("Apify actor did not succeed: status=%s", status)
            raise CollectorError(f"Apify actor completed without success: {status}")
        dataset_id = _nonempty_text(run_data.get("defaultDatasetId"), "Apify default dataset ID")
        dataset = self._transport.request("GET", f"/datasets/{quote(dataset_id, safe='')}/items?limit={limit}", None, self._apify.timeout_seconds)
        if not isinstance(dataset, list):
            self._logger.error("Apify dataset response was malformed.")
            raise CollectorError("Apify dataset response must be a JSON array.")
        now = datetime.now(UTC)
        listings = tuple(RawMarketplaceListing(self._search.marketplace, item, now) for item in dataset if isinstance(item, dict))
        if len(listings) != len(dataset):
            self._logger.error("Apify dataset contained a non-object listing item.")
            raise CollectorError("Apify dataset contains an invalid listing item.")
        if not listings:
            self._logger.warning("Apify collection completed with zero items.")
        self._logger.info("Apify collection completed: received_count=%s actor_status=%s", len(listings), status)
        return CollectionResult(self._search.marketplace, limit, len(listings), now, listings, run_id, status)

    def _start_and_wait(self, limit: int) -> dict[str, Any]:
        """Start one actor run and poll only if Apify's initial wait is insufficient."""
        payload = {"searchUrl": self._search.search_url, "maxItems": limit}
        initial_wait = min(self._apify.timeout_seconds, 60)
        response = self._transport.request("POST", f"/acts/{quote(self._apify.actor_id, safe='')}/runs?waitForFinish={initial_wait}", payload, self._apify.timeout_seconds)
        run = _mapping(_mapping(response, "Apify run wrapper").get("data"), "Apify run data")
        deadline = time.monotonic() + self._apify.timeout_seconds
        while _nonempty_text(run.get("status"), "Apify run status") in {"READY", "RUNNING"}:
            if time.monotonic() >= deadline:
                self._logger.error("Apify actor wait timed out.")
                raise CollectorError("Apify actor timed out before completion.")
            time.sleep(min(2.0, max(0.0, deadline - time.monotonic())))
            run_id = _nonempty_text(run.get("id"), "Apify run ID")
            response = self._transport.request("GET", f"/actor-runs/{quote(run_id, safe='')}", None, self._apify.timeout_seconds)
            run = _mapping(_mapping(response, "Apify run wrapper").get("data"), "Apify run data")
        return run


def _load_apify_token() -> str:
    """Load the local Apify credential without emitting its value.

    Raises:
        ApifyConfigurationError: If APIFY_API_TOKEN is absent or blank.
    """
    load_dotenv()
    token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not token:
        raise ApifyConfigurationError("APIFY_API_TOKEN is not configured.")
    return token


def _mapping(value: Any, label: str) -> dict[str, Any]:
    """Validate an API object without including untrusted content in exceptions."""
    if not isinstance(value, dict):
        raise CollectorError(f"{label} must be a JSON object.")
    return value


def _nonempty_text(value: Any, label: str) -> str:
    """Validate a non-empty API text field without echoing its untrusted value."""
    if not isinstance(value, str) or not value.strip():
        raise CollectorError(f"{label} is missing or invalid.")
    return value
