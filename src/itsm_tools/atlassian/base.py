"""Base client for Atlassian APIs with shared auth and request logic.

This module provides a base HTTP client for all Atlassian services (Jira,
Confluence, JSM) with:
- Automatic credential resolution
- Retry logic with exponential backoff
- Rate limiting handling (429 responses)
- Request/response logging

Example:
    from itsm_tools.atlassian.base import AtlassianClient

    class JiraClient(AtlassianClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._api_path = "/rest/api/3"

        def get_issue(self, key: str) -> dict:
            return self._get(f"{self._api_path}/issue/{key}")
"""

import logging
import time
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from itsm_tools.atlassian.credentials import AtlassianCredentials, get_credentials
from itsm_tools.core.exceptions import (
    AuthenticationError,
    ITSMConnectionError,
    NotFoundError,
    ProviderError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_RETRY_STATUSES = (429, 500, 502, 503, 504)


class AtlassianClient:
    """Base HTTP client for Atlassian APIs.

    Provides shared functionality for Jira, Confluence, and JSM clients:
    - Automatic credential resolution from env vars, keyring, or .env files
    - HTTP Basic Auth with API tokens
    - Retry logic with exponential backoff
    - Rate limiting handling with Retry-After header support
    - Request/response logging

    Attributes:
        base_url: Atlassian instance base URL
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
    """

    provider_name = "atlassian"

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        service: str | None = None,
    ) -> None:
        """Initialize the Atlassian client.

        Args:
            base_url: Atlassian instance URL (e.g., https://company.atlassian.net)
            email: User email for authentication
            api_token: API token for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            backoff_factor: Exponential backoff multiplier
            service: Keyring service name for credential lookup
        """
        # Resolve credentials
        creds = get_credentials(
            base_url=base_url,
            email=email,
            api_token=api_token,
            service=service or "itsm-tools-atlassian",
        )
        self._credentials: AtlassianCredentials = creds
        self.base_url = creds.base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # Create session for connection pooling
        self._session = requests.Session()
        self._session.auth = HTTPBasicAuth(creds.email, creds.api_token)
        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        logger.debug(
            "Initialized %s client for %s (user: %s)",
            self.provider_name,
            self.base_url,
            creds.email,
        )

    def __enter__(self) -> "AtlassianClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - close session."""
        self.close()

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
        logger.debug("Closed %s client session", self.provider_name)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        retry_statuses: tuple[int, ...] = DEFAULT_RETRY_STATUSES,
    ) -> requests.Response:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: API path (appended to base_url)
            params: Query parameters
            json: JSON body (will be serialized)
            data: Raw body data
            headers: Additional headers
            retry_statuses: HTTP status codes that trigger retry

        Returns:
            Response object

        Raises:
            AuthenticationError: If authentication fails (401)
            NotFoundError: If resource not found (404)
            RateLimitError: If rate limit exceeded and retries exhausted
            ITSMConnectionError: If connection fails
            ProviderError: For other HTTP errors
        """
        url = f"{self.base_url}{path}"
        request_headers = dict(self._session.headers)
        if headers:
            request_headers.update(headers)

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    "%s %s (attempt %d/%d)",
                    method,
                    url,
                    attempt + 1,
                    self.max_retries + 1,
                )

                response = self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    data=data,
                    headers=request_headers,
                    timeout=self.timeout,
                )

                # Log response
                logger.debug(
                    "%s %s -> %d (%d bytes)",
                    method,
                    path,
                    response.status_code,
                    len(response.content),
                )

                # Handle specific status codes
                if response.status_code == 401:
                    raise AuthenticationError(
                        "Authentication failed. Check your credentials.",
                        provider=self.provider_name,
                        details={"status_code": 401},
                    )

                if response.status_code == 403:
                    raise AuthenticationError(
                        "Access forbidden. Check your permissions.",
                        provider=self.provider_name,
                        details={"status_code": 403, "url": url},
                    )

                if response.status_code == 404:
                    raise NotFoundError(
                        f"Resource not found: {path}",
                        provider=self.provider_name,
                        details={"status_code": 404, "url": url},
                    )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = self._get_retry_after(response, attempt)
                    if attempt < self.max_retries:
                        logger.warning(
                            "Rate limited. Waiting %d seconds before retry.",
                            retry_after,
                        )
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(
                        "Rate limit exceeded. Try again later.",
                        retry_after=retry_after,
                        provider=self.provider_name,
                        details={"status_code": 429},
                    )

                # Handle retryable server errors
                if response.status_code in retry_statuses and attempt < self.max_retries:
                    wait_time = self._calculate_backoff(attempt)
                    logger.warning(
                        "Server error %d. Waiting %.1f seconds before retry.",
                        response.status_code,
                        wait_time,
                    )
                    time.sleep(wait_time)
                    continue

                # Raise for other errors
                if response.status_code >= 400:
                    error_body = self._safe_json(response)
                    raise ProviderError(
                        f"Request failed: {response.status_code}",
                        status_code=response.status_code,
                        provider=self.provider_name,
                        details={"url": url, "response": error_body},
                    )

                return response

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = self._calculate_backoff(attempt)
                    logger.warning(
                        "Request timed out. Waiting %.1f seconds before retry.",
                        wait_time,
                    )
                    time.sleep(wait_time)
                    continue

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = self._calculate_backoff(attempt)
                    logger.warning(
                        "Connection error. Waiting %.1f seconds before retry.",
                        wait_time,
                    )
                    time.sleep(wait_time)
                    continue

            except (AuthenticationError, NotFoundError, RateLimitError, ProviderError):
                raise

        # All retries exhausted
        if isinstance(last_exception, requests.exceptions.Timeout):
            raise ITSMConnectionError(
                f"Request timed out after {self.max_retries + 1} attempts",
                provider=self.provider_name,
                details={"url": url, "timeout": self.timeout},
            ) from last_exception

        if isinstance(last_exception, requests.exceptions.ConnectionError):
            raise ITSMConnectionError(
                f"Connection failed after {self.max_retries + 1} attempts",
                provider=self.provider_name,
                details={"url": url},
            ) from last_exception

        raise ProviderError(
            "Request failed after all retry attempts",
            provider=self.provider_name,
            details={"url": url},
        )

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a GET request and return JSON response.

        Args:
            path: API path
            params: Query parameters
            **kwargs: Additional arguments passed to _request

        Returns:
            Parsed JSON response
        """
        response = self._request("GET", path, params=params, **kwargs)
        return dict(response.json())

    def _post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a POST request and return JSON response.

        Args:
            path: API path
            json: JSON body
            **kwargs: Additional arguments passed to _request

        Returns:
            Parsed JSON response
        """
        response = self._request("POST", path, json=json, **kwargs)
        if response.status_code == 204:
            return {}
        return dict(response.json())

    def _put(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a PUT request and return JSON response.

        Args:
            path: API path
            json: JSON body
            **kwargs: Additional arguments passed to _request

        Returns:
            Parsed JSON response
        """
        response = self._request("PUT", path, json=json, **kwargs)
        if response.status_code == 204:
            return {}
        return dict(response.json())

    def _delete(
        self,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Make a DELETE request.

        Args:
            path: API path
            **kwargs: Additional arguments passed to _request

        Returns:
            Parsed JSON response or None for 204 responses
        """
        response = self._request("DELETE", path, **kwargs)
        if response.status_code == 204:
            return None
        return dict(response.json())

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        return self.backoff_factor**attempt

    def _get_retry_after(self, response: requests.Response, attempt: int) -> int:
        """Get retry delay from response or calculate backoff.

        Args:
            response: HTTP response with potential Retry-After header
            attempt: Current attempt number

        Returns:
            Delay in seconds
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                pass
        return int(self._calculate_backoff(attempt))

    def _safe_json(self, response: requests.Response) -> dict[str, Any] | str:
        """Safely parse JSON response, returning raw text on failure.

        Args:
            response: HTTP response

        Returns:
            Parsed JSON or response text
        """
        try:
            return dict(response.json())
        except (ValueError, TypeError):
            return response.text

    def test_connection(self) -> bool:
        """Test the connection to the Atlassian instance.

        Returns:
            True if connection is successful

        Raises:
            AuthenticationError: If authentication fails
            ITSMConnectionError: If connection fails
        """
        try:
            # Try to access the server info endpoint (available on most Atlassian APIs)
            self._get("/rest/api/3/serverInfo")
            logger.info("Connection test successful for %s", self.base_url)
            return True
        except NotFoundError:
            # Some instances may not have serverInfo, try alternative
            try:
                self._get("/rest/api/3/myself")
                logger.info("Connection test successful for %s", self.base_url)
                return True
            except NotFoundError:
                # If both fail with 404, connection works but endpoints differ
                logger.info("Connection test successful for %s (auth verified)", self.base_url)
                return True
