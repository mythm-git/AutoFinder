# Changelog

## 2.8.0 — Deterministic Financial Engine

- Added local-only `FinancialCalculator` and canonical conservative, expected, and optimistic post-repair financial scenarios.
- Added traceable full-investment, profit, and two-decimal deterministic ROI arithmetic using validated Step 8 repair totals and valuation ranges.
- Deliberately excluded AI calls, candidate/deal decisions, thresholds, and runtime alerts.

## 2.7.0 — Repair Estimation and AI Valuation

- Added separate provider-neutral repair estimation and temporary AI-only valuation contracts over validated Step 7 evidence.
- Added deterministic verification of aggregate repair totals, bounded uncertainty reserve, and as-is/post-repair AI valuation ranges.
- Deliberately excluded total investment, profit, ROI, candidate decisions, live comparables, and runtime alerts.


## 2.6.0 — Structured Vehicle Analysis

- Added provider-neutral `VehicleAnalysis` Pydantic models with explicit source-fact, text-interpretation, fault, repair, maintenance, seller-claim, risk, and missing-information separation.
- Added deterministic evidence building from `NormalizedListing`, source-fact integrity checks, fixture-only analyzer tests, and a bounded sanitized live-analysis utility.
- Deliberately excluded monetary repair estimates, valuation, profit, ROI, candidate scoring, image analysis, and runtime wiring.


## 2.5.2 — Structured AI Provider Verification

- Added non-mutating provider-local schema adapters: Groq strict object closure and Gemini single-string `const` to `enum` compatibility.
- Switched Gemini structured generation to the documented `google-genai` Interactions API request shape and added safe provider failure diagnostics.
- Verified one bounded neutral live request for each configured provider with canonical local Pydantic validation and safe usage/latency metadata.

## 2.5.1 — Runtime Credential Loading Fix

- Centralized explicit `<PROJECT_ROOT>/.env` loading in `autofinder.core.runtime`, independent of the current working directory.
- Routed main, provider/Apify smoke scripts, and development reporting through the shared loader; individual integrations now only retrieve already-loaded named credentials.

## 2.5.0 — Provider-Agnostic AI Infrastructure

- Added a Pydantic-backed canonical structured-output contract, Groq primary adapter, Gemini fallback adapter, local validation, bounded retries, timeout configuration, and safe usage/latency metadata.
- Added fixture-only provider/fallback tests plus an explicit one-shot neutral provider smoke-test utility.
- Deliberately excluded all car-analysis prompts, valuation, repair, financial, and runtime reporting logic.


## 2.4.0 — Canonical Listing Normalization

- Added the canonical `NormalizedListing` domain model and an Apify-to-domain normalizer.
- Preserved immutable raw source evidence and explicit missing-value warnings.
- Refactored `BasicDealFilter` to consume normalized fields instead of Apify payload paths.
- Added fixture-only normalization and ordering verification.

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
