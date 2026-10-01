# Configuration

`config/autofinder.yaml` contains non-secret editable settings.

- `scheduler.interval_minutes`: future external scheduler cadence.
- `search`: marketplace, postal code, radius, and exact Kleinanzeigen search URL.
- `collection.listings_per_run`: number of newest listings requested each v0.1 run. The initial value is 5.
- `apify.actor_id`: verified non-secret Actor ID.
- `apify.timeout_seconds`: end-to-end actor collection timeout.
- `deduplication.state_file`: project-relative local JSON state path; its default is `data/state/seen_listings.json`.
- `filters` and `ai`: future pipeline configuration, not implemented business behavior.

The current verified actor accepts an input object with exactly the relevant fields:

```json
{"searchUrl": "<configured Kleinanzeigen URL>", "maxItems": 5}
```

The collector never uses `startUrls`. For a live smoke check, run the smoke script without a count override; it uses the configured v0.1 limit. Do not repeatedly call Apify while debugging downstream code.

`config/logging.yaml` controls level and rotation limits. Configuration errors fail visibly. The seen-state path must remain project-relative.

`.env` contains local credentials only: Telegram, Apify, Groq, and Gemini names are documented in `.env.example`. AutoFinder may securely load individual environment values at runtime; developers/tools must never print, log, commit, copy, rename, recreate, or expose secret values. Secrets never belong in YAML, source code, logs, test fixtures, or documentation.

## Seen-listing state

Identity is strictly `marketplace:external_listing_id`; title, price, URL text, and description are never fallback keys. State stores only identity metadata and UTC first-seen timestamps. Writes are atomic, and malformed/corrupted JSON fails closed without being replaced. To recover manually, stop AutoFinder, preserve a copy of the corrupt file for diagnosis, then replace it only with a validated state file.
