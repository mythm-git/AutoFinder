# Changelog

## 2.3.0 — Basic Deterministic Deal Filters

- Added configurable explainable price, URL, seller, dealer-text, mileage, and power checks.
- Added typed filter decisions, stable rejection codes, warnings, and batch statistics.
- Kept filtering separate from AI and preserved raw marketplace evidence.


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
