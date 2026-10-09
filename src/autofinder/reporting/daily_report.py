"""Deterministic Markdown daily diagnostic report generation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from autofinder.reporting.audit_models import AuditRecord
from autofinder.reporting.reason_presenter import present_reason


class DailyReportGenerator:
    """Render human-readable diagnostics from persisted audit data only."""

    def generate(self, local_date: str, records: Iterable[AuditRecord]) -> str:
        """Generate one complete Markdown report without external calls or AI work."""
        entries = list(records)
        counts = Counter(record.outcome for record in entries)
        reasons = Counter(reason for record in entries for reason in record.reasons)
        lines = [f"# AutoFinder Daily Report — {local_date}", "", "## Daily Summary", ""]
        lines.extend(f"- {label}: {value}" for label, value in [
            ("New listings", len(entries)), ("Basic-filter rejects", counts["BASIC_FILTER_REJECT"]), ("AI-analyzed listings", sum(bool(item.analysis) for item in entries)),
            ("Deal rejects", counts["REJECT"]), ("REVIEW candidates", counts["REVIEW"]), ("STRONG candidates", counts["STRONG_CANDIDATE"]), ("Processing failures", counts["PROCESSING_FAILURE"]),
        ])
        lines.extend(["", "## Rejection Overview", "", "| Reason | Count |", "|---|---:|"])
        if reasons:
            lines.extend(f"| {present_reason(reason)} ({reason}) | {count} |" for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0])))
        else:
            lines.append("| No rejection reasons recorded | 0 |")
        lines.extend(["", "## Pipeline Funnel", "", f"Collected new listings: {len(entries)}", "↓", f"Basic filter passed: {len(entries) - counts['BASIC_FILTER_REJECT'] - counts['PROCESSING_FAILURE']}", "↓", f"AI analyzed: {sum(bool(item.analysis) for item in entries)}", "↓", f"Deal evaluated: {sum(bool(item.evaluation) for item in entries)}", "↓", f"REVIEW: {counts['REVIEW']}", "↓", f"STRONG: {counts['STRONG_CANDIDATE']}", "", "## Deal / Listing Details"])
        if not entries:
            lines.extend(["", "No new-listing audit records were captured for this local day. Detailed audit reporting is available from this feature's deployment onward."])
        for record in entries:
            lines.extend(["", *self._detail(record)])
        lines.extend(["", "## Most Common Rejection Reasons", ""])
        lines.extend(f"- {present_reason(reason)}: {count}" for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))) if reasons else lines.append("- No rejection reasons recorded.")
        lines.extend(["", "## Diagnostic Observations", "", f"- {counts['BASIC_FILTER_REJECT']} of {len(entries)} new listings were rejected at the basic filter.", f"- {counts['STRONG_CANDIDATE']} listings reached STRONG_CANDIDATE.", "- This report contains evidence only; it makes no automatic policy recommendations.", ""])
        return "\n".join(lines)

    def write(self, directory: Path, local_date: str, markdown: str) -> Path:
        """Write one UTF-8 report at its deterministic date filename."""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{local_date}.md"
        path.write_text(markdown, encoding="utf-8", newline="\n")
        return path

    def _detail(self, record: AuditRecord) -> list[str]:
        listing = record.listing
        lines = [f"### {record.listing_key}", f"**{listing.get('title') or 'Title unavailable'}**", f"Listing: {listing.get('url') or 'URL unavailable'}", "", f"**Pipeline outcome:** {record.outcome}", "", "#### Listing facts"]
        for label, key, prefix, suffix in [("Price", "price_eur", "€", ""), ("Mileage", "mileage_km", "", " km"), ("Power", "power_ps", "", " PS"), ("Location", "location", "", ""), ("Seller type", "seller_type", "", "")]:
            if listing.get(key) is not None:
                lines.append(f"- {label}: {prefix}{listing[key]}{suffix}")
        if record.reasons:
            lines.extend(["", "#### Blocking reasons", *[f"- {present_reason(code)} ({code})" for code in record.reasons]])
        if record.failure:
            lines.extend(["", "#### Processing failure", f"- Stage: {record.failure['stage']}", f"- Classified error: {record.failure['error_type']}"])
        if record.analysis:
            lines.extend(["", "#### Vehicle analysis", f"- Condition: {record.analysis['condition']}", f"- Risk: {record.analysis['risk']}", f"- Analysis confidence: {record.analysis['confidence']:.0%}"])
            for label, key in [("Current faults", "current_faults"), ("Completed repairs", "completed_repairs"), ("Maintenance", "maintenance"), ("Important missing information", "missing_information")]:
                if values := record.analysis.get(key):
                    lines.extend([f"{label}:", *[f"- {value}" for value in values]])
        if record.repair:
            lines.extend(["", "#### Repair estimate", f"- Minimum: €{record.repair['minimum_eur']}", f"- Expected: €{record.repair['expected_eur']}", f"- High: €{record.repair['high_eur']}", f"- Confidence: {record.repair['confidence']:.0%}"])
        if record.valuation:
            lines.extend(["", "#### AI valuation", f"Source: {record.valuation['source']}"])
            for label, key in [("As-is", "as_is"), ("Post-repair", "post_repair")]:
                value = record.valuation[key]
                lines.append(f"- {label}: €{value['conservative']} / €{value['expected']} / €{value['optimistic']}")
            lines.append(f"- Confidence: {record.valuation['confidence']:.0%}")
        if record.financial:
            lines.extend(["", "#### Financial analysis", "", "| Scenario | Investment | Resale | Profit | ROI |", "|---|---:|---:|---:|---:|"])
            lines.extend(f"| {name.title()} | €{value['investment_eur']} | €{value['resale_eur']} | €{value['profit_eur']} | {value['roi_percent']}% |" for name, value in record.financial.items())
        if record.evaluation:
            lines.extend(["", "#### Deal decision", f"Decision: {record.evaluation['decision'].upper()}"])
        if record.warnings:
            lines.extend(["Warnings:", *[f"- {present_reason(code)} ({code})" for code in record.warnings]])
        if record.outcome == "REJECT" and record.reasons and record.evaluation:
            lines.extend(["", "#### Why AutoFinder did not accept this car", f"Rejected because {present_reason(record.reasons[0]).rstrip('.').lower()}. Expected ROI was {record.evaluation['expected_roi_percent']}% and expected profit was €{record.evaluation['expected_profit_eur']}."])
        return lines
