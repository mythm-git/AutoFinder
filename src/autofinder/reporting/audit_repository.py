"""Filesystem-backed append-only audit persistence with local-day partitioning."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from autofinder.reporting.audit_models import AuditRecord


class JsonlAuditRepository:
    """Persist safe records as UTF-8 JSONL, one file per configured local day."""

    def __init__(self, directory: Path, timezone: str) -> None:
        self._directory = directory
        self._timezone = ZoneInfo(timezone)
        self._logger = logging.getLogger("autofinder.reporting.audit")

    def append(self, record: AuditRecord) -> None:
        """Append one already-sanitized record atomically enough for sequential runs."""
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for_date(record.local_date)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
        self._logger.info("Audit record persisted: outcome=%s listing=%s", record.outcome, record.listing_key)

    def records_for_date(self, local_date: str) -> list[AuditRecord]:
        """Read valid records for one local date; malformed lines are safely skipped."""
        path = self.path_for_date(local_date)
        if not path.exists():
            return []
        records: list[AuditRecord] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(AuditRecord.from_dict(json.loads(line)))
            except (TypeError, ValueError, json.JSONDecodeError, KeyError):
                self._logger.warning("Ignoring malformed audit line: file=%s line=%s", path.name, line_number)
        return records

    def path_for_date(self, local_date: str) -> Path:
        """Return the deterministic date-partitioned JSONL path."""
        return self._directory / f"{local_date}.jsonl"

    def local_now(self) -> datetime:
        """Return a timezone-aware time for deterministic clock injection in tests."""
        return datetime.now(self._timezone)
