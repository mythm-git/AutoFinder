# Runtime pipeline

The implemented runtime is: native n8n Schedule Trigger every 45 minutes (`Europe/Berlin`) → Execute Command → `cd /d C:\\Users\\maitham\\Desktop\\AutoFinder && python -m autofinder` → Apify latest five → minimal identity extraction → persistent early deduplication and marking seen → canonical normalization → deterministic basic filters → VehicleAnalyzer → RepairEstimator → AIValuator → FinancialCalculator → DealEvaluator → candidate alerts → one final runtime summary. Python performs one run then exits; n8n owns recurrence only.

1. `ApifyKleinanzeigenCollector` requests only the configured newest-listings limit using the configured Kleinanzeigen URL; v0.1 is 5.
2. Identity extraction and `EarlyDeduplicator` atomically retain unseen source records before downstream work.
3. `ApifyKleinanzeigenNormalizer` produces immutable `NormalizedListing` facts and raw source evidence.
4. `BasicDealFilter` applies deterministic URL, price, seller, mileage, and power rules.
5. `VehicleAnalyzer` creates validated semantic evidence through `AIManager`.
6. `RepairEstimator` consumes `NormalizedListing` plus `VehicleAnalysis` and produces deterministic-sum repair inputs.
7. `AIValuator` consumes `NormalizedListing`, `VehicleAnalysis`, and `RepairEstimate` to produce temporary `AI_ESTIMATE` as-is and post-repair ranges.
8. `FinancialCalculator` deterministically produces conservative, expected, and optimistic full-investment, profit, and ROI scenarios from Step 8 totals and post-repair value ranges.
9. `DealEvaluator` classifies the validated results as `REJECT`, `REVIEW`, or `STRONG_CANDIDATE` using typed configurable rules.
10. `RuntimeReporter` sends each successfully completed REVIEW/STRONG candidate alert before exactly one final typed run summary through the shared Telegram client; REJECT has no individual alert.
11. The published native n8n `AutoFinder Scheduler` workflow invokes exactly one process per trigger, with no automatic retry or business logic.

Implemented: collection, early deduplication, normalization, basic filters, generic AI infrastructure, vehicle analysis, repair estimation, AI-only valuation, deterministic financial analysis, deterministic deal evaluation, runtime Telegram reporting, complete one-run orchestration, and external n8n scheduling. Not implemented: database, mobile.de comparables, custom scraping, or image analysis.
