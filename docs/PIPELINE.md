# Planned pipeline

The implemented boundaries are now: Apify latest five → minimal identity extraction → persistent early deduplication → full canonical normalization → deterministic basic filters → structured vehicle analysis through provider-agnostic AI. If deduplication finds zero unseen listings, normalization and filtering do no work and the run is a successful no-op. This document describes intent, not a completed runtime pipeline.

1. `ApifyKleinanzeigenCollector` requests only the configured newest-listings limit using the configured Kleinanzeigen URL; v0.1 is 5.
2. Identity extraction and `EarlyDeduplicator` atomically retain unseen source records before downstream work.
3. `ApifyKleinanzeigenNormalizer` produces immutable `NormalizedListing` facts and raw source evidence.
4. `BasicDealFilter` applies deterministic URL, price, seller, mileage, and power rules.
5. Passed listings enter `VehicleAnalyzer`, which sends only selected canonical facts, listing text, and whitelisted structured attributes to `AIManager`.
6. `AIManager` calls Groq first and Gemini only after a classified retryable failure.
7. A locally validated `VehicleAnalysis` separates source facts, text interpretations, current faults, completed repairs, maintenance, seller claims, risks, and relevant unknowns.
8. Future repair estimation, valuation, financial arithmetic, candidate decisions, and Telegram reporting remain separate stages.

Implemented: collection, early deduplication, normalization, basic filters, generic AI infrastructure, and vehicle/listing analysis. Not implemented: repair estimation, valuation, financial arithmetic, candidate decisions, alerts, database, n8n, mobile.de, custom scraping, or image analysis.
