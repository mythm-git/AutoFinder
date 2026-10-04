"""Fixture-only tests for the one-run runtime orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from autofinder.core.exceptions import (
    CollectorError,
    FinancialAnalysisError,
    RepairEstimationError,
    SeenStateError,
    TelegramError,
    VehicleAnalysisError,
)
from autofinder.deals.models import DealDecision
from autofinder.models.collection import CollectionResult, RawMarketplaceListing
from autofinder.models.deduplication import DeduplicationResult
from autofinder.models.filtering import BasicFilterResult
from autofinder.notifications.runtime_models import RuntimeRunStatus
from autofinder.pipeline.runner import (
    FAILED_EXIT_CODE,
    PARTIAL_SUCCESS_EXIT_CODE,
    SUCCESS_EXIT_CODE,
    RuntimePipeline,
    exit_code_for_status,
)


@dataclass
class _Collector:
    listings: tuple[RawMarketplaceListing, ...]
    error: Exception | None = None

    def collect(self) -> CollectionResult:
        if self.error:
            raise self.error
        return CollectionResult("kleinanzeigen", 5, len(self.listings), datetime.now(UTC), self.listings, "run-safe", "SUCCEEDED")


@dataclass
class _Deduplicator:
    result: DeduplicationResult | None = None
    error: Exception | None = None

    def filter_new(self, listings: tuple[RawMarketplaceListing, ...]) -> DeduplicationResult:
        if self.error:
            raise self.error
        assert self.result is not None
        return self.result


class _Normalizer:
    def __init__(self, listings: dict[str, object], fail_keys: set[str] | None = None) -> None:
        self.listings = listings
        self.fail_keys = fail_keys or set()
        self.calls: list[str] = []

    def normalize(self, raw: RawMarketplaceListing) -> object:
        key = raw.raw_data["id"]
        self.calls.append(key)
        if key in self.fail_keys:
            from autofinder.core.exceptions import NormalizationError

            raise NormalizationError("fixture normalization failure")
        return SimpleNamespace(listing=self.listings[key], warnings=())


class _Filter:
    def __init__(self, passed_keys: set[str]) -> None:
        self.passed_keys = passed_keys
        self.calls: list[str] = []

    def filter_listing(self, listing: object, warnings: tuple[object, ...]) -> BasicFilterResult:
        key = listing.identity.canonical_key
        self.calls.append(key)
        return BasicFilterResult(listing, key in self.passed_keys, (), (), ())


class _Analyzer:
    def __init__(self, fail_keys: set[str] | None = None) -> None:
        self.fail_keys = fail_keys or set()
        self.calls: list[str] = []

    def analyze(self, listing: object) -> object:
        key = listing.identity.canonical_key
        self.calls.append(key)
        if key in self.fail_keys:
            raise VehicleAnalysisError("fixture analysis failure")
        return SimpleNamespace(analysis=SimpleNamespace(marker="analysis"))


class _Repair:
    def __init__(self, fail_keys: set[str] | None = None) -> None:
        self.fail_keys = fail_keys or set()
        self.calls: list[str] = []

    def estimate(self, listing: object, analysis: object) -> object:
        key = listing.identity.canonical_key
        self.calls.append(key)
        if key in self.fail_keys:
            raise RepairEstimationError("fixture repair failure")
        return SimpleNamespace(estimate=SimpleNamespace(marker="repair"))


class _Valuator:
    def __init__(self, fail_keys: set[str] | None = None) -> None:
        self.fail_keys = fail_keys or set()
        self.calls: list[str] = []

    def value(self, listing: object, analysis: object, estimate: object) -> object:
        key = listing.identity.canonical_key
        self.calls.append(key)
        if key in self.fail_keys:
            from autofinder.core.exceptions import AIValuationError

            raise AIValuationError("fixture valuation failure")
        return SimpleNamespace(valuation=SimpleNamespace(marker="valuation"))


class _Financial:
    def __init__(self, fail_keys: set[str] | None = None) -> None:
        self.fail_keys = fail_keys or set()
        self.calls: list[str] = []

    def calculate(self, listing: object, estimate: object, valuation: object) -> object:
        key = listing.identity.canonical_key
        self.calls.append(key)
        if key in self.fail_keys:
            raise FinancialAnalysisError("fixture financial failure")
        return SimpleNamespace(marker="financial")


class _Evaluator:
    def __init__(self, decisions: dict[str, DealDecision], fail_keys: set[str] | None = None) -> None:
        self.decisions = decisions
        self.fail_keys = fail_keys or set()
        self.calls: list[str] = []

    def evaluate(self, listing: object, analysis: object, estimate: object, valuation: object, financial: object) -> object:
        key = listing.identity.canonical_key
        self.calls.append(key)
        if key in self.fail_keys:
            from autofinder.core.exceptions import DealEvaluationError

            raise DealEvaluationError("fixture evaluation failure")
        return SimpleNamespace(decision=self.decisions[key])


class _Reporter:
    def __init__(self, fail_candidate_keys: set[str] | None = None) -> None:
        self.fail_candidate_keys = fail_candidate_keys or set()
        self.events: list[tuple[str, str]] = []

    def send_candidate(self, listing: object, *args: object) -> bool:
        key = listing.identity.canonical_key
        self.events.append(("candidate", key))
        if key in self.fail_candidate_keys:
            raise TelegramError("fixture Telegram failure")
        return True

    def send_summary(self, summary: object) -> bool:
        self.events.append(("summary", summary.status.value))
        return True


def _raw(key: str) -> RawMarketplaceListing:
    return RawMarketplaceListing("kleinanzeigen", {"id": key}, datetime.now(UTC))


def _listing(key: str) -> object:
    return SimpleNamespace(identity=SimpleNamespace(canonical_key=key))


def _dedup(new: tuple[RawMarketplaceListing, ...], *, old: int = 0) -> DeduplicationResult:
    return DeduplicationResult(old + len(new), len(new), old, 0, 0, new)


def _pipeline(
    raw: tuple[RawMarketplaceListing, ...],
    deduplication: DeduplicationResult,
    *,
    passed: set[str] | None = None,
    decisions: dict[str, DealDecision] | None = None,
    analyzer_failures: set[str] | None = None,
    repair_failures: set[str] | None = None,
    financial_failures: set[str] | None = None,
    reporter: _Reporter | None = None,
) -> tuple[RuntimePipeline, dict[str, object]]:
    listings = {item.raw_data["id"]: _listing(item.raw_data["id"]) for item in raw}
    dependencies: dict[str, object] = {
        "collector": _Collector(raw),
        "deduplicator": _Deduplicator(deduplication),
        "normalizer": _Normalizer(listings),
        "filter": _Filter(passed or set()),
        "analyzer": _Analyzer(analyzer_failures),
        "repair": _Repair(repair_failures),
        "valuator": _Valuator(),
        "financial": _Financial(financial_failures),
        "evaluator": _Evaluator(decisions or {}),
        "reporter": reporter or _Reporter(),
    }
    return RuntimePipeline(
        dependencies["collector"], dependencies["deduplicator"], dependencies["normalizer"], dependencies["filter"],
        dependencies["analyzer"], dependencies["repair"], dependencies["valuator"], dependencies["financial"],
        dependencies["evaluator"], dependencies["reporter"],
    ), dependencies


def test_all_seen_is_successful_noop_with_summary_only_and_no_downstream_calls() -> None:
    raw = tuple(_raw(str(index)) for index in range(5))
    pipeline, dependencies = _pipeline(raw, _dedup((), old=5))
    result = pipeline.run()

    assert result.summary.status is RuntimeRunStatus.SUCCESS
    assert result.exit_code == SUCCESS_EXIT_CODE
    assert dependencies["normalizer"].calls == []
    assert dependencies["analyzer"].calls == []
    assert dependencies["reporter"].events == [("summary", "success")]


def test_pipeline_processes_only_new_filtered_listings_and_orders_alert_before_summary() -> None:
    raw = tuple(_raw(str(index)) for index in range(5))
    new = raw[2:]
    pipeline, dependencies = _pipeline(
        raw,
        _dedup(new, old=2),
        passed={"2", "3"},
        decisions={"2": DealDecision.REVIEW, "3": DealDecision.REJECT},
    )
    result = pipeline.run()

    assert result.summary.status is RuntimeRunStatus.SUCCESS
    assert result.summary.new_listings_count == 3
    assert result.summary.basic_filter_passed_count == 2
    assert result.summary.basic_filter_rejected_count == 1
    assert result.summary.deals_evaluated_count == 2
    assert result.summary.review_candidates_count == 1
    assert result.summary.rejected_deals_count == 1
    assert dependencies["analyzer"].calls == ["2", "3"]
    assert dependencies["reporter"].events == [("candidate", "2"), ("summary", "success")]


def test_all_filtered_listings_are_successful_and_never_reach_ai() -> None:
    raw = tuple(_raw(str(index)) for index in range(3))
    pipeline, dependencies = _pipeline(raw, _dedup(raw), passed=set())
    result = pipeline.run()

    assert result.summary.status is RuntimeRunStatus.SUCCESS
    assert result.summary.basic_filter_rejected_count == 3
    assert dependencies["analyzer"].calls == []
    assert dependencies["reporter"].events == [("summary", "success")]


@pytest.mark.parametrize(
    ("stage", "analyzer_failures", "repair_failures", "financial_failures"),
    [
        ("analysis", {"0"}, set(), set()),
        ("repair", set(), {"0"}, set()),
        ("financial", set(), set(), {"0"}),
    ],
)
def test_one_listing_failure_isolated_while_later_strong_candidate_completes(
    stage: str,
    analyzer_failures: set[str],
    repair_failures: set[str],
    financial_failures: set[str],
) -> None:
    raw = (_raw("0"), _raw("1"))
    pipeline, dependencies = _pipeline(
        raw,
        _dedup(raw),
        passed={"0", "1"},
        decisions={"0": DealDecision.REJECT, "1": DealDecision.STRONG_CANDIDATE},
        analyzer_failures=analyzer_failures,
        repair_failures=repair_failures,
        financial_failures=financial_failures,
    )
    result = pipeline.run()

    assert result.summary.status is RuntimeRunStatus.PARTIAL_SUCCESS, stage
    assert result.exit_code == PARTIAL_SUCCESS_EXIT_CODE
    assert result.summary.deals_evaluated_count == 1
    assert result.summary.strong_candidates_count == 1
    assert dependencies["reporter"].events == [("candidate", "1"), ("summary", "partial_success")]


def test_candidate_telegram_failure_is_partial_but_final_summary_is_still_sent() -> None:
    raw = (_raw("0"),)
    reporter = _Reporter({"0"})
    pipeline, dependencies = _pipeline(raw, _dedup(raw), passed={"0"}, decisions={"0": DealDecision.REVIEW}, reporter=reporter)
    result = pipeline.run()

    assert result.summary.status is RuntimeRunStatus.PARTIAL_SUCCESS
    assert result.summary.review_candidates_count == 1
    assert dependencies["reporter"].events == [("candidate", "0"), ("summary", "partial_success")]


@pytest.mark.parametrize("error", [CollectorError("fixture"), SeenStateError("fixture")])
def test_critical_collection_or_seen_state_failure_is_failed_and_summary_is_attempted(error: Exception) -> None:
    raw = (_raw("0"),)
    pipeline, dependencies = _pipeline(raw, _dedup(raw))
    if isinstance(error, CollectorError):
        dependencies["collector"].error = error
    else:
        dependencies["deduplicator"].error = error
    result = pipeline.run()

    assert result.summary.status is RuntimeRunStatus.FAILED
    assert result.exit_code == FAILED_EXIT_CODE
    assert result.run_error_type == type(error).__name__
    assert dependencies["reporter"].events == [("summary", "failed")]


def test_exit_status_mapping_is_documented_and_complete() -> None:
    assert exit_code_for_status(RuntimeRunStatus.SUCCESS) == 0
    assert exit_code_for_status(RuntimeRunStatus.PARTIAL_SUCCESS) == 2
    assert exit_code_for_status(RuntimeRunStatus.FAILED) == 1
