"""Custom exceptions for the gmaps-extractor library."""


class GMapsExtractorError(Exception):
    """Base exception for all gmaps-extractor errors."""
    pass


class ServerError(GMapsExtractorError):
    """Raised when the API server cannot be started or reached."""
    pass


class BoundaryError(GMapsExtractorError):
    """Raised when area boundaries cannot be resolved from Nominatim."""
    pass


class ConfigurationError(GMapsExtractorError):
    """Raised when configuration is invalid or incomplete."""
    pass


class RateLimitError(GMapsExtractorError):
    """Raised when rate-limiting exceeds retry capacity."""
    pass


class AuthenticationError(GMapsExtractorError):
    """Raised when proxy or cookie authentication fails."""
    pass
