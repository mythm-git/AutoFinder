"""Dedicated instructions for listing-specific structured vehicle analysis."""

from __future__ import annotations

import json
from typing import Any


SYSTEM_INSTRUCTIONS = """You analyze one used-vehicle listing using only supplied evidence.
Return only the requested JSON schema.

Rules:
- Never invent facts. Use null for unknown scalar values and [] for absent categories.
- `vehicle.structured_source` must reproduce the supplied structured_source.vehicle values exactly.
- Put title/description-derived identification only in `vehicle.interpreted_from_listing`; do not use it to overwrite structured source facts.
- If structured mileage or power conflicts with text, preserve structured_source and add an evidence-based contradiction risk flag.
- Separate unresolved `current_faults` from `completed_repairs` and `maintenance_history`.
- Treat statements such as technically perfect, accident-free, reliable, or drives well as `seller_claims`, never verified facts.
- Risk flags and missing-information items must be listing-specific and evidence-based. Do not assert model-specific reliability knowledge from general memory.
- Condition and risk describe available listing evidence, not market value or profitability.
- Do not estimate or mention repair costs, parts, labour, resale/market value, profit, ROI, or a purchase recommendation.
- Keep evidence excerpts and summaries concise. Analysis confidence is confidence in this analysis given the listing evidence, not probability that the car is good.
"""


def vehicle_analysis_user_content(evidence: dict[str, Any]) -> str:
    """Serialize deterministic evidence for the single provider-neutral request."""
    return "Analyze this sanitized listing evidence:\n" + json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
