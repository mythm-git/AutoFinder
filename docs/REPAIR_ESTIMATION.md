# Repair estimation

`RepairEstimator` accepts only `NormalizedListing` and validated `VehicleAnalysis`, then calls `AIManager`. It does not re-read raw listing text or call a provider SDK directly.

## Evidence and categories

`required_repairs` are limited to unresolved Step 7 faults. `near_term_maintenance` requires evidence that work is due or unresolved; completed repairs and historic maintenance are not automatically charged. Missing information and risk flags may produce separately labelled, bounded `uncertainty_items`, never invented definite repairs.

Each item has rounded whole-euro minimum, expected, and high ranges, an evidence basis, confidence, assumption note, and basic/moderate/specialist work classification. General automotive knowledge is allowed only as explicitly labelled AI background knowledge. These values are AI estimates, not workshop quotes.

## Deterministic arithmetic

Python validates every range and verifies that `cost_summary` exactly equals the sum of all item ranges. The summary explicitly states whether uncertainty reserve is included. Step 8 does not calculate total investment, profit, ROI, or a deal decision.
