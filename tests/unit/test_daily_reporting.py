"""Focused tests for deterministic daily audit reporting."""

from __future__ import annotations

from pathlib import Path

from autofinder.reporting.audit_models import AuditRecord
from autofinder.reporting.audit_repository import JsonlAuditRepository
from autofinder.reporting.daily_report import DailyReportGenerator
from autofinder.reporting.audit_factory import failure_record
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer
from datetime import UTC, datetime


def _record(key: str, outcome: str, reasons: tuple[str, ...] = ()) -> AuditRecord:
    return AuditRecord(
        schema_version=1, recorded_at="2026-10-09T12:00:00+02:00", local_date="2026-10-09",
        run_id="run-1", listing_key=key, outcome=outcome, stage="test",
        listing={"title": key, "url": "https://example.test/listing", "price_eur": 1000, "mileage_km": 100000, "power_ps": 100, "seller_type": "private"},
        reasons=reasons,
    )


def test_jsonl_audit_is_append_only_and_uses_local_date(tmp_path: Path) -> None:
    repository = JsonlAuditRepository(tmp_path, "Europe/Berlin")
    repository.append(_record("one", "BASIC_FILTER_REJECT", ("dealer_seller",)))
    repository.append(_record("two", "REJECT", ("expected_roi_below_minimum",)))

    records = repository.records_for_date("2026-10-09")

    assert repository.path_for_date("2026-10-09").name == "2026-10-09.jsonl"
    assert [record.listing_key for record in records] == ["one", "two"]


def test_daily_report_contains_all_outcomes_and_reason_aggregation(tmp_path: Path) -> None:
    records = [
        _record("basic-1", "BASIC_FILTER_REJECT", ("dealer_seller",)),
        _record("basic-2", "BASIC_FILTER_REJECT", ("price_above_maximum",)),
        _record("reject-1", "REJECT", ("expected_roi_below_minimum",)),
        _record("reject-2", "REJECT", ("expected_roi_below_minimum",)),
        _record("review", "REVIEW"),
        _record("strong", "STRONG_CANDIDATE"),
        _record("failure", "PROCESSING_FAILURE"),
    ]
    generator = DailyReportGenerator()
    report = generator.generate("2026-10-09", records)
    path = generator.write(tmp_path, "2026-10-09", report)

    assert "# AutoFinder Daily Report — 2026-10-09" in report
    assert "Expected ROI is below the configured minimum." in report
    assert "Pipeline outcome:** STRONG_CANDIDATE" in report
    assert "Processing failures: 1" in report
    assert path.read_text(encoding="utf-8") == report


def test_empty_day_report_is_readable() -> None:
    report = DailyReportGenerator().generate("2026-10-09", ())

    assert "No new-listing audit records" in report
    assert "No rejection reasons recorded" in report


def test_audit_failure_record_with_datetime_listing_fields_is_jsonl_safe(tmp_path: Path) -> None:
    """Audit must not prevent final runtime reporting after a listing-stage failure."""
    raw = RawMarketplaceListing("kleinanzeigen", {"id": "3521306041", "title": "Safe", "url": "https://www.kleinanzeigen.de/s-anzeige/safe/3521306041", "price": 1000, "currency": "EUR", "location": "Safe", "sellerType": "private", "attributes": {"brand": "Example", "model": "Car"}}, datetime.now(UTC))
    record = failure_record("run", datetime.now(UTC), ApifyKleinanzeigenNormalizer().normalize(raw).listing, "vehicle_analysis", "VehicleAnalysisError")
    repository = JsonlAuditRepository(tmp_path, "Europe/Berlin")
    repository.append(record)
    assert repository.records_for_date(record.local_date)[0].listing["collected_at"].endswith("+00:00")
