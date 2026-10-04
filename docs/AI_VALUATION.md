# AI-only valuation

`AIValuator` accepts `NormalizedListing`, validated `VehicleAnalysis`, and validated `RepairEstimate`, then calls `AIManager`. Its only source is the controlled `AI_ESTIMATE` value. It retrieves no real listings, mobile.de comparables, URLs, or live market data, and must never invent them.

## As-is and post-repair values

`as_is_value` estimates private-market value in the disclosed current condition. `post_repair_resale_value` estimates normal private resale after validated required repairs are complete. Each uses a rounded conservative/expected/optimistic range with enforced ordering.

The prompt explicitly resists asking-price anchoring. It uses structured facts and validated analysis first, treats seller claims cautiously, and exposes missing variant/year/TÜV/history as uncertainty. General AI market knowledge is transparent in `valuation_basis`; this is not verified market evidence.

## Anti-double-counting and future replacement

A fault included in required repair cost lowers the as-is value, but should not lower post-repair value again once assumed repaired unless an explicit residual issue remains. Service validation rejects an obvious lower post-repair expected value when required repairs exist. A future mobile.de comparable or hybrid valuator can replace this service without changing repair estimation or the later financial engine. Step 8 contains no profit, ROI, candidate score, or deal decision.


## Verification note

The bounded sanitized live check returned no required repairs and only uncertainty reserve, yet the AI post-repair range remained above the as-is range. This is not treated as a financial conclusion: with no definite repair, the uplift is an AI-only uncertainty/presentation assumption and needs later comparable-market validation. Step 9 must not infer profit or ROI from this observation alone.
