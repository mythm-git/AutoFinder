# AutoFinder Development Rules

1. Keep every AutoFinder artifact inside this repository.
2. Use central logging with console and rotating files; never log secrets.
3. Document every Python module with docstrings, types, and meaningful rationale.
4. Keep project documentation current.
5. Use local Git from the beginning; no remote until explicitly authorized.
6. Ignore `.env` before commits; check staging and generated outputs for secrets.
7. Keep adjustable operational and business values in configuration.
8. Use stable interfaces so collectors, repositories, and AI providers are replaceable.
9. Deduplicate early by marketplace and external listing ID.
10. Perform cheap operations before expensive AI calls.
11. Let AI interpret uncertainty, not deterministic business arithmetic.
12. Let Python calculate canonical financial values.
13. Label early AI-only valuations as estimates with uncertainty.
14. Fail closed when critical data is invalid or unavailable.
15. Preserve raw listing evidence.
16. Use small datasets, fixtures, and caches during development.
17. Remain local-first; do not add deployment infrastructure without instruction.
18. Build one approved step at a time: test, document, inspect, commit, report, stop.
19. Send one concise Telegram development report after each completed step.
20. Reuse the Telegram client for development, runtime, and future deal reporting.
