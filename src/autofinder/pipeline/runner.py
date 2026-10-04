"""One-run composition of existing AutoFinder stages without business-rule duplication."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Protocol

from autofinder.analysis.analyzer import VehicleAnalyzer
from autofinder.collectors.base import ListingCollector
from autofinder.core.exceptions import AutoFinderError, TelegramError
from autofinder.deals.evaluator import DealEvaluator
from autofinder.deals.models import DealDecision
from autofinder.deduplication.service import EarlyDeduplicator
from autofinder.filters.basic import BasicDealFilter
from autofinder.financial.calculator import FinancialCalculator
from autofinder.models.collection import RawMarketplaceListing
from autofinder.models.normalization import NormalizationResult
from autofinder.models.normalized_listing import NormalizedListing
from autofinder.notifications.runtime_models import RuntimeRunStatus, RuntimeRunSummary
from autofinder.notifications.runtime_reporter import RuntimeReporter
from autofinder.normalization.apify_kleinanzeigen import ApifyKleinanzeigenNormalizer
from autofinder.repair.estimator import RepairEstimator
from autofinder.valuation.ai_valuator import AIValuator


SUCCESS_EXIT_CODE = 0
FAILED_EXIT_CODE = 1
PARTIAL_SUCCESS_EXIT_CODE = 2


class _Clock(Protocol):
    """Minimal monotonic-clock boundary for deterministic runtime tests."""

    def __call__(self) -> float:
        """Return a monotonically increasing timestamp."""


@dataclass(frozen=True)
class RuntimePipelineResult:
    """Safe terminal result of one complete AutoFinder runtime attempt."""

    summary: RuntimeRunSummary
    exit_code: int
    summary_delivered: bool
    run_error_type: str | None = None


@dataclass
class _Counts:
    """Mutable orchestration counters converted to an immutable summary at completion."""

    listings_collected: int = 0
    invalid_identity_count: int = 0
    previously_seen_count: int = 0
    same_batch_duplicate_count: int = 0
    new_listings_count: int = 0
    normalization_success_count: int = 0
    normalization_failure_count: int = 0
    basic_filter_passed_count: int = 0
    basic_filter_rejected_count: int = 0
    ai_analysis_attempted_count: int = 0
    ai_analysis_failed_count: int = 0
    deals_evaluated_count: int = 0
    rejected_deals_count: int = 0
    review_candidates_count: int = 0
    strong_candidates_count: int = 0


class RuntimePipeline:
    """Run existing AutoFinder services once, sequentially, and report safely.

    The pipeline owns stage order, status aggregation, and failure isolation. It
    deliberately delegates analysis, estimates, financial arithmetic, decisions,
    and Telegram formatting to their established domain services.
    """

    def __init__(
        self,
        collector: ListingCollector,
        deduplicator: EarlyDeduplicator,
        normalizer: ApifyKleinanzeigenNormalizer,
        basic_filter: BasicDealFilter,
        vehicle_analyzer: VehicleAnalyzer,
        repair_estimator: RepairEstimator,
        ai_valuator: AIValuator,
        financial_calculator: FinancialCalculator,
        deal_evaluator: DealEvaluator,
        runtime_reporter: RuntimeReporter,
        clock: _Clock = time.monotonic,
    ) -> None:
        """Attach one reusable dependency instance per runtime stage."""
        self._collector = collector
        self._deduplicator = deduplicator
        self._normalizer = normalizer
        self._basic_filter = basic_filter
        self._vehicle_analyzer = vehicle_analyzer
        self._repair_estimator = repair_estimator
        self._ai_valuator = ai_valuator
        self._financial_calculator = financial_calculator
        self._deal_evaluator = deal_evaluator
        self._runtime_reporter = runtime_reporter
        self._clock = clock
        self._logger = logging.getLogger("autofinder.pipeline.runtime")

    def run(self) -> RuntimePipelineResult:
        """Execute one bounded pipeline run and always attempt one final summary."""
        started_at = self._clock()
        counts = _Counts()
        listing_failure = False
        self._logger.info("AutoFinder runtime run started.")

        try:
            collection = self._collector.collect()
            counts.listings_collected = collection.received_count
            self._logger.info("Collection completed: collected=%s", collection.received_count)
            deduplication = self._deduplicator.filter_new(collection.listings)
        except AutoFinderError as error:
            self._logger.error("Run-level pipeline failure: stage=collection_or_dedup error_type=%s", type(error).__name__)
            return self._complete(counts, RuntimeRunStatus.FAILED, started_at, type(error).__name__)

        counts.invalid_identity_count = deduplication.invalid_identity_count
        counts.previously_seen_count = deduplication.previously_seen_count
        counts.same_batch_duplicate_count = deduplication.duplicate_within_batch_count
        counts.new_listings_count = deduplication.new_count
        self._logger.info(
            "Early deduplication completed: old=%s new=%s invalid_identity=%s same_batch_duplicates=%s",
            counts.previously_seen_count,
            counts.new_listings_count,
            counts.invalid_identity_count,
            counts.same_batch_duplicate_count,
        )

        if not deduplication.new_listings:
            return self._complete(counts, RuntimeRunStatus.SUCCESS, started_at)

        passed_listings: list[NormalizedListing] = []
        for raw_listing in deduplication.new_listings:
            normalized = self._normalize_one(raw_listing, counts)
            if normalized is None:
                listing_failure = True
                continue
            try:
                filtered = self._basic_filter.filter_listing(normalized.listing, normalized.warnings)
            except AutoFinderError as error:
                listing_failure = True
                self._logger.error(
                    "Listing-level failure: stage=basic_filter error_type=%s",
                    type(error).__name__,
                )
                continue
            if filtered.passed:
                counts.basic_filter_passed_count += 1
                passed_listings.append(filtered.listing)
            else:
                counts.basic_filter_rejected_count += 1

        self._logger.info(
            "Basic filtering completed: passed=%s rejected=%s",
            counts.basic_filter_passed_count,
            counts.basic_filter_rejected_count,
        )
        if not passed_listings:
            status = RuntimeRunStatus.PARTIAL_SUCCESS if listing_failure else RuntimeRunStatus.SUCCESS
            return self._complete(counts, status, started_at)

        for listing in passed_listings:
            if not self._process_listing(listing, counts):
                listing_failure = True

        status = RuntimeRunStatus.PARTIAL_SUCCESS if listing_failure else RuntimeRunStatus.SUCCESS
        return self._complete(counts, status, started_at)

    def _normalize_one(self, raw_listing: RawMarketplaceListing, counts: _Counts) -> NormalizationResult | None:
        """Normalize one already-seen listing, isolating source-shape failures."""
        try:
            result = self._normalizer.normalize(raw_listing)
        except AutoFinderError as error:
            counts.normalization_failure_count += 1
            self._logger.error("Listing-level failure: stage=normalization error_type=%s", type(error).__name__)
            return None
        counts.normalization_success_count += 1
        return result

    def _process_listing(self, listing: NormalizedListing, counts: _Counts) -> bool:
        """Run all remaining canonical stages for one filtered listing."""
        identity = listing.identity.canonical_key
        counts.ai_analysis_attempted_count += 1
        self._logger.info("Listing AI analysis started: listing=%s", identity)
        try:
            analysis_result = self._vehicle_analyzer.analyze(listing)
        except AutoFinderError as error:
            counts.ai_analysis_failed_count += 1
            self._logger.error("Listing-level failure: listing=%s stage=vehicle_analysis error_type=%s", identity, type(error).__name__)
            return False

        try:
            repair_result = self._repair_estimator.estimate(listing, analysis_result.analysis)
            valuation_result = self._ai_valuator.value(listing, analysis_result.analysis, repair_result.estimate)
            financial_analysis = self._financial_calculator.calculate(listing, repair_result.estimate, valuation_result.valuation)
            evaluation = self._deal_evaluator.evaluate(
                listing,
                analysis_result.analysis,
                repair_result.estimate,
                valuation_result.valuation,
                financial_analysis,
            )
        except AutoFinderError as error:
            self._logger.error("Listing-level failure: listing=%s stage=downstream error_type=%s", identity, type(error).__name__)
            return False

        counts.deals_evaluated_count += 1
        if evaluation.decision is DealDecision.REJECT:
            counts.rejected_deals_count += 1
            self._logger.info("Deal decision: listing=%s decision=%s", identity, evaluation.decision.value)
            return True
        if evaluation.decision is DealDecision.REVIEW:
            counts.review_candidates_count += 1
        else:
            counts.strong_candidates_count += 1

        self._logger.info("Deal decision: listing=%s decision=%s", identity, evaluation.decision.value)
        try:
            self._runtime_reporter.send_candidate(
                listing,
                analysis_result.analysis,
                repair_result.estimate,
                valuation_result.valuation,
                financial_analysis,
                evaluation,
            )
        except TelegramError as error:
            self._logger.error("Listing-level failure: listing=%s stage=candidate_reporting error_type=%s", identity, type(error).__name__)
            return False
        return True

    def _complete(
        self,
        counts: _Counts,
        status: RuntimeRunStatus,
        started_at: float,
        run_error_type: str | None = None,
    ) -> RuntimePipelineResult:
        """Build one final summary, send it once, and map the terminal exit code."""
        summary = _summary_from_counts(counts, status, max(0.0, self._clock() - started_at))
        delivered = False
        try:
            delivered = self._runtime_reporter.send_summary(summary)
        except TelegramError as error:
            self._logger.error("Runtime summary delivery failed: error_type=%s", type(error).__name__)
            if status is not RuntimeRunStatus.FAILED:
                status = RuntimeRunStatus.PARTIAL_SUCCESS
                summary = summary.model_copy(update={"status": status})
        exit_code = exit_code_for_status(status)
        self._logger.info(
            "AutoFinder runtime run completed: status=%s duration_seconds=%.3f summary_delivered=%s",
            status.value,
            summary.duration_seconds,
            delivered,
        )
        return RuntimePipelineResult(summary, exit_code, delivered, run_error_type)


def exit_code_for_status(status: RuntimeRunStatus) -> int:
    """Return the documented process exit code for one runtime status."""
    return {
        RuntimeRunStatus.SUCCESS: SUCCESS_EXIT_CODE,
        RuntimeRunStatus.PARTIAL_SUCCESS: PARTIAL_SUCCESS_EXIT_CODE,
        RuntimeRunStatus.FAILED: FAILED_EXIT_CODE,
    }[status]


def _summary_from_counts(counts: _Counts, status: RuntimeRunStatus, duration_seconds: float) -> RuntimeRunSummary:
    """Convert orchestration counters into the existing validated report contract."""
    return RuntimeRunSummary(
        status=status,
        listings_collected=counts.listings_collected,
        invalid_identity_count=counts.invalid_identity_count,
        previously_seen_count=counts.previously_seen_count,
        same_batch_duplicate_count=counts.same_batch_duplicate_count,
        new_listings_count=counts.new_listings_count,
        normalization_success_count=counts.normalization_success_count,
        normalization_failure_count=counts.normalization_failure_count,
        basic_filter_passed_count=counts.basic_filter_passed_count,
        basic_filter_rejected_count=counts.basic_filter_rejected_count,
        ai_analysis_attempted_count=counts.ai_analysis_attempted_count,
        ai_analysis_failed_count=counts.ai_analysis_failed_count,
        deals_evaluated_count=counts.deals_evaluated_count,
        rejected_deals_count=counts.rejected_deals_count,
        review_candidates_count=counts.review_candidates_count,
        strong_candidates_count=counts.strong_candidates_count,
        duration_seconds=duration_seconds,
    )
