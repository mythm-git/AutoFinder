"""Tests for typed configuration loading and validation."""

from pathlib import Path

import pytest

from autofinder.core.config import load_config
from autofinder.core.exceptions import ConfigurationError


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "autofinder.yaml"


def test_loads_expected_foundation_configuration() -> None:
    """The committed non-secret foundation configuration validates."""
    config = load_config(CONFIG_PATH)
    assert config.scheduler.interval_minutes == 45
    assert config.search.postal_code == "27449"
    assert config.collection.max_new_listings_per_run == 5
    assert config.collection.acquisition_batch_size == 20
    assert config.apify.actor_id == "rKEiEgI8vfyKcaBUj"
    assert config.apify.timeout_seconds == 120


def test_rejects_collection_batch_smaller_than_new_listing_limit(tmp_path: Path) -> None:
    """Invalid collection semantics fail clearly rather than silently proceeding."""
    config = CONFIG_PATH.read_text(encoding="utf-8").replace("acquisition_batch_size: 20", "acquisition_batch_size: 4")
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(config, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="acquisition_batch_size"):
        load_config(invalid)


def test_env_is_ignored_and_example_contains_names_only() -> None:
    """Repository policy protects the real local secrets file by path."""
    root = CONFIG_PATH.parents[1]
    assert ".env" in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert (root / ".env.example").read_text(encoding="utf-8").splitlines() == [
        "TELEGRAM_BOT_TOKEN=", "TELEGRAM_CHAT_ID=", "APIFY_API_TOKEN=", "GROQ_API_KEY=", "GEMINI_API_KEY=",
    ]
