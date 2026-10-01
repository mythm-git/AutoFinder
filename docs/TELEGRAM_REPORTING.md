# Telegram reporting

The shared `TelegramClient` owns Telegram Bot API transport, timeout handling, and secret-safe errors. `DevelopmentReporter` is the only reporter implemented in Step 1 and sends a concise post-commit development summary.

Future `RuntimeReporter` may describe run health, while a future `DealReporter` may send candidate cars. They must reuse `TelegramClient`, but their message types and delivery policy remain separate. A Telegram delivery failure is logged and surfaced; it does not erase completed local implementation work.
