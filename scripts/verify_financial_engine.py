"""Run the local-only Step 9 financial fixture verification (no network or .env)."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from autofinder.financial import FinancialCalculator
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer
from autofinder.repair.models import RepairEstimate
from autofinder.valuation.models import AIValuation


RAW_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json"


def _fixture_inputs():
    payload = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))[0]
    listing = ApifyKleinanzeigenNormalizer().normalize(
        RawMarketplaceListing("kleinanzeigen", payload, datetime.now(UTC))
    ).listing
    repair = RepairEstimate.model_validate(
        {"required_repairs": [], "near_term_maintenance": [],
         "uncertainty_items": [{"item_type": "uncertainty_reserve", "component": "documented uncertainty",
             "description": "Bounded Step 8 uncertainty reserve", "evidence_basis": "validated_analysis",
             "evidence": "Validated Step 7 missing-information evidence", "minimum_eur": 120,
             "expected_eur": 190, "high_eur": 290, "work_complexity": "unknown",
             "confidence": 0.5, "assumption_note": "No definite repair is invented."}],
         "cost_summary": {"minimum_total_eur": 120, "expected_total_eur": 190,
             "high_total_eur": 290, "includes_uncertainty_reserve": True}, "confidence": 0.5}
    )
    valuation = AIValuation.model_validate(
        {"source": "AI_ESTIMATE",
         "as_is_value": {"conservative_eur": 1500, "expected_eur": 2000, "optimistic_eur": 2500},
         "post_repair_resale_value": {"conservative_eur": 2000, "expected_eur": 2600, "optimistic_eur": 3200},
         "positive_factors": [], "negative_factors": [], "uncertainties": ["Sanitized fixture uncertainty."],
         "valuation_basis": ["structured_vehicle_facts"], "confidence": 0.5}
    )
    return listing, repair, valuation


def main() -> None:
    listing, repair, valuation = _fixture_inputs()
    analysis = FinancialCalculator().calculate(listing, repair, valuation)
    print(f"Purchase: €{analysis.expected.purchase_price_eur}")
    for name, scenario in (("CONSERVATIVE", analysis.conservative), ("EXPECTED", analysis.expected), ("OPTIMISTIC", analysis.optimistic)):
        print(name)
        print(f"Repair: €{scenario.repair_cost_eur}")
        print(f"Investment: €{scenario.total_investment_eur}")
        print(f"Resale: €{scenario.resale_value_eur}")
        print(f"Profit: €{scenario.expected_profit_eur}")
        print(f"ROI: {scenario.roi_percent}%")


if __name__ == "__main__":
    main()
