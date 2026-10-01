"""Atomic local JSON persistence for v0.1 seen-listing state."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autofinder.core.exceptions import SeenStateError
from autofinder.deduplication.base import SeenListingRepository
from autofinder.models.identity import ListingIdentity


class JsonSeenListingRepository(SeenListingRepository):
    """Persist minimal identity metadata in an atomically replaced JSON state file.

    V0.1 expects a single local runtime instance. Atomic replacement prevents
    partial files on interruption; stronger cross-process locking can be added
    behind this repository contract if future scheduling requires it.
    """

    STATE_VERSION = 1

    def __init__(self, state_file: Path) -> None:
        """Create a repository targeting a project-relative resolved state path.

        Args:
            state_file: Local JSON state destination. Parent directories are created
                only when the first state write occurs.
        """
        self._state_file = state_file
        self._logger = logging.getLogger("autofinder.deduplication.json_repository")

    def contains(self, identity: ListingIdentity) -> bool:
        """Return whether the atomic state currently contains an identity.

        Raises:
            SeenStateError: If existing state is corrupted or has an invalid schema.
        """
        return identity.canonical_key in self._read_state()["listings"]

    def mark_seen(self, identity: ListingIdentity, first_seen_at: datetime) -> None:
        """Persist a previously unseen identity without overwriting its first-seen time.

        Raises:
            SeenStateError: If state cannot be validated or written safely.
        """
        state = self._read_state()
        key = identity.canonical_key
        if key in state["listings"]:
            return
        timestamp = _utc_timestamp(first_seen_at)
        state["listings"][key] = {
            "marketplace": identity.marketplace,
            "external_listing_id": identity.external_listing_id,
            "first_seen_at": timestamp,
        }
        self._write_state_atomic(state)
        self._logger.debug("Persisted seen listing identity: %s", key)

    def _read_state(self) -> dict[str, Any]:
        """Read and strictly validate local state, never silently resetting it."""
        if not self._state_file.exists():
            return {"version": self.STATE_VERSION, "listings": {}}
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self._logger.error("Seen-listing state is unreadable or corrupted: %s", type(error).__name__)
            raise SeenStateError("Seen-listing state is unreadable or corrupted; it was preserved.") from error
        return _validate_state(payload)

    def _write_state_atomic(self, state: dict[str, Any]) -> None:
        """Write validated state to a sibling temp file then atomically replace it."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self._state_file.parent, prefix=f".{self._state_file.stem}.", suffix=".tmp", delete=False) as handle:
                temporary_path = Path(handle.name)
                json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self._state_file)
        except OSError as error:
            self._logger.error("Seen-listing state write failed: %s", type(error).__name__)
            raise SeenStateError("Seen-listing state could not be written safely.") from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError as error:
                    self._logger.warning("Could not clean temporary seen-state file: %s", type(error).__name__)


def _validate_state(payload: Any) -> dict[str, Any]:
    """Validate versioned minimal state without exposing arbitrary file content."""
    if not isinstance(payload, dict) or payload.get("version") != JsonSeenListingRepository.STATE_VERSION or not isinstance(payload.get("listings"), dict):
        raise SeenStateError("Seen-listing state schema is invalid; it was preserved.")
    for key, metadata in payload["listings"].items():
        if not isinstance(key, str) or not isinstance(metadata, dict):
            raise SeenStateError("Seen-listing state schema is invalid; it was preserved.")
        marketplace = metadata.get("marketplace")
        external_id = metadata.get("external_listing_id")
        first_seen_at = metadata.get("first_seen_at")
        if not all(isinstance(value, str) and value for value in (marketplace, external_id, first_seen_at)):
            raise SeenStateError("Seen-listing state schema is invalid; it was preserved.")
        if key != f"{marketplace}:{external_id}":
            raise SeenStateError("Seen-listing state identity key is invalid; it was preserved.")
    return payload


def _utc_timestamp(value: datetime) -> str:
    """Convert an aware datetime to unambiguous UTC ISO-8601 text.

    Raises:
        SeenStateError: If a caller supplies an ambiguous naive datetime.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise SeenStateError("first_seen_at must be timezone-aware.")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
