"""Safe, append-only audit record contracts for daily diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuditRecord:
    """One privacy-safe, already-decided listing outcome for daily reporting."""

    schema_version: int
    recorded_at: str
    local_date: str
    run_id: str
    listing_key: str
    outcome: str
    stage: str
    listing: dict[str, Any]
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    analysis: dict[str, Any] | None = None
    repair: dict[str, Any] | None = None
    valuation: dict[str, Any] | None = None
    financial: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None
    failure: dict[str, str] | None = None
    diagnostics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe data without provider payloads or credentials."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditRecord":
        """Rebuild a validated-shape record while tolerating future extra keys."""
        return cls(
            schema_version=int(payload.get("schema_version", 1)),
            recorded_at=str(payload["recorded_at"]),
            local_date=str(payload["local_date"]),
            run_id=str(payload["run_id"]),
            listing_key=str(payload["listing_key"]),
            outcome=str(payload["outcome"]),
            stage=str(payload["stage"]),
            listing=dict(payload.get("listing") or {}),
            reasons=tuple(str(value) for value in payload.get("reasons") or ()),
            warnings=tuple(str(value) for value in payload.get("warnings") or ()),
            analysis=_optional_mapping(payload.get("analysis")),
            repair=_optional_mapping(payload.get("repair")),
            valuation=_optional_mapping(payload.get("valuation")),
            financial=_optional_mapping(payload.get("financial")),
            evaluation=_optional_mapping(payload.get("evaluation")),
            failure=_optional_string_mapping(payload.get("failure")),
            diagnostics=_optional_mapping(payload.get("diagnostics")),
        )


def _optional_mapping(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _optional_string_mapping(value: object) -> dict[str, str] | None:
    return {str(key): str(item) for key, item in value.items()} if isinstance(value, dict) else None
