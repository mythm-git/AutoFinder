"""Plain-text, bounded runtime summaries and candidate alerts over validated inputs."""

from __future__ import annotations

from decimal import Decimal
import logging
from typing import Iterable

from autofinder.analysis.models import VehicleAnalysis
from autofinder.core.config import TelegramReportingConfig
from autofinder.deals.models import DealDecision, DealEvaluation, DealEvaluationCode
from autofinder.financial.models import FinancialAnalysis
from autofinder.models.normalized_listing import NormalizedListing
from autofinder.notifications.runtime_models import RuntimeRunStatus, RuntimeRunSummary
from autofinder.notifications.telegram import TelegramClient
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.models import AIValuation


TELEGRAM_TEXT_LIMIT = 4_000
_ITEM_TEXT_LIMIT = 180

_REASON_TEXT: dict[str, str] = {
    DealEvaluationCode.EXPECTED_PROFIT_NON_POSITIVE.value: "Expected profit is not positive.",
    DealEvaluationCode.EXPECTED_ROI_BELOW_MINIMUM.value: "Expected ROI is below the configured minimum.",
    DealEvaluationCode.VEHICLE_RISK_VERY_HIGH.value: "Vehicle risk is very high.",
    DealEvaluationCode.CONSERVATIVE_ROI_NEGATIVE.value: "Conservative scenario is still loss-making.",
    DealEvaluationCode.CONSERVATIVE_ROI_BELOW_STRONG_MINIMUM.value: "Conservative ROI is below the strong-candidate threshold.",
    DealEvaluationCode.VEHICLE_RISK_HIGH.value: "Vehicle risk is high.",
    DealEvaluationCode.VEHICLE_RISK_UNKNOWN.value: "Vehicle risk is unknown.",
    DealEvaluationCode.ANALYSIS_CONFIDENCE_LOW.value: "Listing analysis confidence is below the configured threshold.",
    DealEvaluationCode.REPAIR_CONFIDENCE_LOW.value: "Repair estimate confidence is below the configured threshold.",
    DealEvaluationCode.VALUATION_CONFIDENCE_LOW.value: "Valuation confidence is below the configured threshold.",
    DealEvaluationCode.REPAIR_UNCERTAINTY_PRESENT.value: "Repair costs contain meaningful uncertainty.",
    DealEvaluationCode.LISTING_INFORMATION_INCOMPLETE.value: "Important listing information is incomplete.",
    DealEvaluationCode.VALUATION_AI_ONLY.value: "Valuation is AI-only and has no live market comparables yet.",
    DealEvaluationCode.CONSERVATIVE_SCENARIO_POSITIVE.value: "Conservative scenario remains positive.",
}


