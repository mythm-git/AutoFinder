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
_SEPARATOR = "━━━━━━━━━━━━━━━━━━━━━━"

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
        """Format one compact, deliberately non-promotional runtime summary."""
        status = {
            RuntimeRunStatus.SUCCESS: "✅ SUCCESS",
            RuntimeRunStatus.PARTIAL_SUCCESS: "⚠️ PARTIAL_SUCCESS",
            RuntimeRunStatus.FAILED: "❌ FAILED",
        }[summary.status]
        candidates = summary.review_candidates_count + summary.strong_candidates_count
        return "\n".join((
            "AutoFinder Run",
            status,
            "",
            f"Collected: {summary.listings_collected}",
            f"New: {summary.new_listings_count}",
            f"Analyzed: {summary.ai_analysis_attempted_count}",
            f"Evaluated: {summary.deals_evaluated_count}",
            f"Candidates: {candidates}",
            "",
            "Next run: ~45 min",
        ))


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
        """Render a visually distinct alert from validated upstream values only."""
        if evaluation.decision is DealDecision.REJECT:
            return None
        if max_list_items < 1:
            raise ValueError("max_list_items must be positive")
        expected = financial_analysis.expected
        conservative = financial_analysis.conservative
        optimistic = financial_analysis.optimistic
        vehicle = analysis.vehicle.interpreted_from_listing
        identity = _clean(" ".join(part for part in (listing.vehicle.make or vehicle.make, listing.vehicle.model or vehicle.model, vehicle.variant) if part)) or _clean(listing.title) or "Vehicle details unavailable"
        location = _clean(" ".join(part for part in (listing.location.postal_code, listing.location.city) if part)) or "Location unavailable"
        strong = evaluation.decision is DealDecision.STRONG_CANDIDATE
        lines = _candidate_header(strong, identity, location, listing.price_eur, expected.expected_profit_eur, expected.roi_percent)
        lines.extend((_SEPARATOR, "FINANCIALS", _SEPARATOR, f"Purchase        {_money_int(expected.purchase_price_eur)}", f"Repair est.     {_money_int(expected.repair_cost_eur)}", f"Total cost      {_money_int(expected.total_investment_eur)}", f"Expected resale {_money_int(expected.resale_value_eur)}", "", f"Expected profit {_signed_money(expected.expected_profit_eur)}", f"Expected ROI    {_percent(expected.roi_percent)}", "", f"Conservative ROI {_percent(conservative.roi_percent)}", f"Optimistic ROI   {_percent(optimistic.roi_percent)}", "", _SEPARATOR, "CONDITION", _SEPARATOR, f"Condition: {analysis.overall_condition.value.replace('_', ' ').title()}", f"Risk: {analysis.risk_level.value.replace('_', ' ').title()}"))
        repairs = _repair_items(repair_estimate, max_list_items)
        if repairs:
            lines.extend(("", "Repairs:", *repairs))
        repair_summary = repair_estimate.cost_summary
        lines.extend(("", "Estimated repairs:", f"{_money_int(repair_summary.minimum_total_eur)} – {_money_int(repair_summary.expected_total_eur)} – {_money_int(repair_summary.high_total_eur)}", "", _SEPARATOR, "⚠️ WATCH OUT", _SEPARATOR))
        watch_out = _watch_out(analysis, evaluation, max_list_items)
        lines.extend(watch_out or ("• No additional validated warnings.",))
        lines.extend(("", "Confidence:", f"Analysis   {_confidence(analysis.analysis_confidence)}", f"Repair     {_confidence(repair_estimate.confidence)}", f"Valuation  {_confidence(valuation.confidence)}", "", _SEPARATOR, "WHY IT'S INTERESTING", _SEPARATOR, *_interesting_reasons(listing, expected.expected_profit_eur, expected.roi_percent, conservative.roi_percent), "", _SEPARATOR, "OPEN LISTING", _SEPARATOR))
        url = _clean(listing.url)
        if url:
            if strong:
                lines.append("CHECK THIS CAR NOW")
            lines.append(_bounded(url, 500))
        else:
            lines.append("Listing URL unavailable.")
        lines.extend(("", _SEPARATOR, "Verify car physically before buying", _SEPARATOR))
        return _bound_message("\n".join(lines))


def _candidate_header(strong: bool, identity: str, location: str, price: float | None, profit: int, roi: Decimal) -> list[str]:
    """Build the decision-specific top block without evaluating the deal again."""
    if strong:
        return [
            "🚨 STRONG DEAL 🚨",
            "AUTOFINDER HIGH-PRIORITY FIND",
            _SEPARATOR,
            _bounded(identity, 120),
            f"PRICE: {_money(price)}",
            f"EXPECTED ROI: {_percent(roi)}",
            f"EXPECTED PROFIT: {_signed_money(profit)}",
            "✅ STRONG_CANDIDATE",
            _bounded(location, 100),
            "",
        ]
    return [
        _SEPARATOR,
        "AUTOFINDER DEAL FOUND",
        _SEPARATOR,
        _bounded(identity, 120),
        _bounded(location, 100),
        f"PRICE: {_money(price)}",
        "",
        "⭐ DECISION: REVIEW",
        f"EXPECTED ROI: {_percent(roi)}",
        f"EXPECTED PROFIT: {_signed_money(profit)}",
        "",
    ]


def _repair_items(repair_estimate: RepairEstimate, limit: int) -> list[str]:
    """Show only persisted repair evidence, bounded for a mobile alert."""
    items = repair_estimate.required_repairs + repair_estimate.near_term_maintenance + repair_estimate.uncertainty_items
    return _bounded_items([f"• {_bounded(_clean(f'{item.component}: {item.description}'), _ITEM_TEXT_LIMIT)}" for item in items], limit)


def _watch_out(analysis: VehicleAnalysis, evaluation: DealEvaluation, limit: int) -> list[str]:
    """Use existing warnings and recorded missing information without inference."""
    items = [f"• {reason_text(code)}" for code in evaluation.reasons + evaluation.warnings]
    items.extend(f"• Missing: {_bounded(_clean(item.topic.value.replace('_', ' ')), _ITEM_TEXT_LIMIT)}" for item in analysis.missing_information)
    items.extend(f"• {_bounded(_clean(item.explanation), _ITEM_TEXT_LIMIT)}" for item in analysis.risk_flags)
    return _bounded_items(items, limit)


def _interesting_reasons(listing: NormalizedListing, profit: int, roi: Decimal, conservative_roi: Decimal) -> list[str]:
    """State only deterministic positives already present in canonical inputs."""
    reasons: list[str] = []
    if profit > 0:
        reasons.append("✅ Expected profit is positive")
    if roi > 0:
        reasons.append("✅ Expected ROI is positive")
    if listing.seller.type.value == "private":
        reasons.append("✅ Private seller")
    if conservative_roi > 0:
        reasons.append("✅ Conservative scenario is positive")
    return reasons or ["• Candidate decision is based on the validated pipeline output"]


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



def _money_int(value: int) -> str:
    """Format an already-calculated euro amount without any calculation."""
    return f"€{value:,}"


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
