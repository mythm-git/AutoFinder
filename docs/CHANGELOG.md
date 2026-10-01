# Changelog


## 2.2.0 — Listing Identity and Early Deduplication

- Added stable `marketplace:external_listing_id` identity extraction from raw Apify `id`.
- Added atomic local JSON seen-state persistence and same-batch duplicate protection.
- Added corruption-safe failure behavior, fixture-only verification, and typed deduplication statistics.
## 2.1.0 — Apify Kleinanzeigen Collector

- Added `ApifyKleinanzeigenCollector` behind the stable `ListingCollector` contract.
- Added typed Apify configuration, safe credential loading, API response validation, timeouts, and safe collection metadata.
- Preserved raw Apify listing mappings through `RawMarketplaceListing` and `CollectionResult`.
- Added sanitized fixture-based collector tests and a bounded optional live smoke-test script.
- Documented verified `searchUrl`/`maxItems` actor input and the configurable v0.1 latest-listings limit.

## 2.0.0 — Project Foundation

- Created a clean Python-first AutoFinder v2 foundation.
- Added validated YAML configuration and central rotating logging.
- Added reusable Telegram client and development reporter.
- Added minimal application startup, stable future-facing contracts, tests, and local documentation.
- Deliberately excluded all runtime business logic for later approved steps.
