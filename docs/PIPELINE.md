# Planned pipeline

This document describes intent, not a completed runtime pipeline.

1. External n8n scheduling later starts Python using the configured interval.
2. `ApifyKleinanzeigenCollector` requests only the configured newest-listings limit using the configured Kleinanzeigen URL; v0.1 is 5.
3. It preserves raw dataset records and safe run metadata in `CollectionResult`.
4. A later stage extracts identity (`marketplace + external_listing_id`) immediately.
5. A later duplicate repository marks every newly discovered listing as seen, then discards previously seen listings before expensive work.
6. If all five are already known, the run ends successfully with zero downstream processing; it does not search deeper for replacements.
7. Later normalization validates raw source fields, then cheap deterministic filters run before AI.
8. AI later interprets uncertainty, condition, repair inputs, resale ranges, confidence, and risks.
9. Python later performs final financial arithmetic and deal threshold checks.
10. A future runtime/deal reporter emits candidate alerts.

The Apify collector is implemented. Deduplication, normalization, filtering, AI, valuation, arithmetic, and deal evaluation are not.
