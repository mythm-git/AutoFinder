"""Send one explicit AutoFinder development report through the shared client.

This script is intentionally manual: automated unit tests inject a transport and
never send messages to a real Telegram group.
"""

from __future__ import annotations

import argparse

from autofinder.notifications.development_reporter import DevelopmentReport, DevelopmentReporter
from autofinder.notifications.telegram import TelegramClient


def main() -> int:
    """Parse a development summary and deliver it using local environment credentials."""
    parser = argparse.ArgumentParser(description="Send an AutoFinder development report.")
    parser.add_argument("--step", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--passed", type=int, required=True)
    parser.add_argument("--failed", type=int, required=True)
    parser.add_argument("--next", dest="next_step", required=True)
    parser.add_argument("--implemented", action="append", required=True)
    args = parser.parse_args()
    report = DevelopmentReport(
        step_name=args.step,
        status="✅ Completed",
        implemented=tuple(args.implemented),
        tests_passed=args.passed,
        tests_failed=args.failed,
        git_commit=args.commit,
        next_step=args.next_step,
    )
    DevelopmentReporter(TelegramClient.from_environment()).send(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
