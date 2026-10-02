"""Provider-agnostic structured AI infrastructure."""

from autofinder.ai.factory import create_ai_manager
from autofinder.ai.manager import AIManager
from autofinder.ai.models import ProviderHealthResponse, StructuredAIRequest, StructuredAIResult

__all__ = ["AIManager", "ProviderHealthResponse", "StructuredAIRequest", "StructuredAIResult", "create_ai_manager"]
