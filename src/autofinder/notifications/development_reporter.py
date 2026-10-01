"""Development-step reporting built on the reusable Telegram client."""

from __future__ import annotations

from dataclasses import dataclass

from autofinder.notifications.telegram import TelegramClient


@dataclass(frozen=True)
class DevelopmentReport:
    """Structured, secret-free summary of one completed development step."""

    step_name: str
    status: str
    implemented: tuple[str, ...]
    tests_passed: int
    tests_failed: int
    git_commit: str
    next_step: str


class DevelopmentReporter:
    """Formats and sends one concise development report through Telegram."""

    def __init__(self, client: TelegramClient) -> None:
        """Attach the shared Telegram client."""
        self._client = client

    def send(self, report: DevelopmentReport) -> None:
        """Format and deliver the report as plain text."""
        self._client.send_text(self.format(report))

    @staticmethod
    def format(report: DevelopmentReport) -> str:
        """Return a stable human-readable development report message."""
        items = "\n".join(f"• {item}" for item in report.implemented)
        return (
            "AutoFinder Development\n\n"
            f"Step: {report.step_name}\n"
            f"Status: {report.status}\n\n"
            f"Implemented:\n{items}\n\n"
            f"Tests:\n• {report.tests_passed} passed\n• {report.tests_failed} failed\n\n"
            f"Git:\n{report.git_commit}\n\n"
            f"Next:\n{report.next_step}"
        )
