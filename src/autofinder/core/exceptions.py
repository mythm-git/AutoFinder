"""Domain-specific exceptions for AutoFinder."""


class AutoFinderError(Exception):
    """Base exception for expected AutoFinder failures."""


class ConfigurationError(AutoFinderError):
    """Raised when non-secret application configuration is invalid."""


class RuntimeCredentialError(ConfigurationError):
    """Raised safely when a required project-root environment variable is unavailable."""


class TelegramError(AutoFinderError):
    """Raised when a Telegram notification cannot be delivered."""


class CollectorError(AutoFinderError):
    """Raised when marketplace acquisition cannot produce validated raw evidence."""


class ApifyConfigurationError(CollectorError):
    """Raised when the local Apify credential or non-secret actor configuration is invalid."""


class ApifyTransportError(CollectorError):
    """Raised when Apify network or API interactions fail without exposing request secrets."""


class IdentityError(AutoFinderError):
    """Raised when a raw marketplace listing lacks a stable external identity."""


class SeenStateError(AutoFinderError):
    """Raised when persistent seen-listing state is malformed, unreadable, or unwritable."""


class NormalizationError(AutoFinderError):
    """Raised when source data cannot safely form a canonical normalized listing."""


class AIError(AutoFinderError):
    """Base exception for expected provider-agnostic AI failures."""


class AIConfigurationError(AIError):
    """Raised when non-secret AI settings or required local credentials are invalid."""


class AIRequestError(AIError):
    """Raised before dispatch when a provider-neutral request is invalid."""


class AIProviderError(AIError):
    """Raised for one safely classified provider attempt failure."""

    def __init__(
        self,
        message: str,
        *,
        kind: str = "provider_error",
        retryable: bool = True,
        stage: str = "provider_request",
        exception_type: str | None = None,
        status_code: int | None = None,
        provider_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable
        self.stage = stage
        self.exception_type = exception_type
        self.status_code = status_code
        self.provider_code = provider_code


class AIResponseValidationError(AIProviderError):
    """Raised when a provider response cannot satisfy the canonical schema."""


class AIAllProvidersFailed(AIError):
    """Raised after primary and permitted fallback attempts have failed."""



class VehicleAnalysisError(AIError):
    """Raised when a listing cannot produce a trustworthy structured analysis."""



class RepairEstimationError(AIError):
    """Raised when validated evidence cannot produce a trustworthy repair estimate."""


class AIValuationError(AIError):
    """Raised when validated evidence cannot produce a trustworthy AI valuation."""



class FinancialAnalysisError(AutoFinderError):
    """Raised when validated monetary inputs cannot produce deterministic scenarios."""


class DealEvaluationError(AutoFinderError):
    """Raised when validated upstream evidence cannot be deterministically classified."""
