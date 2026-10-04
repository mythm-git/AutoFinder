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
cd /d C:\Users\maitham\Desktop\AutoFinder && python -m autofinder
```

AutoFinder loads its own project-root `.env`, performs one complete runtime run, sends its own candidate/runtime Telegram messages, and exits. n8n stores no AutoFinder credentials and performs no business logic.

## Exit codes

- `0`: `SUCCESS`
- `2`: `PARTIAL_SUCCESS`; n8n may present this as a failed command although the Python runtime completed with isolated listing/reporting failures.
- `1`: `FAILED`

There are no automatic retries. One trigger creates one Python process.

## Local operation

This is a native npm n8n setup on Windows, not Docker. n8n must remain running for schedules to fire. Execute Command availability requires `NODES_EXCLUDE=[]`; the local persistent setting is:

```cmd
setx NODES_EXCLUDE "[]"
```

Restart n8n after changing that setting.

Use the n8n UI to manually execute the workflow before publishing/activating it. After activation, inspect **Executions** in the workflow UI for command output, exit behavior, and run history. Deactivate the workflow in the n8n UI to pause scheduling.

## Concurrency

No custom lock is configured in v0.1. AutoFinder normally completes far below the 45-minute interval; overlap policy belongs to Step 14 review.
