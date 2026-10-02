"""Run one explicit neutral structured-output smoke test for one AI provider."""

from __future__ import annotations

import argparse
from pathlib import Path

from autofinder.ai.gemini_provider import GeminiProvider
from autofinder.ai.groq_provider import GroqProvider
from autofinder.ai.models import ProviderHealthResponse, StructuredAIRequest
from autofinder.core.config import load_config
from autofinder.core.exceptions import AIError
from autofinder.core.runtime import load_project_environment


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Request one generic schema-constrained response and print only safe metadata."""
    parser = argparse.ArgumentParser(description="Run one provider-specific AutoFinder AI smoke test.")
    parser.add_argument("provider", choices=("groq", "gemini"))
    args = parser.parse_args()
    load_project_environment(PROJECT_ROOT)
    config = load_config(PROJECT_ROOT / "config" / "autofinder.yaml")
    request = StructuredAIRequest(
        purpose="provider_health_smoke",
        system_instructions="Return the required JSON only. This is an infrastructure health check, not vehicle analysis.",
        user_content="Confirm that schema-constrained structured output is working.",
        response_model=ProviderHealthResponse,
        max_output_tokens=120,
    )
    try:
        provider = GroqProvider(config.ai.groq.model, config.ai.timeout_seconds) if args.provider == "groq" else GeminiProvider(config.ai.gemini.model, config.ai.timeout_seconds)
        response = provider.generate_structured(request)
        data = request.response_model.model_validate_json(response.content)
    except AIError as error:
        print(f"provider={args.provider} success=false error_type={type(error).__name__}")
        return 1
    print(f"provider={response.provider} model={response.model} success=true latency_seconds={response.latency_seconds:.3f}")
    print(f"usage={response.usage} request_id={response.request_id} finish_reason={response.finish_reason}")
    print(f"schema_validated={data.status == 'ok'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
