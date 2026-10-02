"""Minimal executable foundation for AutoFinder v2."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from autofinder.core.config import load_config
from autofinder.core.logging import configure_logging
from autofinder.core.runtime import load_project_environment, resolve_project_root

PROJECT_ROOT = resolve_project_root()


def main() -> int:
    """Start the foundation application, validate configuration, then exit cleanly.

    Returns:
        ``0`` on successful foundation startup; configuration errors propagate to
        make startup failures visible to the scheduler.
    """
    load_project_environment(PROJECT_ROOT)
    logging_settings = _load_logging_settings(PROJECT_ROOT / "config" / "logging.yaml")
    logger = configure_logging(
        PROJECT_ROOT / "logs",
        level=logging_settings["level"],
        max_bytes=logging_settings["max_bytes"],
        backup_count=logging_settings["backup_count"],
    )
    config = load_config(PROJECT_ROOT / "config" / "autofinder.yaml")
    logger.info("AutoFinder v2 started.")
    logger.info(
        "Foundation configuration: marketplace=%s postal_code=%s radius_km=%s interval_minutes=%s listings_per_run=%s",
        config.search.marketplace,
        config.search.postal_code,
        config.search.radius_km,
        config.scheduler.interval_minutes,
        config.collection.listings_per_run,
    )
    logger.info("No runtime pipeline has been implemented yet.")
    return 0


def _load_logging_settings(path: Path) -> dict[str, object]:
    """Load small logging-only YAML settings with a clear validation boundary."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    settings = payload.get("logging") if isinstance(payload, dict) else None
    if not isinstance(settings, dict):
        raise ValueError("logging.yaml must contain a logging mapping")
    required = ("level", "max_bytes", "backup_count")
    if any(key not in settings for key in required):
        raise ValueError("logging.yaml is missing required settings")
    return settings
