# Configuration

## Normalization

Normalization has no changing business thresholds. It maps only verified source fields after deduplication, keeps raw evidence, and uses `None` plus warnings for unavailable optional facts. Price, mileage, power, and dealer rules remain configured under `filters` and are evaluated only against canonical normalized fields.

`config/autofinder.yaml` contains non-secret editable settings.

- `scheduler.interval_minutes`: future external scheduler cadence.
- `search`: marketplace, postal code, radius, and exact Kleinanzeigen search URL.
- `collection.listings_per_run`: number of newest listings requested each v0.1 run. The initial value is 5.
- `apify.actor_id`: verified non-secret Actor ID.
- `apify.timeout_seconds`: end-to-end actor collection timeout.
- `deduplication.state_file`: project-relative local JSON state path; its default is `data/state/seen_listings.json`.
- `filters.price`, `filters.mileage`, and `filters.power`: inclusive deterministic bounds checked internally.
- `filters.reject_dealers`: enables structured seller and configured text-indicator rejection.
- `filters.dealer_text_indicators`: normalized case-insensitive exact phrases checked only when dealer rejection is enabled.
- `telegram`: non-secret runtime presentation policy. `runtime_summary_enabled` sends one final summary for each Step 12 run; `candidate_alerts_enabled` permits REVIEW/STRONG alerts; `max_list_items` bounds displayed fault, repair, maintenance, missing-information, risk, and warning lists (initially 4). No quiet-hour or scheduling policy is added.
- `deal_evaluation`: non-secret Step 10 decision-support policy. It defines the minimum expected ROI (20% initially), conservative ROI needed for a strong candidate, three independent 0.0–1.0 confidence thresholds, maximum risk allowed for strong classification (`low` or `medium`), and optional very-high-risk rejection. These are not AI prompts or purchase rules.
- `ai.primary_provider` / `ai.fallback_provider`: the two supported provider names, `groq` then `gemini`.
- `ai.timeout_seconds`: timeout passed to both official SDKs; the committed value is 60 seconds.
- `ai.max_retries_per_provider`: bounded retries after clearly transient provider failures; the committed value is 1.
- `ai.groq.model` / `ai.gemini.model`: non-secret, editable provider model identifiers. See `AI_PROVIDERS.md` for selected models and API details.

The current verified actor accepts an input object with exactly the relevant fields:

```json
{"searchUrl": "<configured Kleinanzeigen URL>", "maxItems": 5}
```

The collector never uses `startUrls`. For a live smoke check, run the smoke script without a count override; it uses the configured v0.1 limit. Do not repeatedly call Apify while debugging downstream code.

## Deterministic filter semantics

Filtering runs only after a valid unseen listing has been persisted. Price, URL, invalid identity, explicit dealer status, configured dealer text, and malformed/out-of-range present mileage or power reject. Missing mileage or power is a warning, not a rejection. Raw evidence is never rewritten. The future AI stage receives only passed listings.

`config/logging.yaml` controls level and rotation limits. Configuration errors fail visibly. The seen-state path must remain project-relative.

`.env` contains local credentials only: Telegram, Apify, Groq, and Gemini names are documented in `.env.example`. `autofinder.core.runtime.load_project_environment(project_root)` is the sole loader: it explicitly loads `<project_root>/.env` and preserves already-injected process values for n8n/deployments. `resolve_project_root()` prefers explicit `AUTOFINDER_PROJECT_ROOT`, then a source-tree root, and only then an upward `config/autofinder.yaml` search for local invocation; it never relies solely on the current working directory. Main, provider smoke scripts, the Apify smoke script, and the development reporter pass their established `PROJECT_ROOT` to this loader. Services then retrieve individual required names without performing their own dotenv discovery. Developers/tools must never print, log, commit, copy, rename, recreate, or expose secret values. Secrets never belong in YAML, source code, logs, test fixtures, or documentation.

## Seen-listing state

Identity is strictly `marketplace:external_listing_id`; title, price, URL text, and description are never fallback keys. State stores only identity metadata and UTC first-seen timestamps. Writes are atomic, and malformed/corrupted JSON fails closed without being replaced. To recover manually, stop AutoFinder, preserve a copy of the corrupt file for diagnosis, then replace it only with a validated state file.
