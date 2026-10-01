# Architecture

AutoFinder is code-first and Python-first. n8n later has a deliberately small boundary: start the local application, schedule it, and optionally monitor successful completion. It must not host business logic.

Python owns collection, raw-evidence preservation, normalization, early deduplication, deterministic filtering, AI orchestration, valuation inputs, canonical financial calculations, deal evaluation, logging, reporting, and application lifecycle.

`ApifyKleinanzeigenCollector` is the initial `ListingCollector` implementation. It receives `SearchConfig`, `CollectionConfig`, and `ApifyConfig`, sends only the verified actor payload fields `searchUrl` and `maxItems`, and returns `CollectionResult`/`RawMarketplaceListing` evidence. A future direct Kleinanzeigen collector can replace it without changing downstream consumers. In v0.1, the collector requests only the configured latest-listings limit (initially 5) and never searches deeper to replace later duplicates.

Apify/Kleinanzeigen results are acquisition evidence, not trusted business validation: later normalization and filters independently validate important conditions even if the configured search URL contains filters. Raw item mappings are retained intact.

`JsonSeenListingRepository` is the initial `SeenListingRepository` implementation. It stores only `marketplace`, external listing ID, and UTC `first_seen_at` under `data/state/seen_listings.json`; a database can replace it later behind the same contract. `EarlyDeduplicator` extracts identity from Apify's raw `id`, persists each valid unseen listing before later filters, and rejects historical, same-batch, or identity-less records. State writes use sibling temporary files followed by atomic replacement. Corrupted state fails closed and is never silently reset. V0.1 assumes one local runtime instance; locking can be strengthened later if needed.

`BasicDealFilter` accepts only raw listings already emitted by early deduplication. It independently checks configured structured values even when the marketplace search URL includes the same limits, because external filter results are evidence rather than trusted enforcement. It returns stable rejection codes versus non-blocking warnings and never mutates raw evidence. Only passed listings will reach future AI work.

Groq will be the initial primary AI provider and Gemini the fallback behind `AIProvider`. Initial valuation is explicitly AI-only and must show uncertainty; mobile.de comparables and database history are later. Python, not AI, calculates canonical investment, profit, ROI, and threshold checks.
