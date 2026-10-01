"""Tests for Telegram client and development-report formatting without network calls."""

import json
from urllib.error import URLError
from urllib.request import Request

import pytest

from autofinder.core.exceptions import TelegramError
from autofinder.notifications.development_reporter import DevelopmentReport, DevelopmentReporter
from autofinder.notifications.telegram import TelegramClient, TelegramSettings


def test_client_constructs_text_request_without_network() -> None:
    """An injected transport receives the expected Telegram payload."""
    captured: list[Request] = []

    def transport(request: Request, timeout: float) -> None:
        captured.append(request)
        assert timeout == 10.0

    client = TelegramClient(TelegramSettings("fake-token", "123"), transport=transport)
    client.send_text("Foundation complete")
    assert len(captured) == 1
    assert json.loads(captured[0].data.decode("utf-8")) == {"chat_id": "123", "text": "Foundation complete"}


def test_client_surfaces_delivery_failure_without_secret(caplog: pytest.LogCaptureFixture) -> None:
    """Transport errors become useful domain errors and do not log credentials."""
    def failing_transport(request: Request, timeout: float) -> None:
        raise URLError("offline")

    client = TelegramClient(TelegramSettings("sensitive-token", "456"), transport=failing_transport)
    with pytest.raises(TelegramError, match="delivery failed"):
        client.send_text("test")
    assert "sensitive-token" not in caplog.text


def test_development_reporter_formats_required_summary() -> None:
    """Development reports keep reusable structured information intact."""
    report = DevelopmentReport("Project Foundation", "✅ Completed", ("Logging", "Tests"), 8, 0, "abc123", "Collector")
    text = DevelopmentReporter.format(report)
    assert "Step: Project Foundation" in text
    assert "• 8 passed" in text
    assert "Git:\nabc123" in text
