# AutoFinder v2

AutoFinder searches for potentially profitable used cars. This is a new, local-first, Python-first implementation.

## Current status

Step 11 adds a shared-client `RuntimeReporter` that formats one runtime summary and alerts only `REVIEW` / `STRONG_CANDIDATE` deals. Messages are bounded plain text, preserve evidence and upstream calculations, and always require human inspection; `REJECT` deals remain aggregate-only. This step does not wire the runtime pipeline.

Step 10 owns deterministic decisions, Step 9 owns financial arithmetic, Step 8 provides evidence-grounded repair and temporary AI-only valuation inputs, and Step 7 remains their semantic vehicle-analysis boundary.

## Local setup and run

Use a supported Python 3.11+ installation. From this directory, create/activate a virtual environment if desired, then install the development extras:

```powershell
python -m pip install -e ".[dev]"
python -m autofinder
```

Run tests with `python -m pytest`. `python scripts/verify_deduplication.py` performs a local fixture-only verification; it makes no Apify call.

## Configuration and secrets

Operational settings are in `config/autofinder.yaml`; logging settings are in `config/logging.yaml`. `.env` is a local secrets file. AutoFinder securely loads individual required values at runtime (for example, `APIFY_API_TOKEN` and Telegram settings), but developers and tooling must never print, log, commit, copy, or expose those values. `.env.example` contains names only.

## Runtime files

Logs are written to `logs/autofinder.log` with rotation. Successful bounded collector samples may be cached locally in ignored `data/cache/`; future state belongs in `data/state/`.

See `docs/` for architecture, planned pipeline, configuration, development rules, and Telegram reporting.
