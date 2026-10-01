# Architecture

AutoFinder is code-first and Python-first. n8n later has a deliberately small boundary: start the local application, schedule it, and optionally monitor successful completion. It must not host business logic.

Python owns collection, raw-evidence preservation, normalization, early deduplication, deterministic filtering, AI orchestration, valuation inputs, canonical financial calculations, deal evaluation, logging, reporting, and application lifecycle.

The initial collector will use Apify for Kleinanzeigen and implement the `ListingCollector` contract, allowing a future direct Kleinanzeigen collector to replace it. Initial seen-listing memory will be local JSON behind `SeenListingRepository`; a database is later. Groq will be the initial primary AI provider and Gemini the fallback behind `AIProvider`. Initial valuation is explicitly AI-only and must show uncertainty; mobile.de comparables and database history are later. Python, not AI, calculates canonical investment, profit, ROI, and threshold checks.
