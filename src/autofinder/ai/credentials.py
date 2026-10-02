"""Secret-loading helpers that never return credentials in errors or logs."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from autofinder.core.exceptions import AIConfigurationError


def load_api_key(name: str) -> str:
    """Load one required provider credential from environment or the local ignored file."""
    load_dotenv()
    value = os.getenv(name, "").strip()
    if not value:
        raise AIConfigurationError(f"{name} is not configured.")
    return value
