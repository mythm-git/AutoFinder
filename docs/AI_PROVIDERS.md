# AI providers

## Boundary

Future code uses `AIManager.generate_structured(StructuredAIRequest)` rather than a provider SDK. A request contains a purpose, system instructions, user content, optional output-token cap, schema name, and one Pydantic response model. That Pydantic model is the canonical schema source: its JSON Schema is adapted by both provider adapters and the returned JSON is validated again with `model_validate_json` before a `StructuredAIResult` is returned.

`StructuredAIResult` contains only validated final data plus successful provider/model, latency, optional input/output/total token counts, a bounded safe provider request ID, finish metadata, and safe per-attempt summaries. It never preserves provider reasoning, raw responses, credentials, or authorization headers.

## Configured providers

- Primary: Groq, model `openai/gpt-oss-120b`.
- Fallback: Gemini, model `gemini-3.8-flash`.
- Timeout: 60 seconds for each SDK call.
- Retry policy: one retry per provider, then at most one fallback provider; no loops.

Groq is called through the official `groq` Python SDK Chat Completions API with `response_format.type=json_schema`, a canonical schema, and `strict=true`. Groq's official [Structured Outputs documentation](https://console.groq.com/docs/structured-outputs) lists `openai/gpt-oss-120b` as supporting strict structured output and documents the strict-mode all-required/closed-object constraints. Its [rate-limit documentation](https://console.groq.com/docs/rate-limits) specifies HTTP 429 for rate limits and its [API reference](https://console.groq.com/docs/api-reference) documents response usage metadata.

Gemini is called through the official `google-genai` Python SDK's current `client.interactions.create(...)` API. It passes `response_format={"type": "text", "mime_type": "application/json", "schema": ...}` and bounded `generation_config` settings. Google's [Interactions migration guide](https://ai.google.dev/gemini-api/docs/migrate-to-interactions) and [Interactions API reference](https://ai.google.dev/api/interactions-api-v1) document that shape; [Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) documents JSON Schema/Pydantic support, and the [Gemini 3.8 Flash model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) lists structured output support for `gemini-3.8-flash`.

## Provider schema compatibility

Adapters derive independent deep copies from the one canonical Pydantic JSON Schema. Groq recursively closes every object and marks all properties required for strict mode. Gemini recursively translates Pydantic's single string `Literal` form (`const: "ok"`) into Gemini's supported equivalent (`type: "string", enum: ["ok"]`); it preserves existing multi-value enums, nullable `anyOf` branches, numeric bounds, object definitions, and array items. Provider output is always validated again against the unchanged canonical Pydantic model.

The final bounded neutral live checks passed: Groq `openai/gpt-oss-120b` (0.697 seconds; 252 input / 115 output / 367 total tokens) and Gemini `gemini-3.8-flash` (6.074 seconds; 29 input / 35 output / 64 total tokens).
## Failure policy

Adapters classify rate limits, timeouts/transport interruptions, server errors, malformed/empty structured responses, and local schema validation failures as retryable. The manager logs safe provider/model/purpose/kind metadata, optionally retries that provider once, then activates Gemini only when Groq's classified retryable attempts are exhausted. Invalid local requests, unsupported configuration, and non-retryable API/client errors stop without a pointless fallback. If both permitted providers fail, `AIAllProvidersFailed` is raised and no fake data is returned.

All provider calls are time-bounded. Token metadata is captured only when the SDK supplies it; unavailable values remain `None`, and no cost or quota business logic exists.

## Security and scope

Keys are read by name from the ignored local environment only: `GROQ_API_KEY` and `GEMINI_API_KEY`. The central runtime loader explicitly loads `<PROJECT_ROOT>/.env` before adapters retrieve a key by name; adapters never perform dotenv discovery. Keys are not written to YAML, logs, exceptions, fixtures, smoke output, documentation examples, or Git. Normal tests use injected fakes and make zero network calls. `scripts/smoke_ai_provider.py groq` and `scripts/smoke_ai_provider.py gemini` are explicit one-request neutral health checks.

Step 6 intentionally defines no vehicle condition, repair, valuation, resale, ROI, candidate-scoring, or runtime reporting prompt. Those require a later approved schema and evidence boundary.
