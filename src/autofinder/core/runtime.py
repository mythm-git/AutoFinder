"""Central project-root runtime environment loading and secret retrieval."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from autofinder.core.exceptions import ConfigurationError, RuntimeCredentialError


ENVIRONMENT_FILE_NAME = ".env"

CONFIGURATION_RELATIVE_PATH = Path("config") / "autofinder.yaml"


def resolve_project_root() -> Path:
    """Resolve the local project root without hard-coding a user-specific path.

    An explicit ``AUTOFINDER_PROJECT_ROOT`` supports n8n and installed execution.
    Source-tree resolution is preferred for development; an upward configuration-file
    search is only a fallback for a local invocation launched beneath the project.
    """
    explicit = os.getenv("AUTOFINDER_PROJECT_ROOT", "").strip()
    candidates = [Path(explicit)] if explicit else []
    candidates.append(Path(__file__).resolve().parents[3])
    candidates.extend((Path.cwd(), *Path.cwd().parents))
    for candidate in candidates:
        root = candidate.resolve()
        if (root / CONFIGURATION_RELATIVE_PATH).is_file():
            return root
    raise ConfigurationError("Could not resolve an AutoFinder project root with config/autofinder.yaml.")


def load_project_environment(project_root: Path) -> None:
    """Load exactly ``project_root/.env`` without relying on discovery or the CWD.

    Missing files are allowed until a service requests a required credential. Existing
    process variables take precedence, which supports n8n and deployment injection.
    """
    root = project_root.resolve()
    load_dotenv(dotenv_path=root / ENVIRONMENT_FILE_NAME, override=False)


def required_environment_value(name: str) -> str:
    """Return one non-empty runtime value without ever including it in an error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeCredentialError(f"{name} is not configured.")
    return value
