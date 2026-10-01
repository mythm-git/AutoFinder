# Configuration

`config/autofinder.yaml` contains non-secret, editable settings: scheduler interval, search scope and URL, collection limits, future deterministic filter thresholds, and AI provider preference. The requested initial values are present but are not hard-coded in business logic.

`config/logging.yaml` controls level and rotation limits. The application validates its primary configuration at startup and fails visibly for malformed or incompatible values.

`.env` contains local credentials only: Telegram, Apify, Groq, and Gemini names are documented in `.env.example`. Do not commit, print, rename, recreate, or modify `.env`. Secrets never belong in YAML, source code, logs, test fixtures, or documentation.
