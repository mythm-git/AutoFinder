# Planned pipeline

The implemented boundaries are now: Apify latest five → minimal identity extraction → persistent early deduplication → full canonical normalization → deterministic basic filters → provider-agnostic AI infrastructure. If deduplication finds zero unseen listings, normalization and filtering do no work and the run is a successful no-op. The AI infrastructure is not wired into the runtime and contains no car analysis; valuation, financial calculations, and reporting remain future stages.

This document describes intent, not a completed runtime pipeline.

1. External n8n scheduling later starts Python using the configured interval.
2. `ApifyKleinanzeigenCollector` requests only the configured newest-listings limit using the configured Kleinanzeigen URL; v0.1 is 5.
3. It preserves raw dataset records and safe run metadata in `CollectionResult`.
4. `EarlyDeduplicator` extracts `marketplace + external_listing_id` from each raw record.
5. Every valid unseen identity is atomically marked seen immediately; later filtering must not delay this.
6. Historical duplicates, same-batch duplicates, and records without reliable IDs stop here.
7. If all five are already known, the run ends successfully with zero downstream processing; it does not search deeper for replacements.
8. `BasicDealFilter` applies configured deterministic URL, price, seller, dealer-text, mileage, and power checks without changing raw evidence.
9. Rejected listings remain seen; missing optional mileage/power create warnings rather than rejection.
10. `AIManager` is available for future downstream code: Groq is primary and Gemini is the classified-failure fallback; it returns only locally validated structured data.
11. Future vehicle analysis later defines which normalized evidence is sent and which condition/repair/valuation schema is requested.
12. Future Python performs final financial arithmetic and deal threshold checks.
13. A future runtime/deal reporter emits candidate alerts.

Collection, persistent early deduplication, normalization, deterministic filtering, and generic AI provider infrastructure are implemented. Vehicle analysis, valuation, arithmetic, and deal evaluation are not.
