# Runtime pipeline

## One manual run

From the project root, run:

```powershell
python -m autofinder
```

This performs one bounded run and exits. It is intentionally not an internal scheduler; n8n scheduling is a future step.

## Execution order

1. Load the explicit project-root runtime environment, typed configuration, and central logging.
2. Collect only `collection.listings_per_run` latest Kleinanzeigen records (currently five).
3. Extract stable identity and run persistent early deduplication.
4. Mark every valid unseen record as seen before normalization or filtering.
5. If there are no unseen records, send one `SUCCESS` runtime summary and exit.
6. Normalize unseen records, then apply deterministic basic filters.
7. If no records pass, send one `SUCCESS` runtime summary and exit without AI calls.
8. Sequentially process each passed record through `VehicleAnalyzer`, `RepairEstimator`, `AIValuator`, `FinancialCalculator`, and `DealEvaluator`.
9. Send REVIEW or STRONG_CANDIDATE alerts as each listing completes; REJECT remains aggregate-only.
10. Send exactly one final runtime summary after all candidate alerts.

The pipeline never fetches replacement records after duplicates or filtering. It does not calculate repairs, valuation, financials, or deal decisions itself; those remain in their canonical services.

## Failure behavior

A collector, seen-state, configuration, or composition failure is run-level and yields `FAILED` where the runtime reporter can be initialized. A normalization, AI, repair, valuation, financial, evaluation, or candidate-delivery failure is listing-level: the listing stops, later listings continue, and the final status is `PARTIAL_SUCCESS`.

Valid unseen listings stay marked as seen even if a later expensive stage fails. This v0.1 state policy intentionally avoids repeated processing; retry/pending-state design is deferred.

## Status and exit codes

- `SUCCESS` — exit `0`: intended work completed, including normal zero-new and all-filtered no-op runs.
- `PARTIAL_SUCCESS` — exit `2`: infrastructure completed but at least one listing or candidate alert failed.
- `FAILED` — exit `1`: a critical run-level failure prevented normal continuation.

The final summary uses actual counted results only. Logs use safe identities and stage/error types; they never include prompts, raw listings, provider responses, headers, or credentials.
