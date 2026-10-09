"""CLI service for local daily Markdown reporting and optional Telegram delivery."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from autofinder.core.config import DailyReportingConfig
from autofinder.core.exceptions import TelegramError
from autofinder.notifications.telegram import TelegramClient
from autofinder.reporting.audit_repository import JsonlAuditRepository
from autofinder.reporting.daily_report import DailyReportGenerator


def generate_daily_report(project_root: Path, config: DailyReportingConfig, date_value: str, send: bool, force: bool, client: TelegramClient | None = None) -> tuple[Path, bool]:
    """Generate a deterministic local report and send it once unless forced."""
    local_date = _parse_date(date_value, config.timezone)
    repository = JsonlAuditRepository(project_root / config.audit_directory, config.timezone)
    generator = DailyReportGenerator()
    path = generator.write(project_root / config.report_directory, local_date, generator.generate(local_date, repository.records_for_date(local_date)))
    sent = False
    state_path = project_root / config.state_file
    state = _load_state(state_path)
    if send and config.send_to_telegram and (force or state.get(local_date) != "sent"):
        if client is None:
            client = TelegramClient.from_project_environment(project_root)
        client.send_document(path, f"AutoFinder Daily Report — {local_date}")
        state[local_date] = "sent"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sent = True
    return path, sent


def main() -> int:
    """Run the documented manual daily-report command."""
    parser = argparse.ArgumentParser(description="Generate an AutoFinder daily diagnostic report.")
    parser.add_argument("--date", default="yesterday", help="yesterday or YYYY-MM-DD")
    parser.add_argument("--send", action="store_true", help="send the Markdown file as a Telegram document")
    parser.add_argument("--force", action="store_true", help="allow a repeat Telegram delivery")
    args = parser.parse_args()
    from autofinder.core.config import load_config
    from autofinder.core.runtime import resolve_project_root
    root = resolve_project_root()
    config = load_config(root / "config" / "autofinder.yaml").daily_reporting
    if config is None or not config.enabled:
        raise SystemExit("daily_reporting is not enabled")
    path, sent = generate_daily_report(root, config, args.date, args.send, args.force)
    logging.getLogger("autofinder.reporting.daily").info("Daily report generated: file=%s sent=%s", path.name, sent)
    return 0


def _parse_date(value: str, timezone: str) -> str:
    if value == "yesterday":
        return (datetime.now(ZoneInfo(timezone)).date() - timedelta(days=1)).isoformat()
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()


def _load_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return {str(key): str(item) for key, item in value.items()} if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
