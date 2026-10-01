"""Reusable Telegram Bot API client with secret-safe errors and logging."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from autofinder.core.exceptions import TelegramError


class TelegramTransport(Protocol):
    """Protocol enabling deterministic tests without real Telegram requests."""

    def __call__(self, request: Request, timeout: float) -> None:
        """Send a prepared request or raise a network exception."""


@dataclass(frozen=True)
class TelegramSettings:
    """Non-printable Telegram destination settings loaded from environment."""

    bot_token: str
    chat_id: str


class TelegramClient:
    """Small shared Telegram text-message client for development and runtime reporters."""

    def __init__(self, settings: TelegramSettings, timeout_seconds: float = 10.0, transport: TelegramTransport | None = None) -> None:
        """Create a client using injected settings and optionally a test transport."""
        self._settings = settings
        self._timeout_seconds = timeout_seconds
        self._transport = transport or _send_request
        self._logger = logging.getLogger("autofinder.notifications.telegram")

    @classmethod
    def from_environment(cls) -> "TelegramClient":
        """Create a client from local ``.env``/environment values.

        Raises:
            TelegramError: If required credential names are missing or blank.
        """
        load_dotenv()
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            raise TelegramError("Telegram is not configured: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required.")
        return cls(TelegramSettings(bot_token=token, chat_id=chat_id))

    def send_text(self, text: str, parse_mode: str | None = None) -> None:
        """Send one bounded non-empty text message.

        Args:
            text: Plain text or safely constructed Markdown message.
            parse_mode: Optional Telegram mode, such as ``MarkdownV2``.

        Raises:
            TelegramError: If Telegram rejects or cannot receive the message.
        """
        if not text.strip():
            raise TelegramError("Telegram messages must not be empty.")
        payload: dict[str, str] = {"chat_id": self._settings.chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        request = Request(
            url=f"https://api.telegram.org/bot{self._settings.bot_token}/sendMessage",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            self._transport(request, self._timeout_seconds)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            self._logger.error("Telegram delivery failed: %s", type(error).__name__)
            raise TelegramError("Telegram delivery failed; see application logs for details.") from error
        self._logger.info("Telegram message delivered.")


def _send_request(request: Request, timeout: float) -> None:
    """Execute a Telegram request and ensure a response body is consumed."""
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 -- fixed Telegram API URL
        response.read()
