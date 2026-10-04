"""Print sanitized Step 11 formatter fixtures locally; no network or .env."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from autofinder.analysis.models import VehicleAnalysis
from autofinder.deals.models import DealEvaluation
from autofinder.financial.models import FinancialAnalysis, FinancialScenario
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer
from autofinder.notifications.runtime_models import RuntimeRunSummary
from autofinder.notifications.runtime_reporter import RuntimeReporter
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.models import AIValuation


def _listing():
    raw = json.loads((PROJECT_ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json").read_text(encoding="utf-8"))[0]
    return ApifyKleinanzeigenNormalizer().normalize(RawMarketplaceListing("kleinanzeigen", raw, datetime.now(UTC))).listing


def _analysis() -> VehicleAnalysis:
    return VehicleAnalysis.model_validate({"vehicle": {"structured_source": {"make": "Volkswagen", "model": "Golf", "mileage_km": 174000, "power_ps": 100}, "interpreted_from_listing": {"make": None, "model": None, "variant": "1.6", "registration_year": 2008, "engine": None, "fuel_type": "petrol", "transmission": "manual", "power_kw": None, "engine_cc": None, "tuv_until": None, "accident_free": None}}, "current_faults": [{"component": "air conditioning", "issue": "not working", "severity": "medium", "evidence": "Sanitized", "confidence": 0.9}], "completed_repairs": [{"component": "front brakes", "repair": "recently replaced", "mileage_km": None, "date_or_timeframe": None, "evidence": "Sanitized", "confidence": 0.9}], "maintenance_history": [], "seller_claims": [], "positive_signals": [], "risk_flags": [], "missing_information": [{"topic": "tuv", "reason": "Not stated."}], "condition_summary": "Sanitized fixture.", "overall_condition": "good", "risk_level": "medium", "analysis_confidence": 0.9})


def _repair() -> RepairEstimate:
    item = {"item_type": "uncertainty_reserve", "component": "history", "description": "bounded uncertainty", "evidence_basis": "validated_analysis", "evidence": "Sanitized", "minimum_eur": 120, "expected_eur": 190, "high_eur": 290, "work_complexity": "unknown", "confidence": 0.6, "assumption_note": None}
    return RepairEstimate.model_validate({"required_repairs": [], "near_term_maintenance": [], "uncertainty_items": [item], "cost_summary": {"minimum_total_eur": 120, "expected_total_eur": 190, "high_total_eur": 290, "includes_uncertainty_reserve": True}, "confidence": 0.6})


def _valuation() -> AIValuation:
    return AIValuation.model_validate({"source": "AI_ESTIMATE", "as_is_value": {"conservative_eur": 1500, "expected_eur": 2000, "optimistic_eur": 2400}, "post_repair_resale_value": {"conservative_eur": 2200, "expected_eur": 2600, "optimistic_eur": 3200}, "positive_factors": [], "negative_factors": [], "uncertainties": [], "valuation_basis": ["structured_vehicle_facts"], "confidence": 0.7})


def _financial() -> FinancialAnalysis:
    def scenario(name: str, purchase: int, repair: int, resale: int) -> FinancialScenario:
        investment = purchase + repair
        profit = resale - investment
        return FinancialScenario(scenario=name, purchase_price_eur=purchase, repair_cost_eur=repair, additional_costs_eur=0, total_investment_eur=investment, resale_value_eur=resale, expected_profit_eur=profit, roi_percent=(Decimal(profit) / Decimal(investment) * 100).quantize(Decimal("0.01")))
    return FinancialAnalysis(conservative=scenario("conservative", 1850, 290, 2070), expected=scenario("expected", 1850, 190, 2600), optimistic=scenario("optimistic", 1850, 120, 2950), valuation_source="AI_ESTIMATE", as_is_value_reference={"conservative_eur": 1500, "expected_eur": 2000, "optimistic_eur": 2400})


def _evaluation(decision: str) -> DealEvaluation:
    return DealEvaluation.model_validate({"decision": decision, "financially_eligible": decision != "reject", "reasons": ["expected_roi_below_minimum"] if decision == "reject" else [], "warnings": [] if decision == "reject" else ["conservative_roi_negative", "valuation_ai_only"], "expected_roi_percent": "27.45", "conservative_roi_percent": "-3.27", "optimistic_roi_percent": "49.75", "expected_profit_eur": 560, "expected_total_investment_eur": 2040, "vehicle_risk_level": "medium", "analysis_confidence": 0.9, "repair_confidence": 0.6, "valuation_confidence": 0.7, "valuation_source": "AI_ESTIMATE", "rules_version": "v0.1"})


def _summary(new: int, passed: int) -> RuntimeRunSummary:
    return RuntimeRunSummary(status="success", listings_collected=5, invalid_identity_count=0, previously_seen_count=5 - new, same_batch_duplicate_count=0, new_listings_count=new, normalization_success_count=new, normalization_failure_count=0, basic_filter_passed_count=passed, basic_filter_rejected_count=new - passed, ai_analysis_attempted_count=passed, ai_analysis_failed_count=0, deals_evaluated_count=passed, rejected_deals_count=0, review_candidates_count=passed, strong_candidates_count=0, duration_seconds=3.4)


def main() -> None:
    print("ZERO NEW LISTINGS")
    print(RuntimeReporter.format_summary(_summary(0, 0)))
    print("\nFILTERED-OUT RUN")
    print(RuntimeReporter.format_summary(_summary(3, 0)))
    for decision in ("review", "strong_candidate", "reject"):
        print(f"\n{decision.upper()} CANDIDATE")
        text = RuntimeReporter.format_candidate(_listing(), _analysis(), _repair(), _valuation(), _financial(), _evaluation(decision))
        print(text if text is not None else "No candidate alert (REJECT suppressed).")


if __name__ == "__main__":
    main()
