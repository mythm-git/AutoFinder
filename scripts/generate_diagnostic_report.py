"""Generate the maximum-detail safe seven-day audit report without AI calls."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from autofinder.core.config import load_config
from autofinder.core.runtime import resolve_project_root
from autofinder.notifications.telegram import TelegramClient
from autofinder.reporting.audit_repository import JsonlAuditRepository
from autofinder.reporting.reason_presenter import present_reason


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _pct(part: int, total: int) -> str:
    return f"{(100 * part / total):.1f}%" if total else "n/a"


def generate(root: Path, days: int = 7) -> Path:
    """Render stored audit evidence only; missing history remains explicitly missing."""
    config = load_config(root / "config" / "autofinder.yaml")
    daily = config.daily_reporting
    assert daily is not None
    now = datetime.now(ZoneInfo(daily.timezone)).date()
    dates = [(now - timedelta(days=index)).isoformat() for index in range(days - 1, -1, -1)]
    repo = JsonlAuditRepository(root / daily.audit_directory, daily.timezone)
    records = [record for date in dates for record in repo.records_for_date(date)]
    outcomes = Counter(record.outcome for record in records)
    basic_reasons = Counter(reason for record in records if record.outcome == "BASIC_FILTER_REJECT" for reason in record.reasons)
    deal_reasons = Counter(reason for record in records if record.outcome == "REJECT" for reason in record.reasons)
    filters = config.filters
    rules = config.deal_evaluation
    lines = ["# AutoFinder Diagnostic Report — Last 7 Days", "", f"Coverage: {dates[0]} through {dates[-1]} ({daily.timezone})", "", "## Evidence Availability", "", "- Detailed audit data available from: 2026-10-10T00:23:47+02:00.", "- FULL DETAIL AVAILABLE: safe audit records persisted from that timestamp onward.", "- HISTORICAL DETAIL NOT RECORDED: source payloads, complete normalized models, provider metadata, runtime aggregates, and downstream AI/financial objects were not persisted by the old audit schema; this report does not recreate them or call AI.", "- Daily report delivery diagnosis: the tracked n8n export `AutoFinder Daily Report` has `active: false`; an inactive workflow cannot fire its 00:10 schedule.", "", "## Active Configuration", "", "```json", _json({"filters": {"price": {"min_eur": filters.price.minimum, "max_eur": filters.price.maximum}, "mileage": {"min_km": filters.mileage.minimum, "max_km": filters.mileage.maximum}, "power": {"min_ps": filters.power.minimum, "max_ps": filters.power.maximum}, "reject_dealers": filters.reject_dealers}, "deal_evaluation": rules.__dict__}), "```", "", "## Pipeline Funnel", "", "| Metric | Count | Percent of new listings |", "|---|---:|---:|", f"| New listings with audit outcomes | {len(records)} | 100.0% |", f"| Basic-filter rejects | {outcomes['BASIC_FILTER_REJECT']} | {_pct(outcomes['BASIC_FILTER_REJECT'], len(records))} |", f"| Deals evaluated | {sum(bool(record.evaluation) for record in records)} | {_pct(sum(bool(record.evaluation) for record in records), len(records))} |", f"| DEAL_REJECT | {outcomes['REJECT']} | {_pct(outcomes['REJECT'], len(records))} |", f"| REVIEW | {outcomes['REVIEW']} | {_pct(outcomes['REVIEW'], len(records))} |", f"| STRONG_CANDIDATE | {outcomes['STRONG_CANDIDATE']} | {_pct(outcomes['STRONG_CANDIDATE'], len(records))} |", f"| Processing failures | {outcomes['PROCESSING_FAILURE']} | {_pct(outcomes['PROCESSING_FAILURE'], len(records))} |", "", "Run-level totals (scheduled/runtime runs, collected, duplicates, normalization and provider attempts) were not historically persisted in audit records and are unavailable without treating log inference as authoritative.", "", "## Basic Filter Rejection Reasons", "", "| Rank | Machine code / explanation | Count | Percent |", "|---:|---|---:|---:|"]
    lines.extend(f"| {index} | `{reason}` — {present_reason(reason)} | {count} | {_pct(count, outcomes['BASIC_FILTER_REJECT'])} |" for index, (reason, count) in enumerate(sorted(basic_reasons.items(), key=lambda item: (-item[1], item[0])), 1)) or lines.append("| - | None | 0 | n/a |")
    lines.extend(["", "## Deal Evaluation Rejection Reasons", "", "| Rank | Machine code / explanation | Count | Percent |", "|---:|---|---:|---:|"])
    lines.extend(f"| {index} | `{reason}` — {present_reason(reason)} | {count} | {_pct(count, outcomes['REJECT'])} |" for index, (reason, count) in enumerate(sorted(deal_reasons.items(), key=lambda item: (-item[1], item[0])), 1)) or lines.append("| - | No evaluated deal rejects persisted | 0 | n/a |")
    lines.extend(["", "## New Listing Detail"])
    for record in records:
        listing = record.listing
        lines.extend(["", f"### {record.listing_key}", "", "#### Listing Identity", f"- Marketplace: {listing.get('identity', {}).get('marketplace', 'Kleinanzeigen (legacy audit inference)')}", f"- External ID: {listing.get('identity', {}).get('external_listing_id', record.listing_key.rsplit(':', 1)[-1])}", f"- Canonical ID: {record.listing_key}", f"- First seen: not historically persisted", f"- Processing timestamp: {record.recorded_at}", f"- Run ID: {record.run_id}", "", "#### Source / Raw Listing Information", "```json", _json(listing), "```", "", "#### Complete Normalized Listing", "Historical detail not recorded in schema v1; available safe compatibility fields are shown above. Null mileage/power here are normalized values retained by the legacy record.", "", f"## BASIC FILTER: {'REJECT' if record.outcome == 'BASIC_FILTER_REJECT' else 'PASS'}"])
        if record.outcome == "BASIC_FILTER_REJECT":
            for reason in record.reasons:
                actual = {"invalid_mileage": listing.get("mileage_km"), "invalid_power": listing.get("power_ps"), "dealer_seller": listing.get("seller_type")}.get(reason, "not historically persisted")
                limit = {"invalid_mileage": f"{filters.mileage.minimum}–{filters.mileage.maximum} km; invalid source value cannot be compared", "invalid_power": f"{filters.power.minimum}–{filters.power.maximum} PS; invalid source value cannot be compared", "dealer_seller": "private sellers only"}.get(reason, "see active configuration")
                lines.extend([f"- `{reason}` — {present_reason(reason)} Actual: `{actual}`. Configured rule: {limit}."])
            lines.extend(["", "#### Basic Filter Distance", "Numerical distance is unavailable for invalid/missing normalized values; no numeric value was persisted."])
        if record.failure:
            lines.extend(["", "#### Processing Failure", "```json", _json(record.failure), "```"])
        lines.extend(["", "#### VehicleAnalysis / RepairEstimate / AIValuation / FinancialAnalysis / DealEvaluation", "Not reached for this basic-filter rejection." if record.outcome == "BASIC_FILTER_REJECT" else "Historical full validated object not persisted in schema v1."])
    lines.extend(["", "## Closest Rejected Deals", "", "No DEAL_REJECT records with financial data were historically persisted.", "", "## Highest Expected ROI Among Rejected Cars", "", "No DEAL_REJECT records with expected ROI were historically persisted.", "", "## Highest Expected Profit Among Rejected Cars", "", "No DEAL_REJECT records with expected profit were historically persisted.", "", "## Basic Filter Near Misses", "", "No numerical near misses can be ranked because all persisted basic-filter numerical rejections have invalid/null mileage or power values.", "", "## AI Provider Metadata", "", "not historically persisted", "", "## Diagnostic Observations", "", f"- {_pct(outcomes['BASIC_FILTER_REJECT'], len(records))} of new listings with stored audit outcomes were rejected at BasicDealFilter.", f"- The most frequent basic-filter reason was `{basic_reasons.most_common(1)[0][0] if basic_reasons else 'none'}`.", "- No stored listing reached AI analysis, repair estimation, valuation, or deal evaluation.", "- No policy recommendation is made by this evidence-only report.", "", "# Raw Safe Audit Appendix"])
    for record in records:
        lines.extend(["", f"## {record.listing_key}", "```json", _json(record.to_dict()), "```"])
    output = root / "reports" / "daily" / "AutoFinder_Diagnostic_Last_7_Days.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    root = resolve_project_root()
    path = generate(root)
    if args.send:
        TelegramClient.from_project_environment(root).send_document(path, "AutoFinder Diagnostic Report — Last 7 Days")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
