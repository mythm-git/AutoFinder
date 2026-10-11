"""Construct deliberately minimal audit evidence from existing typed outcomes."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import re
from typing import Any

from autofinder.analysis.models import VehicleAnalysis
from autofinder.deals.models import DealEvaluation
from autofinder.financial.models import FinancialAnalysis
from autofinder.models.filtering import BasicFilterResult
from autofinder.models.normalized_listing import NormalizedListing
from autofinder.repair.models import RepairEstimate
from autofinder.reporting.audit_models import AuditRecord
from autofinder.valuation.models import AIValuation


def basic_filter_record(run_id: str, now: datetime, result: BasicFilterResult) -> AuditRecord:
    """Record an existing pre-AI filter rejection without invoking AI."""
    return _record(run_id, now, result.listing, "BASIC_FILTER_REJECT", "basic_filter", reasons=[item.value for item in result.rejection_reasons], diagnostics={"filter_warnings": [item.value for item in result.warnings], "matched_dealer_indicators": list(result.matched_indicators)})


def evaluation_record(run_id: str, now: datetime, listing: NormalizedListing, analysis: VehicleAnalysis, repair: RepairEstimate, valuation: AIValuation, financial: FinancialAnalysis, evaluation: DealEvaluation) -> AuditRecord:
    """Record existing complete pipeline outputs without redoing any calculation."""
    return _record(run_id, now, listing, evaluation.decision.value.upper(), "deal_evaluation", reasons=[item.value for item in evaluation.reasons], warnings=[item.value for item in evaluation.warnings], analysis=analysis.model_dump(mode="json"), repair=repair.model_dump(mode="json"), valuation=valuation.model_dump(mode="json"), financial=financial.model_dump(mode="json"), evaluation=evaluation.model_dump(mode="json"), diagnostics={"audit_detail": "complete_validated_models"})


def failure_record(run_id: str, now: datetime, listing: NormalizedListing | None, stage: str, error_type: str) -> AuditRecord:
    """Record a classified failure only; never persist an exception message or raw payload."""
    key = listing.identity.canonical_key if listing else "unavailable"
    safe_listing = _listing(listing) if listing else {"title": None, "url": None}
    return AuditRecord(1, now.isoformat(), now.date().isoformat(), run_id, key, "PROCESSING_FAILURE", stage, safe_listing, failure={"stage": stage, "error_type": error_type})


def _record(run_id: str, now: datetime, listing: NormalizedListing, outcome: str, stage: str, **data: Any) -> AuditRecord:
    return AuditRecord(1, now.isoformat(), now.date().isoformat(), run_id, listing.identity.canonical_key, outcome, stage, _listing(listing), **data)


def _listing(listing: NormalizedListing) -> dict[str, Any]:
    value = asdict(listing)
    value["identity"]["canonical_key"] = listing.identity.canonical_key
    value["source"]["raw_data"] = _sanitize(value["source"].get("raw_data", {}))
    # Compatibility fields make old and new records equally reportable.
    value.update({"url": listing.url, "price_eur": listing.price_eur, "make": listing.vehicle.make, "model": listing.vehicle.model, "mileage_km": listing.vehicle.mileage_km, "power_ps": listing.vehicle.power_ps, "seller_type": listing.seller.type.value, "location": listing.location.raw_text or listing.location.city})
    return value
def _sanitize(value: Any) -> Any:
    """Recursively retain public listing evidence while excluding credentials/contact data."""
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items() if not _PRIVATE_KEY.search(str(key))}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _PHONE.sub("[redacted phone]", _EMAIL.sub("[redacted email]", value))
    return value


_PRIVATE_KEY = re.compile(r"(?:token|secret|authorization|cookie|password|email|phone|contact|seller.?name)", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d ()/-]{7,}\d)(?!\w)")


