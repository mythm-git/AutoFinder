# Planned pipeline

The implemented boundaries are now: Apify latest five → minimal identity extraction → persistent early deduplication → full canonical normalization → deterministic basic filters → structured vehicle analysis → repair estimation → temporary AI-only valuation → deterministic financial analysis → deterministic deal evaluation. This document describes intent, not a completed runtime pipeline.

1. `ApifyKleinanzeigenCollector` requests only the configured newest-listings limit using the configured Kleinanzeigen URL; v0.1 is 5.
2. Identity extraction and `EarlyDeduplicator` atomically retain unseen source records before downstream work.
3. `ApifyKleinanzeigenNormalizer` produces immutable `NormalizedListing` facts and raw source evidence.
4. `BasicDealFilter` applies deterministic URL, price, seller, mileage, and power rules.
5. `VehicleAnalyzer` creates validated semantic evidence through `AIManager`.
6. `RepairEstimator` consumes `NormalizedListing` plus `VehicleAnalysis` and produces deterministic-sum repair inputs.
7. `AIValuator` consumes `NormalizedListing`, `VehicleAnalysis`, and `RepairEstimate` to produce temporary `AI_ESTIMATE` as-is and post-repair ranges.
8. `FinancialCalculator` deterministically produces conservative, expected, and optimistic full-investment, profit, and ROI scenarios from Step 8 totals and post-repair value ranges.
9. `DealEvaluator` classifies the validated results as `REJECT`, `REVIEW`, or `STRONG_CANDIDATE` using typed configurable rules.
10. Future runtime Telegram reporting, end-to-end pipeline orchestration, and n8n scheduling remain separate stages.

Implemented: collection, early deduplication, normalization, basic filters, generic AI infrastructure, vehicle analysis, repair estimation, AI-only valuation, deterministic financial analysis, and deterministic deal evaluation. Not implemented: runtime alerts, complete orchestration, database, n8n, mobile.de comparables, custom scraping, or image analysis.
