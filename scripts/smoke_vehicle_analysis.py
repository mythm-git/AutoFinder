"""Run one explicit sanitized vehicle-analysis verification through AIManager."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from autofinder.ai.factory import create_ai_manager
from autofinder.analysis import VehicleAnalyzer
from autofinder.core.config import load_config
from autofinder.core.runtime import load_project_environment
from autofinder.models.collection import RawMarketplaceListing
from autofinder.normalization import ApifyKleinanzeigenNormalizer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "apify_kleinanzeigen_dataset.json"
CASES_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "vehicle_analysis_cases.json"


def main() -> int:
    """Analyze the sanitized completed-repairs case and print safe result metadata."""
    load_project_environment(PROJECT_ROOT)
    config = load_config(PROJECT_ROOT / "config" / "autofinder.yaml")
    raw = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))[0]
    case = next(item for item in json.loads(CASES_FIXTURE.read_text(encoding="utf-8")) if item["name"] == "completed_repairs")
    raw["title"] = case["title"]
    raw["description"] = case["description"]
    listing = ApifyKleinanzeigenNormalizer().normalize(RawMarketplaceListing("kleinanzeigen", raw, datetime.now(UTC))).listing
    result = VehicleAnalyzer(create_ai_manager(config.ai)).analyze(listing)
    analysis = result.analysis
    print(f"provider={result.provider} model={result.model} latency_seconds={result.latency_seconds:.3f} usage={result.usage}")
    print(f"condition={analysis.overall_condition.value} risk={analysis.risk_level.value} confidence={analysis.analysis_confidence:.2f}")
    print(f"counts=current_faults:{len(analysis.current_faults)} completed_repairs:{len(analysis.completed_repairs)} maintenance:{len(analysis.maintenance_history)} seller_claims:{len(analysis.seller_claims)} risk_flags:{len(analysis.risk_flags)} missing_information:{len(analysis.missing_information)}")
    print(f"current_fault_components={[item.component for item in analysis.current_faults]}")
    print(f"completed_repair_components={[item.component for item in analysis.completed_repairs]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())