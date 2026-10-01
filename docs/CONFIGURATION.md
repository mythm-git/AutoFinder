# Configuration

`config/autofinder.yaml` contains non-secret editable settings.

- `scheduler.interval_minutes`: future external scheduler cadence.
- `search`: marketplace, postal code, radius, and exact Kleinanzeigen search URL.
- `collection.max_new_listings_per_run`: future maximum unseen listings entering the pipeline.
- `collection.acquisition_batch_size`: default maximum newest records requested by the collector; it is deliberately independent from the unseen-listing limit.
- `apify.actor_id`: verified non-secret Actor ID.
- `apify.timeout_seconds`: end-to-end actor collection timeout.
- `filters` and `ai`: future pipeline configuration, not implemented business behavior.

The current verified actor accepts an input object with exactly the relevant fields:

```json
{"searchUrl": "<configured Kleinanzeigen URL>", "maxItems": 5}
```

The collector never uses `startUrls`. For a live smoke check, pass `--max-items 5`; do not repeatedly call Apify while debugging downstream code.

`config/logging.yaml` controls level and rotation limits. Configuration errors fail visibly.

`.env` contains local credentials only: Telegram, Apify, Groq, and Gemini names are documented in `.env.example`. AutoFinder may securely load individual environment values at runtime; developers/tools must never print, log, commit, copy, rename, recreate, or expose secret values. Secrets never belong in YAML, source code, logs, test fixtures, or documentation.
