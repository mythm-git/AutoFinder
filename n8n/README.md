# AutoFinder Scheduler

## Purpose

This directory contains the secret-free export for the native Windows npm n8n workflow:

- Name: `AutoFinder Scheduler`
- Workflow ID: `AFScheduler0001`
- n8n version verified: `2.35.7`

The workflow has exactly two nodes:

1. Schedule Trigger — every 45 minutes.
2. Execute Command — launches one AutoFinder process.

Its workflow timezone is `Europe/Berlin`.

## Command

The Execute Command node runs:

```cmd
cd /d C:\Users\maitham\Desktop\AutoFinder && python scripts\run_scheduled_autofinder.py
```

The wrapper invokes `python -m autofinder`; AutoFinder loads its own project-root `.env`, performs one complete runtime run, and sends one runtime-summary Telegram message for every invocation, including zero-new-listing and partial-success runs. Candidate alerts are separate from that run summary. n8n stores no AutoFinder credentials and performs no business logic.

## Exit codes

- `0`: `SUCCESS`
- `2`: `PARTIAL_SUCCESS`; the wrapper maps this reported, non-fatal runtime status to n8n exit `0` after AutoFinder has sent its summary.
- `1`: `FAILED`

There are no automatic retries. One trigger creates one Python process.

## Runtime reporting

Runtime summaries are independent of the separate daily Markdown diagnostic-report workflow. A safe audit-persistence failure is logged and cannot prevent the final runtime summary. Prior red scheduler executions were caused by an unhandled audit JSON-serialization error after a recoverable listing-stage failure, before the runtime could reach its final summary.
## Local operation

This is a native npm n8n setup on Windows, not Docker. n8n must remain running for schedules to fire. Execute Command availability requires `NODES_EXCLUDE=[]`; the local persistent setting is:

```cmd
setx NODES_EXCLUDE "[]"
```

Restart n8n after changing that setting.

Use the n8n UI to manually execute the workflow before publishing/activating it. After activation, inspect **Executions** in the workflow UI for command output, exit behavior, and run history. Deactivate the workflow in the n8n UI to pause scheduling.

## Concurrency

No custom lock is configured in v0.1. AutoFinder normally completes far below the 45-minute interval; overlap policy belongs to Step 14 review.

## Scheduler exit-code mapping

`AutoFinder Scheduler` invokes `scripts/run_scheduled_autofinder.py`. The wrapper preserves the runtime's internal `0` (success), `2` (partial success), and `1` (failure) semantics, but maps only `2` to an n8n-success exit so a delivered partial-success Telegram summary does not make the n8n execution red. A genuine `1` or another unexpected non-zero code remains an n8n error.
