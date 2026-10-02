"""Secret-loading helpers that never return credentials in errors or logs."""

from __future__ import annotations

from autofinder.core.exceptions import AIConfigurationError, RuntimeCredentialError
from autofinder.core.runtime import required_environment_value


def load_api_key(name: str) -> str:
    """Retrieve one already-loaded project runtime credential without discovery."""
    try:
        return required_environment_value(name)
    except RuntimeCredentialError as error:
        raise AIConfigurationError(str(error)) from error
