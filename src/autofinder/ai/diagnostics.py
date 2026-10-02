"""Safe provider-error extraction without serializing requests or credentials."""

from __future__ import annotations

import re
from typing import Any

_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"\b(?:gsk_|AIza)[A-Za-z0-9_-]+"),
)


def safe_message(value: Any) -> str:
    """Return a bounded diagnostic message with common credential forms redacted."""
    message = str(value).replace("\n", " ").replace("\r", " ")
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub(r"\1[redacted]" if pattern.groups >= 1 else "[redacted]", message)
    return message[:300] or "Provider returned no diagnostic message."


def safe_code(value: Any) -> str | None:
    """Keep only short scalar machine-readable codes."""
    text = str(value).strip() if value is not None else ""
    return text[:80] if text and re.fullmatch(r"[A-Za-z0-9_.-]+", text) else None


def error_details(error: Any) -> tuple[int | None, str | None, str]:
    """Extract safe HTTP/provider codes and a redacted message from an SDK error."""
    status_code = getattr(error, "status_code", getattr(error, "code", None))
    status_code = status_code if isinstance(status_code, int) else None
    body = getattr(error, "body", None)
    details = getattr(error, "details", None)
    payload = body if isinstance(body, dict) else details if isinstance(details, dict) else {}
    nested = payload.get("error", payload) if isinstance(payload, dict) else {}
    provider_code = safe_code(nested.get("code") or nested.get("type") or getattr(error, "status", None)) if isinstance(nested, dict) else safe_code(getattr(error, "status", None))
    return status_code, provider_code, safe_message(getattr(error, "message", error))
