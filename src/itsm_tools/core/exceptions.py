"""Exception hierarchy for itsm-tools."""


class ITSMError(Exception):
    """Base exception for all itsm-tools errors."""

    def __init__(self, message: str, provider: str | None = None, details: dict | None = None):
        """Initialize ITSMError.

        Args:
            message: Error message
            provider: Provider name (e.g., 'atlassian_jira')
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.details = details or {}

    def __str__(self) -> str:
        """Return string representation."""
        if self.provider:
            return f"[{self.provider}] {self.message}"
        return self.message


class AuthenticationError(ITSMError):
    """Authentication failed."""


class RateLimitError(ITSMError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        provider: str | None = None,
        details: dict | None = None,
    ):
        """Initialize RateLimitError.

        Args:
            message: Error message
            retry_after: Seconds until retry is allowed
            provider: Provider name
            details: Additional error details
        """
        super().__init__(message, provider, details)
        self.retry_after = retry_after


class NotFoundError(ITSMError):
    """Resource not found."""

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        provider: str | None = None,
        details: dict | None = None,
    ):
        """Initialize NotFoundError.

        Args:
            message: Error message
            resource_type: Type of resource (e.g., 'issue', 'page')
            resource_id: Resource identifier
            provider: Provider name
            details: Additional error details
        """
        super().__init__(message, provider, details)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(ITSMError):
    """Validation error for input data."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        provider: str | None = None,
        details: dict | None = None,
    ):
        """Initialize ValidationError.

        Args:
            message: Error message
            field: Field that failed validation
            provider: Provider name
            details: Additional error details
        """
        super().__init__(message, provider, details)
        self.field = field


class ConnectionError(ITSMError):
    """Connection to provider failed."""


class PermissionError(ITSMError):
    """Insufficient permissions for operation."""


class ProviderError(ITSMError):
    """Provider-specific error."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        provider: str | None = None,
        details: dict | None = None,
    ):
        """Initialize ProviderError.

        Args:
            message: Error message
            status_code: HTTP status code
            provider: Provider name
            details: Additional error details
        """
        super().__init__(message, provider, details)
        self.status_code = status_code