class RuntimeReporter:
    """Deliver runtime summaries and non-rejected candidate alerts via Telegram."""

    def __init__(self, client: TelegramClient, config: TelegramReportingConfig) -> None:
        self._client = client
        self._config = config
        self._logger = logging.getLogger("autofinder.notifications.runtime")

    def send_summary(self, summary: RuntimeRunSummary) -> bool:
        """Send one enabled run summary; return false when deliberately suppressed."""
        if not self._config.runtime_summary_enabled:
            self._logger.warning("Runtime summary suppressed by configuration.")
            return False
        self._client.send_text(self.format_summary(summary))
        self._logger.info("Runtime summary sent: status=%s", summary.status.value)
        return True

    def send_candidate(
        self,
        listing: NormalizedListing,
        analysis: VehicleAnalysis,
        repair_estimate: RepairEstimate,
        valuation: AIValuation,
        financial_analysis: FinancialAnalysis,
        evaluation: DealEvaluation,
    ) -> bool:
        """Send one enabled REVIEW/STRONG alert; never alert a rejected deal."""
        message = self.format_candidate(
            listing, analysis, repair_estimate, valuation, financial_analysis, evaluation, self._config.max_list_items
        )
        if message is None:
            self._logger.info("Candidate alert not sent for rejected listing=%s", listing.identity.canonical_key)
            return False
        if not self._config.candidate_alerts_enabled:
            self._logger.warning("Candidate alert suppressed by configuration: listing=%s", listing.identity.canonical_key)
            return False
        if not _clean(listing.url):
            self._logger.warning("Candidate listing URL is unavailable: listing=%s", listing.identity.canonical_key)
        if len(message) >= TELEGRAM_TEXT_LIMIT:
            self._logger.warning("Candidate message was truncated: listing=%s", listing.identity.canonical_key)
        self._client.send_text(message)
        self._logger.info("Candidate alert sent: listing=%s decision=%s", listing.identity.canonical_key, evaluation.decision.value)
        return True

    @staticmethod
    def format_summary(summary: RuntimeRunSummary) -> str:
        """Format one concise plain-text runtime summary without fabricated counts."""
        heading = {
            RuntimeRunStatus.SUCCESS: "Run completed ✅",
            RuntimeRunStatus.PARTIAL_SUCCESS: "Run completed with partial success ⚠️",
            RuntimeRunStatus.FAILED: "Run failed ❌",
        }[summary.status]
        lines = ["AutoFinder Runtime", "", heading, "", "Collection:", f"• Collected: {summary.listings_collected}"]
        if summary.invalid_identity_count:
            lines.append(f"• Invalid identity: {summary.invalid_identity_count}")
        lines.extend((f"• Already seen: {summary.previously_seen_count}", f"• Same-batch duplicates: {summary.same_batch_duplicate_count}", f"• New: {summary.new_listings_count}"))
        if summary.new_listings_count == 0:
            lines.extend(("", "No new cars to process.", "", f"Duration: {_duration(summary.duration_seconds)}"))
            return "\n".join(lines)
        lines.extend((
            "", "Normalization:", f"• Succeeded: {summary.normalization_success_count}", f"• Failed: {summary.normalization_failure_count}",
            "", "Filtering:", f"• Passed: {summary.basic_filter_passed_count}", f"• Rejected: {summary.basic_filter_rejected_count}",
        ))
        if summary.basic_filter_passed_count == 0:
            lines.extend(("", "Candidates: 0", "", f"Duration: {_duration(summary.duration_seconds)}"))
            return "\n".join(lines)
        lines.extend((
            "", "AI:", f"• Analyzed: {summary.ai_analysis_attempted_count}", f"• Failed: {summary.ai_analysis_failed_count}",
            "", "Deals:", f"• Rejected: {summary.rejected_deals_count}", f"• Review: {summary.review_candidates_count}", f"• Strong: {summary.strong_candidates_count}",
            "", f"Duration: {_duration(summary.duration_seconds)}",
        ))
        return "\n".join(lines)

    @staticmethod
    def format_candidate(
        listing: NormalizedListing,
        analysis: VehicleAnalysis,
        repair_estimate: RepairEstimate,
        valuation: AIValuation,
        financial_analysis: FinancialAnalysis,
        evaluation: DealEvaluation,
        max_list_items: int = 4,
    ) -> str | None:
        """Render a concise candidate alert using only upstream values; reject is silent."""
        if evaluation.decision is DealDecision.REJECT:
            return None
        if max_list_items < 1:
            raise ValueError("max_list_items must be positive")
        strong = evaluation.decision is DealDecision.STRONG_CANDIDATE
        header = "AutoFinder Strong Candidate" if strong else "AutoFinder Candidate — REVIEW"
        expected = financial_analysis.expected
        conservative = financial_analysis.conservative
        optimistic = financial_analysis.optimistic
        vehicle = analysis.vehicle.interpreted_from_listing
        make = listing.vehicle.make or vehicle.make
        model = listing.vehicle.model or vehicle.model
        identity = _clean(" ".join(part for part in (make, model, vehicle.variant) if part)) or _clean(listing.title) or "Vehicle details unavailable"
        location = _clean(" ".join(part for part in (listing.location.postal_code, listing.location.city) if part)) or "Location unavailable"

        lines = [
            header, "", _bounded(identity, 120), _money(listing.price_eur), _bounded(location, 100),
            "", f"Decision: {evaluation.decision.value.upper()}",
            f"Condition: {analysis.overall_condition.value.replace('_', ' ').title()}",
            f"Risk: {analysis.risk_level.value.replace('_', ' ').title()}",
            f"Analysis confidence: {_confidence(analysis.analysis_confidence)}",
        ]
        vehicle_facts = _vehicle_facts(vehicle.registration_year, listing.vehicle.mileage_km, listing.vehicle.power_ps, vehicle.fuel_type, vehicle.transmission, vehicle.tuv_until)
        if vehicle_facts:
            lines.extend(("", "Vehicle:", *vehicle_facts))
        important_points = _important_points(analysis, max_list_items)
        if important_points:
            lines.extend(("", "Important points:", *important_points))
        summary = repair_estimate.cost_summary
        lines.extend((
            "", "Repair estimate:",
            f"• Minimum: €{summary.minimum_total_eur}",
            f"• Expected: €{summary.expected_total_eur}",
            f"• High: €{summary.high_total_eur}",
            f"• Confidence: {_confidence(repair_estimate.confidence)}",
            "", "AI valuation:",
            f"• As-is: {_value_range(valuation.as_is_value.conservative_eur, valuation.as_is_value.expected_eur, valuation.as_is_value.optimistic_eur)}",
            f"• Post-repair: {_value_range(valuation.post_repair_resale_value.conservative_eur, valuation.post_repair_resale_value.expected_eur, valuation.post_repair_resale_value.optimistic_eur)}",
            f"• Confidence: {_confidence(valuation.confidence)}",
            "• Source: AI estimate",
            "", "Financials:",
            f"• Expected investment: €{expected.total_investment_eur}",
            f"• Expected profit: {_signed_money(expected.expected_profit_eur)}",
            f"• Expected ROI: {_percent(expected.roi_percent)}",
            "", "ROI scenarios:",
            f"• Conservative: {_percent(conservative.roi_percent)}",
            f"• Expected: {_percent(expected.roi_percent)}",
            f"• Optimistic: {_percent(optimistic.roi_percent)}",
        ))
        notes = _notes(evaluation.reasons + evaluation.warnings, max_list_items)
        if notes:
            lines.extend(("", "Why this decision:" if not strong else "Warnings:", *notes))
        lines.extend(("", "Human inspection and approval required."))
        url = _clean(listing.url)
        if url:
            lines.extend(("", "Kleinanzeigen:", _bounded(url, 500)))
        else:
            lines.extend(("", "Listing URL unavailable."))
        return _bound_message("\n".join(lines))


