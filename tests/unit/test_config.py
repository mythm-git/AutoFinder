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
    assert config.collection.listings_per_run == 5
    assert config.apify.actor_id == "rKEiEgI8vfyKcaBUj"
    assert config.apify.timeout_seconds == 120
    assert config.deduplication.state_file == "data/state/seen_listings.json"
    assert config.filters.mileage.minimum == 0
    assert config.filters.mileage.maximum == 200000
    assert "autohaus" in config.filters.dealer_text_indicators
    assert config.telegram.runtime_summary_enabled is True
    assert config.telegram.candidate_alerts_enabled is True
    assert config.telegram.max_list_items == 4
    assert config.deal_evaluation.minimum_expected_roi_percent == 20
    assert config.deal_evaluation.minimum_conservative_roi_for_strong_percent == 0
    assert config.deal_evaluation.maximum_risk_for_strong.value == "medium"
    assert config.deal_evaluation.reject_very_high_risk is True


def test_rejects_nonpositive_listings_per_run(tmp_path: Path) -> None:
    """The configured bounded request size must remain positive."""
    config = CONFIG_PATH.read_text(encoding="utf-8").replace("listings_per_run: 5", "listings_per_run: 0")
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(config, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="listings_per_run"):
        load_config(invalid)


def test_rejects_invalid_telegram_reporting_bound(tmp_path: Path) -> None:
    """Runtime presentation remains intentionally concise and configurable."""
    config = CONFIG_PATH.read_text(encoding="utf-8").replace("max_list_items: 4", "max_list_items: 11")
    invalid = tmp_path / "invalid-telegram.yaml"
    invalid.write_text(config, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="telegram.max_list_items"):
        load_config(invalid)


def test_env_is_ignored_and_example_contains_names_only() -> None:
    """Repository policy protects the real local secrets file by path."""
    root = CONFIG_PATH.parents[1]
    assert ".env" in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert (root / ".env.example").read_text(encoding="utf-8").splitlines() == [
        "TELEGRAM_BOT_TOKEN=", "TELEGRAM_CHAT_ID=", "APIFY_API_TOKEN=", "GROQ_API_KEY=", "GEMINI_API_KEY=",
    ]
