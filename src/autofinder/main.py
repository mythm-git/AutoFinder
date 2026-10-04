"""Executable one-run composition root for AutoFinder v2."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from autofinder.ai.factory import create_ai_manager
from autofinder.analysis.analyzer import VehicleAnalyzer
from autofinder.collectors.apify_kleinanzeigen import ApifyKleinanzeigenCollector
from autofinder.core.config import AppConfig, load_config
from autofinder.core.exceptions import AutoFinderError
from autofinder.core.logging import configure_logging
from autofinder.core.runtime import load_project_environment, resolve_project_root
from autofinder.deals.evaluator import DealEvaluator
from autofinder.deduplication.json_repository import JsonSeenListingRepository
from autofinder.deduplication.service import EarlyDeduplicator
from autofinder.filters.basic import BasicDealFilter
from autofinder.financial.calculator import FinancialCalculator
from autofinder.notifications.runtime_reporter import RuntimeReporter
from autofinder.notifications.telegram import TelegramClient
from autofinder.normalization.apify_kleinanzeigen import ApifyKleinanzeigenNormalizer
from autofinder.pipeline.runner import FAILED_EXIT_CODE, RuntimePipeline
from autofinder.repair.estimator import RepairEstimator
from autofinder.valuation.ai_valuator import AIValuator


PROJECT_ROOT = resolve_project_root()


def main() -> int:
    """Execute one complete AutoFinder run and return its documented exit code."""
    load_project_environment(PROJECT_ROOT)
    logging_settings = _load_logging_settings(PROJECT_ROOT / "config" / "logging.yaml")
    logger = configure_logging(
        PROJECT_ROOT / "logs",
        level=logging_settings["level"],
        max_bytes=logging_settings["max_bytes"],
        backup_count=logging_settings["backup_count"],
    )
    try:
        config = load_config(PROJECT_ROOT / "config" / "autofinder.yaml")
        pipeline = build_runtime_pipeline(config, PROJECT_ROOT)
        result = pipeline.run()
    except AutoFinderError as error:
        logger.error("AutoFinder runtime initialization failed: error_type=%s", type(error).__name__)
        return FAILED_EXIT_CODE

    logger.info(
        "AutoFinder module execution completed: status=%s exit_code=%s",
        result.summary.status.value,
        result.exit_code,
    )
    return result.exit_code


def build_runtime_pipeline(config: AppConfig, project_root: Path) -> RuntimePipeline:
    """Construct reusable runtime dependencies once for a single sequential run."""
    collector = ApifyKleinanzeigenCollector(config.search, config.collection, config.apify)
    deduplicator = EarlyDeduplicator(
        JsonSeenListingRepository(project_root / config.deduplication.state_file)
    )
    ai_manager = create_ai_manager(config.ai)
    return RuntimePipeline(
        collector=collector,
        deduplicator=deduplicator,
        normalizer=ApifyKleinanzeigenNormalizer(),
        basic_filter=BasicDealFilter(config.filters),
        vehicle_analyzer=VehicleAnalyzer(ai_manager),
        repair_estimator=RepairEstimator(ai_manager),
        ai_valuator=AIValuator(ai_manager),
        financial_calculator=FinancialCalculator(),
        deal_evaluator=DealEvaluator(config.deal_evaluation),
        runtime_reporter=RuntimeReporter(
            TelegramClient.from_project_environment(project_root),
            config.telegram,
        ),
    )


def _load_logging_settings(path: Path) -> dict[str, object]:
    """Load small logging-only YAML settings with a clear validation boundary."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    settings = payload.get("logging") if isinstance(payload, dict) else None
    if not isinstance(settings, dict):
        raise ValueError("logging.yaml must contain a logging mapping")
    required = ("level", "max_bytes", "backup_count")
    if any(key not in settings for key in required):
        raise ValueError("logging.yaml is missing required settings")
    return settings
