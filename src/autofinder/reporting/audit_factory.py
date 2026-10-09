"""Construct deliberately minimal audit evidence from existing typed outcomes."""

from __future__ import annotations

from datetime import datetime
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
    return _record(run_id, now, result.listing, "BASIC_FILTER_REJECT", "basic_filter", reasons=[item.value for item in result.rejection_reasons])


def evaluation_record(run_id: str, now: datetime, listing: NormalizedListing, analysis: VehicleAnalysis, repair: RepairEstimate, valuation: AIValuation, financial: FinancialAnalysis, evaluation: DealEvaluation) -> AuditRecord:
    """Record existing complete pipeline outputs without redoing any calculation."""
    return _record(run_id, now, listing, evaluation.decision.value.upper(), "deal_evaluation", reasons=[item.value for item in evaluation.reasons], warnings=[item.value for item in evaluation.warnings], analysis={
        "condition": analysis.overall_condition.value, "risk": analysis.risk_level.value, "confidence": analysis.analysis_confidence,
        "current_faults": [_short(item.component, item.issue) for item in analysis.current_faults[:6]],
        "completed_repairs": [_short(item.component, item.repair) for item in analysis.completed_repairs[:6]],
        "maintenance": [item.service for item in analysis.maintenance_history[:6]],
        "missing_information": [item.topic.value for item in analysis.missing_information[:6]],
        "risk_flags": [item.explanation for item in analysis.risk_flags[:6]],
    }, repair={
        "minimum_eur": repair.cost_summary.minimum_total_eur, "expected_eur": repair.cost_summary.expected_total_eur, "high_eur": repair.cost_summary.high_total_eur,
        "confidence": repair.confidence, "uncertainty": repair.cost_summary.includes_uncertainty_reserve,
        "items": [item.description for item in (repair.required_repairs + repair.near_term_maintenance + repair.uncertainty_items)[:8]],
    }, valuation={
        "source": valuation.source.value, "as_is": _range(valuation.as_is_value), "post_repair": _range(valuation.post_repair_resale_value), "confidence": valuation.confidence,
        "uncertainties": list(valuation.uncertainties[:6]),
    }, financial={name: _scenario(getattr(financial, name)) for name in ("conservative", "expected", "optimistic")}, evaluation={
        "decision": evaluation.decision.value, "expected_roi_percent": str(evaluation.expected_roi_percent), "conservative_roi_percent": str(evaluation.conservative_roi_percent),
        "optimistic_roi_percent": str(evaluation.optimistic_roi_percent), "expected_profit_eur": evaluation.expected_profit_eur,
        "expected_total_investment_eur": evaluation.expected_total_investment_eur, "rules_version": evaluation.rules_version,
    })


def failure_record(run_id: str, now: datetime, listing: NormalizedListing | None, stage: str, error_type: str) -> AuditRecord:
    """Record a classified failure only; never persist an exception message or raw payload."""
    key = listing.identity.canonical_key if listing else "unavailable"
    safe_listing = _listing(listing) if listing else {"title": None, "url": None}
    return AuditRecord(1, now.isoformat(), now.date().isoformat(), run_id, key, "PROCESSING_FAILURE", stage, safe_listing, failure={"stage": stage, "error_type": error_type})


def _record(run_id: str, now: datetime, listing: NormalizedListing, outcome: str, stage: str, **data: Any) -> AuditRecord:
    return AuditRecord(1, now.isoformat(), now.date().isoformat(), run_id, listing.identity.canonical_key, outcome, stage, _listing(listing), **data)


def _listing(listing: NormalizedListing) -> dict[str, Any]:
    return {"title": listing.title, "url": listing.url, "price_eur": listing.price_eur, "make": listing.vehicle.make, "model": listing.vehicle.model, "mileage_km": listing.vehicle.mileage_km, "power_ps": listing.vehicle.power_ps, "seller_type": listing.seller.type.value, "location": listing.location.raw_text or listing.location.city}


def _range(value: Any) -> dict[str, int]:
    return {"conservative": value.conservative_eur, "expected": value.expected_eur, "optimistic": value.optimistic_eur}


def _scenario(value: Any) -> dict[str, Any]:
    return {"investment_eur": value.total_investment_eur, "resale_eur": value.resale_value_eur, "profit_eur": value.expected_profit_eur, "roi_percent": str(value.roi_percent)}


def _short(left: str, right: str) -> str:
    return f"{left}: {right}"
