# Daily diagnostic reporting

AutoFinder writes one safe, append-only JSONL audit file per Europe/Berlin day under `data/audit/YYYY-MM-DD.jsonl`. It records only newly deduplicated listings and never retains provider payloads, descriptions, contact information, exception messages, or credentials.

The daily scheduler runs at 00:10 Europe/Berlin and generates the previous local day's report at `reports/daily/YYYY-MM-DD.md`. Report files and runtime state are ignored by Git.

Run manually:

```powershell
python scripts/generate_daily_report.py --date yesterday --send
python scripts/generate_daily_report.py --date 2026-10-09 --force --send
```

The report is deterministic: it aggregates canonical filter/deal reason codes and presents already-calculated analysis, repair, valuation, and financial results. It never calls AI or changes policy. Telegram delivery sends the Markdown as a document. A successful send is recorded in `data/report_state/daily_reports.json`; repeat sends are suppressed unless `--force` is requested. If Telegram fails, the local report remains the source of truth.

Detailed evidence is available only from deployment of this feature onward. Collect several days of reports before considering any tuning.
