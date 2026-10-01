"""Domain-specific exceptions for AutoFinder."""


class AutoFinderError(Exception):
    """Base exception for expected AutoFinder failures."""


class ConfigurationError(AutoFinderError):
    """Raised when non-secret application configuration is invalid."""


class TelegramError(AutoFinderError):
    """Raised when a Telegram notification cannot be delivered."""
