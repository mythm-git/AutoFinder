# Planned pipeline

This document describes intent, not a completed runtime pipeline.

1. External n8n scheduling later starts Python using the configured interval.
2. `ApifyKleinanzeigenCollector` requests a configurable newest-first acquisition batch using the configured Kleinanzeigen URL.
3. It preserves raw dataset records and safe run metadata in `CollectionResult`.
4. A later stage extracts identity (`marketplace + external_listing_id`) immediately.
5. A later duplicate repository discards previously seen listings before expensive work.
6. Acquisition continues only until the configured maximum of unseen listings is reached or its batch is exhausted.
7. Later normalization validates raw source fields, then cheap deterministic filters run before AI.
8. AI later interprets uncertainty, condition, repair inputs, resale ranges, confidence, and risks.
9. Python later performs final financial arithmetic and deal threshold checks.
10. A future runtime/deal reporter emits candidate alerts.

The Apify collector is implemented. Deduplication, normalization, filtering, AI, valuation, arithmetic, and deal evaluation are not.
