# Architecture

AutoFinder is code-first and Python-first. n8n later has a deliberately small boundary: start the local application, schedule it, and optionally monitor successful completion. It must not host business logic.

Python owns collection, raw-evidence preservation, normalization, early deduplication, deterministic filtering, AI orchestration, valuation inputs, canonical financial calculations, deal evaluation, logging, reporting, and application lifecycle.

`ApifyKleinanzeigenCollector` is the initial `ListingCollector` implementation. It receives `SearchConfig`, `CollectionConfig`, and `ApifyConfig`, sends only the verified actor payload fields `searchUrl` and `maxItems`, and returns `CollectionResult`/`RawMarketplaceListing` evidence. A future direct Kleinanzeigen collector can replace it without changing downstream consumers. The configured acquisition batch size is intentionally separate from the later maximum unseen-listing throughput.

Apify/Kleinanzeigen results are acquisition evidence, not trusted business validation: later normalization and filters independently validate important conditions even if the configured search URL contains filters. Raw item mappings are retained intact.

Initial seen-listing memory will be local JSON behind `SeenListingRepository`; a database is later. Groq will be the initial primary AI provider and Gemini the fallback behind `AIProvider`. Initial valuation is explicitly AI-only and must show uncertainty; mobile.de comparables and database history are later. Python, not AI, calculates canonical investment, profit, ROI, and threshold checks.
