"""Dedicated instructions for transparent temporary AI-only market valuation."""

from __future__ import annotations

import json
from typing import Any


SYSTEM_INSTRUCTIONS = """Estimate a rough German private-market vehicle value from supplied validated evidence only. Return only the requested JSON schema.

Rules:
- Source must be `AI_ESTIMATE`. No real comparables, live listings, URLs, prices from websites, or retrieved market data exist here; never invent them.
- Estimate independent vehicle market value. Do not mechanically copy or anchor to the seller asking price.
- `as_is_value` reflects disclosed current condition. `post_repair_resale_value` assumes validated required repairs are completed and the vehicle is sale-ready.
- Do not penalize post-repair value again for a fault that the supplied repair estimate says is repaired, unless an explicit residual issue remains.
- Use structured vehicle facts and validated analysis as primary evidence. Seller claims are not verified facts. General market knowledge is allowed only when declared in valuation_basis.
- Missing variant/year/TÜV/history and other uncertainty should reduce confidence or appear as uncertainty, not become fabricated facts.
- Keep rounded whole-euro ranges ordered conservative <= expected <= optimistic.
- Do not calculate repair totals, investment, profit, ROI, candidate score, or a buying recommendation.
"""


def ai_valuation_user_content(evidence: dict[str, Any]) -> str:
    return "Estimate temporary AI-only valuation from this validated evidence:\n" + json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
