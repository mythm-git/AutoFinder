"""Domain-specific exceptions for AutoFinder."""


class AutoFinderError(Exception):
    """Base exception for expected AutoFinder failures."""


class ConfigurationError(AutoFinderError):
    """Raised when non-secret application configuration is invalid."""


class TelegramError(AutoFinderError):
    """Raised when a Telegram notification cannot be delivered."""


class CollectorError(AutoFinderError):
    """Raised when marketplace acquisition cannot produce validated raw evidence."""


class ApifyConfigurationError(CollectorError):
    """Raised when the local Apify credential or non-secret actor configuration is invalid."""


class ApifyTransportError(CollectorError):
    """Raised when Apify network or API interactions fail without exposing request secrets."""
