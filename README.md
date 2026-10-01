# AutoFinder v2

AutoFinder searches for potentially profitable used cars. This is a new, local-first, Python-first implementation; its runtime pipeline has not been implemented yet.

## Current status

Step 1 provides configuration, central rotating logging, an executable foundation, reusable Telegram development reporting, contracts for replaceable integrations, tests, and local Git. It does not scrape, deduplicate, filter listings, call AI, calculate ROI, or score deals.

## Local setup and run

Use a supported Python 3.11+ installation. From this directory, create/activate a virtual environment if desired, then install the development extras:

```powershell
python -m pip install -e ".[dev]"
python -m autofinder
```

Run tests with `python -m pytest`.

## Configuration and secrets

Operational settings are in `config/autofinder.yaml`; logging settings are in `config/logging.yaml`. `.env` is a local secrets file and must never be modified, printed, committed, or copied. Start from `.env.example` only when setting up another local environment.

## Runtime files

Logs are written to `logs/autofinder.log` with rotation. Future state and cache data belong in `data/state/` and `data/cache/`; generated contents are ignored by Git.

See `docs/` for architecture, planned pipeline, configuration, development rules, and Telegram reporting.
