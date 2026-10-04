"""Verify five local deterministic Step 10 decision cases (no network or .env)."""

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

from autofinder.analysis.models import VehicleAnalysis
from autofinder.core.config import load_config
from autofinder.deals import DealEvaluator
from autofinder.financial.models import FinancialAnalysis, FinancialScenario
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.models import AIValuation


def _listing():
    raw = json.loads((PROJECT_ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json").read_text(encoding="utf-8"))[0]
    return ApifyKleinanzeigenNormalizer().normalize(RawMarketplaceListing("kleinanzeigen", raw, datetime.now(UTC))).listing


def _analysis(risk: str) -> VehicleAnalysis:
    flags = [] if risk not in {"high", "very_high"} else [{"category": "limited_information", "explanation": "Sanitized risk.", "evidence": "Sanitized fixture.", "confidence": 0.8}]
    return VehicleAnalysis.model_validate({
        "vehicle": {"structured_source": {"make": None, "model": None, "mileage_km": None, "power_ps": None}, "interpreted_from_listing": {"make": None, "model": None, "variant": None, "registration_year": None, "engine": None, "fuel_type": None, "transmission": None, "power_kw": None, "engine_cc": None, "tuv_until": None, "accident_free": None}},
        "current_faults": [], "completed_repairs": [], "maintenance_history": [], "seller_claims": [], "positive_signals": [], "risk_flags": flags, "missing_information": [],
        "condition_summary": "Sanitized deterministic fixture.", "overall_condition": "average", "risk_level": risk, "analysis_confidence": 0.85,
    })


def _repair() -> RepairEstimate:
    return RepairEstimate.model_validate({"required_repairs": [], "near_term_maintenance": [], "uncertainty_items": [], "cost_summary": {"minimum_total_eur": 0, "expected_total_eur": 0, "high_total_eur": 0, "includes_uncertainty_reserve": False}, "confidence": 0.75})


def _valuation() -> AIValuation:
    return AIValuation.model_validate({"source": "AI_ESTIMATE", "as_is_value": {"conservative_eur": 1000, "expected_eur": 1200, "optimistic_eur": 1400}, "post_repair_resale_value": {"conservative_eur": 1200, "expected_eur": 1400, "optimistic_eur": 1600}, "positive_factors": [], "negative_factors": [], "uncertainties": [], "valuation_basis": ["structured_vehicle_facts"], "confidence": 0.78})


def _financial(conservative: int, expected: int, optimistic: int) -> FinancialAnalysis:
    def scenario(name: str, roi: int) -> FinancialScenario:
        profit = roi * 10
        return FinancialScenario(scenario=name, purchase_price_eur=1000, repair_cost_eur=0, additional_costs_eur=0, total_investment_eur=1000, resale_value_eur=1000 + profit, expected_profit_eur=profit, roi_percent=Decimal(str(roi)))
    return FinancialAnalysis(conservative=scenario("conservative", conservative), expected=scenario("expected", expected), optimistic=scenario("optimistic", optimistic), valuation_source="AI_ESTIMATE", as_is_value_reference={"conservative_eur": 1000, "expected_eur": 1200, "optimistic_eur": 1400})


def main() -> None:
    evaluator = DealEvaluator(load_config(PROJECT_ROOT / "config" / "autofinder.yaml").deal_evaluation)
    cases = (
        ("CASE 1 — Current Step 9 fixture equivalent", -27, -1, 24, "medium"),
        ("CASE 2 — Profitable but downside-negative", -4, 32, 61, "medium"),
        ("CASE 3 — Strong profitable case", 8, 31, 55, "medium"),
        ("CASE 4 — Profitable but high risk", 10, 35, 60, "high"),
        ("CASE 5 — Profitable but very-high risk", 10, 35, 60, "very_high"),
    )
    for title, conservative, expected, optimistic, risk in cases:
        result = evaluator.evaluate(_listing(), _analysis(risk), _repair(), _valuation(), _financial(conservative, expected, optimistic))
        print(f"{title}: {result.decision.value.upper()} reasons={[code.value for code in result.reasons]}")


if __name__ == "__main__":
    main()
