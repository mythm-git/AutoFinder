"""Dedicated instructions for evidence-grounded German repair estimation."""

from __future__ import annotations

import json
from typing import Any


SYSTEM_INSTRUCTIONS = """Estimate rounded, practical German repair/maintenance expenditure from the supplied validated evidence only. Return only the requested JSON schema.

Rules:
- `current_faults` may produce `required_repairs`; completed repairs must never be charged again unless explicit evidence says that work remains defective or incomplete.
- Routine maintenance history is not automatically a cost. Include near-term maintenance only when listing evidence indicates it is due or unresolved.
- Missing information and risk flags may create a bounded `uncertainty_reserve`, never an imaginary definite repair.
- General automotive knowledge may inform ranges only when labelled `general_ai_knowledge`; do not assert model-specific failures without listing evidence.
- Costs must be rounded whole euros, with minimum <= expected <= high. High means a reasonable adverse case, not a catastrophe.
- Include every item in exactly one category and make `cost_summary` exactly equal the sum of all listed item ranges. State whether uncertainty reserve is included.
- Do not value the vehicle, estimate resale, calculate profit/ROI, recommend a purchase, or discount labour for DIY ability.
"""


def repair_estimation_user_content(evidence: dict[str, Any]) -> str:
    return "Estimate repair inputs from this validated evidence:\n" + json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
