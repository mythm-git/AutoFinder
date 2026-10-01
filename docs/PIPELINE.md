# Planned pipeline

This document describes intent, not implemented behavior.

1. External n8n schedule starts Python using the configured interval.
2. A collector fetches a newest-first acquisition batch.
3. Listing identity (`marketplace + external_listing_id`) is extracted immediately.
4. Previously seen listings are discarded before expensive work.
5. Acquisition continues only until the configured maximum of unseen listings is reached or its batch is exhausted.
6. Raw marketplace evidence is preserved, then normalized.
7. Cheap deterministic filters run before AI.
8. AI interprets uncertainty, condition, repair inputs, resale ranges, confidence, and risks.
9. Python performs final financial arithmetic and deal threshold checks.
10. A future runtime/deal reporter emits candidate alerts.

No collector, deduplication, filtering, AI, valuation, arithmetic, or deal evaluation exists in Step 1.
