# Deterministic Financial Engine

## Purpose and boundary

Step 9 converts already validated Step 8 monetary inputs into transparent financial outcomes. FinancialCalculator accepts a NormalizedListing, RepairEstimate, and AIValuation, then returns FinancialAnalysis.

It does not call AI, providers, web services, or marketplaces. It does not reinterpret listing evidence, estimate repairs or values, choose a candidate, or apply a minimum-ROI rule.

## Full-investment formula

Every scenario exposes its inputs:

    total_investment = purchase_price + repair_cost + additional_costs
    profit = resale_value - total_investment
    ROI percent = profit / total_investment * 100

Current additional costs default to exactly €0. The calculator accepts an explicit non-negative whole-euro amount so later deterministic costs—such as transport or detailing—can be introduced without altering the formulas. It never adds an invented reserve; Step 8 uncertainty reserves are already included in RepairEstimate totals.

## Fixed scenario mapping

| Scenario | Repair total | Post-repair resale value |
| --- | --- | --- |
| Conservative | high | conservative |
| Expected | expected | expected |
| Optimistic | minimum | optimistic |

The post-repair range is used because the intended workflow is purchase, complete evidenced work, then resell. The existing as-is range is preserved as reference only; it is not substituted into the repaired-resale ROI calculation.

## Arithmetic and validation

Current monetary values are whole integer euros. Python uses integer arithmetic for money and Decimal only for ROI, rounded once with ROUND_HALF_UP to two decimal places. Inputs must have a positive purchase price, non-negative repair/additional/resale values, and positive total investment. Each FinancialScenario independently verifies its own investment, profit, and rounded ROI arithmetic.

Losses remain losses: negative profit and negative ROI are returned without clamping. Invalid upstream model-constructed ranges fail clearly rather than being corrected.

## Scope limitation

FinancialAnalysis reports outcomes only. It contains no candidate/deal decision, score, threshold, buy/reject status, or external comparable data. Step 10 will interpret the deterministic scenarios into explicit deal rules.
