"""Run one explicit, bounded Apify collector smoke test and optionally cache raw evidence."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from autofinder.collectors.apify_kleinanzeigen import ApifyKleinanzeigenCollector
from autofinder.core.config import load_config
from autofinder.core.logging import configure_logging
from autofinder.core.runtime import load_project_environment
from autofinder.main import _load_logging_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Run a small collector request; no downstream pipeline stages are invoked."""
    parser = argparse.ArgumentParser(description="Run a bounded Apify collector smoke test.")
    parser.add_argument("--cache", action="store_true", help="Save successful raw evidence under ignored data/cache/.")
    args = parser.parse_args()
    load_project_environment(PROJECT_ROOT)
    logging_settings = _load_logging_settings(PROJECT_ROOT / "config" / "logging.yaml")
    configure_logging(PROJECT_ROOT / "logs", logging_settings["level"], logging_settings["max_bytes"], logging_settings["backup_count"])
    config = load_config(PROJECT_ROOT / "config" / "autofinder.yaml")
    result = ApifyKleinanzeigenCollector(config.search, config.collection, config.apify).collect()
    print(f"Apify collector succeeded: requested={result.requested_count} received={result.received_count} status={result.actor_status}")
    if args.cache:
        destination = PROJECT_ROOT / "data" / "cache" / "apify_kleinanzeigen_smoke.json"
        destination.write_text(json.dumps(asdict(result), default=str, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Successful raw evidence cached under data/cache/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
