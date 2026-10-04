# AutoFinder v2

AutoFinder searches for potentially profitable used cars. This is a new, local-first, Python-first implementation.

## Current status

Step 13 adds the native n8n 2.35.7 scheduler workflow `AutoFinder Scheduler` (`AFScheduler0001`). It triggers the existing one-run Python process every 45 minutes in `Europe/Berlin`; collection, AI, financial logic, decisions, and Telegram reporting remain in Python.

Step 10 owns deterministic decisions, Step 9 owns financial arithmetic, Step 8 provides evidence-grounded repair and temporary AI-only valuation inputs, and Step 7 remains their semantic vehicle-analysis boundary.

## Local setup and run

Use a supported Python 3.11+ installation. From this directory, create/activate a virtual environment if desired, then install the development extras:

```powershell
python -m pip install -e ".[dev]"
python -m autofinder
```

Run tests with `python -m pytest`. `python -m autofinder` executes one complete real run and exits; it does not provide 45-minute scheduling. `python scripts/verify_runtime_pipeline.py` performs a local fixture-only pipeline verification and makes no external calls.

## Configuration and secrets

Operational settings are in `config/autofinder.yaml`; logging settings are in `config/logging.yaml`. `.env` is a local secrets file. AutoFinder securely loads individual required values at runtime (for example, `APIFY_API_TOKEN` and Telegram settings), but developers and tooling must never print, log, commit, copy, or expose those values. `.env.example` contains names only.

## Runtime files

Logs are written to `logs/autofinder.log` with rotation. Successful bounded collector samples may be cached locally in ignored `data/cache/`; future state belongs in `data/state/`.

See `docs/` for architecture, planned pipeline, configuration, development rules, and Telegram reporting.