def reason_text(code: DealEvaluationCode | str) -> str:
    """Translate one stable machine code without changing its stored value."""
    value = code.value if isinstance(code, DealEvaluationCode) else str(code)
    return _REASON_TEXT.get(value, f"Additional evaluation note: {_bounded(_clean(value) or 'unknown', 100)}")


def _important_points(analysis: VehicleAnalysis, limit: int) -> list[str]:
    """Present repairs separately from current faults, with deterministic bounds."""
    lines: list[str] = []
    current = [f"⚠️ Current fault: {_bounded(_clean(f'{item.component}: {item.issue}'), _ITEM_TEXT_LIMIT)}" for item in analysis.current_faults]
    completed = [f"✅ Completed repair: {_bounded(_clean(f'{item.component}: {item.repair}'), _ITEM_TEXT_LIMIT)}" for item in analysis.completed_repairs]
    maintenance = [f"✅ Maintenance: {_bounded(_clean(item.service), _ITEM_TEXT_LIMIT)}" for item in analysis.maintenance_history]
    missing = [f"⚠️ Missing: {_bounded(_clean(item.topic.value.replace('_', ' ')), _ITEM_TEXT_LIMIT)}" for item in analysis.missing_information]
    risks = [f"⚠️ Risk: {_bounded(_clean(item.explanation), _ITEM_TEXT_LIMIT)}" for item in analysis.risk_flags]
    for group in (current, completed, maintenance, missing, risks):
        lines.extend(_bounded_items(group, limit))
    return lines


def _notes(codes: Iterable[DealEvaluationCode], limit: int) -> list[str]:
    return _bounded_items([f"⚠️ {reason_text(code)}" for code in codes], limit)


def _bounded_items(items: list[str], limit: int) -> list[str]:
    displayed = items[:limit]
    if len(items) > limit:
        displayed.append(f"• +{len(items) - limit} more")
    return displayed


def _vehicle_facts(year: int | None, mileage: float | None, power: float | None, fuel: str | None, transmission: str | None, tuv: str | None) -> list[str]:
    values = []
    if year is not None:
        values.append(f"• Year: {year}")
    if mileage is not None:
        values.append(f"• Mileage: {int(mileage):,} km")
    if power is not None:
        values.append(f"• Power: {int(power)} PS")
    if fuel:
        values.append(f"• Fuel: {_bounded(_clean(fuel), 80)}")
    if transmission:
        values.append(f"• Transmission: {_bounded(_clean(transmission), 80)}")
    if tuv:
        values.append(f"• TÜV: {_bounded(_clean(tuv), 80)}")
    return values


def _value_range(conservative: int, expected: int, optimistic: int) -> str:
    return f"€{conservative} / €{expected} / €{optimistic}"


def _money(value: float | None) -> str:
    return f"€{int(value):,}" if value is not None else "Price unavailable"


def _signed_money(value: int) -> str:
    return f"{'+' if value >= 0 else '-'}€{abs(value)}"


def _percent(value: Decimal) -> str:
    return f"{value:+.2f}%"


def _confidence(value: float) -> str:
    return f"{value * 100:.0f}%"


def _duration(value: float) -> str:
    return f"{value:.1f}s"


def _clean(value: object | None) -> str:
    return " ".join(str(value or "").split())


def _bounded(value: str, limit: int) -> str:
    return value if len(value) <= limit else f"{value[:limit - 1].rstrip()}…"


def _bound_message(value: str) -> str:
    if len(value) <= TELEGRAM_TEXT_LIMIT:
        return value
    suffix = "\n… [message truncated]"
    return f"{value[:TELEGRAM_TEXT_LIMIT - len(suffix)].rstrip()}{suffix}"
