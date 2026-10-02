"""Tests for explicit project-root runtime environment loading without real secrets."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from autofinder.ai.credentials import load_api_key
from autofinder.core.exceptions import AIConfigurationError, RuntimeCredentialError, TelegramError
from autofinder.core.runtime import load_project_environment, required_environment_value, resolve_project_root
from autofinder.notifications.telegram import TelegramClient


FAKE_GROQ = "test-groq-secret"
FAKE_GEMINI = "test-gemini-secret"
FAKE_TELEGRAM = "test-telegram-secret"


def _write_test_env(root: Path) -> None:
    (root / ".env").write_text(
        "\n".join((
            f"GROQ_API_KEY={FAKE_GROQ}",
            f"GEMINI_API_KEY={FAKE_GEMINI}",
            f"TELEGRAM_BOT_TOKEN={FAKE_TELEGRAM}",
            "TELEGRAM_CHAT_ID=123456",
            "APIFY_API_TOKEN=test-apify-secret",
        )),
        encoding="utf-8",
    )


def test_project_root_env_load_is_independent_of_current_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, elsewhere = tmp_path / "project", tmp_path / "elsewhere"
    root.mkdir()
    elsewhere.mkdir()
    _write_test_env(root)
    for name in ("GROQ_API_KEY", "GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "APIFY_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(elsewhere)
    load_project_environment(root)
    assert load_api_key("GROQ_API_KEY") == FAKE_GROQ
    assert load_api_key("GEMINI_API_KEY") == FAKE_GEMINI
    client = TelegramClient.from_project_environment(root)
    assert client._settings.chat_id == "123456"  # noqa: SLF001 -- verifies central loader wiring only



def test_explicit_project_root_resolves_when_cwd_is_unrelated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, elsewhere = tmp_path / "project", tmp_path / "elsewhere"
    (root / "config").mkdir(parents=True)
    (root / "config" / "autofinder.yaml").write_text("test", encoding="utf-8")
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("AUTOFINDER_PROJECT_ROOT", str(root))
    assert resolve_project_root() == root.resolve()


def test_missing_project_env_and_individual_credential_fail_safely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GROQ_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(name, raising=False)
    load_project_environment(tmp_path)
    with pytest.raises(RuntimeCredentialError, match="GROQ_API_KEY") as missing:
        required_environment_value("GROQ_API_KEY")
    assert "test-groq-secret" not in str(missing.value)
    with pytest.raises(AIConfigurationError, match="GROQ_API_KEY"):
        load_api_key("GROQ_API_KEY")
    with pytest.raises(TelegramError, match="TELEGRAM_BOT_TOKEN"):
        TelegramClient.from_project_environment(tmp_path)


def test_runtime_loader_and_errors_never_log_or_print_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _write_test_env(root)
    for name in ("GROQ_API_KEY", "GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "APIFY_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with caplog.at_level(logging.DEBUG):
        load_project_environment(root)
        load_api_key("GROQ_API_KEY")
        TelegramClient.from_project_environment(root)
    captured = capsys.readouterr()
    output = captured.out + captured.err + caplog.text
    assert FAKE_GROQ not in output and FAKE_GEMINI not in output and FAKE_TELEGRAM not in output
