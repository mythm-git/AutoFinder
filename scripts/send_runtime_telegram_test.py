"""Send exactly one clearly marked Step 11 runtime-style Telegram test message."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from autofinder.core.config import load_config
from autofinder.notifications.runtime_models import RuntimeRunSummary
from autofinder.notifications.runtime_reporter import RuntimeReporter
from autofinder.notifications.telegram import TelegramClient


def main() -> int:
    config = load_config(PROJECT_ROOT / "config" / "autofinder.yaml")
    summary = RuntimeRunSummary(
        status="success", listings_collected=0, invalid_identity_count=0, previously_seen_count=0,
        same_batch_duplicate_count=0, new_listings_count=0, normalization_success_count=0,
        normalization_failure_count=0, basic_filter_passed_count=0, basic_filter_rejected_count=0,
        ai_analysis_attempted_count=0, ai_analysis_failed_count=0, deals_evaluated_count=0,
        rejected_deals_count=0, review_candidates_count=0, strong_candidates_count=0,
        duration_seconds=0.1,
    )
    message = "AutoFinder Runtime Message Test\n\n" + RuntimeReporter.format_summary(summary)
    TelegramClient.from_project_environment(PROJECT_ROOT).send_text(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
