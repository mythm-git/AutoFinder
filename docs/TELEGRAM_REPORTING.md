# Telegram reporting

`TelegramClient` is the sole Telegram Bot API transport. It owns timeout handling and secret-safe delivery errors. `DevelopmentReporter` remains unchanged and sends concise post-commit development summaries headed `AutoFinder Development`.

Step 11 adds `RuntimeReporter`, which uses the same client while preserving separate runtime semantics. It can send one enabled `AutoFinder Runtime` summary per future run and candidate alerts for `REVIEW` (`AutoFinder Candidate — REVIEW`) or `STRONG_CANDIDATE` (`AutoFinder Strong Candidate`). `REJECT` never produces an individual alert; it appears only as an aggregate runtime count.

Runtime summaries treat zero new listings and all-filtered listings as successful normal outcomes. Run status is `SUCCESS`, `PARTIAL_SUCCESS`, or `FAILED`. The Step 12 runtime pipeline sends candidate alerts first and exactly one final summary last. A candidate delivery failure produces `PARTIAL_SUCCESS` while later listings and the final summary are still attempted.

Messages use Telegram plain text with no parse mode, so no Markdown/HTML escaping is needed for user-derived fields. Titles, URLs, individual list entries, displayed lists, and the final message are deterministically bounded; the final limit is 4,000 characters. Candidate messages use only validated upstream models, label valuation as AI estimate, translate stable reason codes in the presentation layer, and state that human inspection and approval remain required. A Telegram delivery failure is logged and surfaced; it does not erase completed local work.
