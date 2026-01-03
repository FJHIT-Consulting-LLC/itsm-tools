"""Tests for Atlassian base client."""

from unittest.mock import MagicMock, patch

import pytest
import responses

from itsm_tools.atlassian.base import AtlassianClient
from itsm_tools.core.exceptions import (
    AuthenticationError,
    ITSMConnectionError,
    NotFoundError,
    ProviderError,
    RateLimitError,
)


@pytest.fixture
def mock_credentials():
    """Mock get_credentials to return test credentials."""
    with patch("itsm_tools.atlassian.base.get_credentials") as mock:
        mock.return_value = MagicMock(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
        )
        yield mock


class TestAtlassianClientInit:
    """Tests for AtlassianClient initialization."""

    def test_init_with_explicit_credentials(self, mock_credentials: MagicMock) -> None:
        """Test initialization with explicit credentials."""
        client = AtlassianClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
        )
        assert client.base_url == "https://test.atlassian.net"
        assert client.timeout == 30
        assert client.max_retries == 3

    def test_init_custom_timeout(self, mock_credentials: MagicMock) -> None:
        """Test initialization with custom timeout."""
        client = AtlassianClient(timeout=60)
        assert client.timeout == 60

    def test_init_custom_retries(self, mock_credentials: MagicMock) -> None:
        """Test initialization with custom retry settings."""
        client = AtlassianClient(max_retries=5, backoff_factor=3.0)
        assert client.max_retries == 5
        assert client.backoff_factor == 3.0


class TestAtlassianClientContextManager:
    """Tests for context manager support."""

    def test_context_manager(self, mock_credentials: MagicMock) -> None:
        """Test using client as context manager."""
        with AtlassianClient() as client:
            assert client is not None
            assert client.base_url == "https://test.atlassian.net"

    def test_close_called_on_exit(self, mock_credentials: MagicMock) -> None:
        """Test that close is called when exiting context."""
        with patch.object(AtlassianClient, "close") as mock_close:
            with AtlassianClient():
                pass
            mock_close.assert_called_once()


class TestAtlassianClientRequests:
    """Tests for HTTP request methods."""

    @responses.activate
    def test_get_request(self, mock_credentials: MagicMock) -> None:
        """Test GET request."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            json={"key": "value"},
            status=200,
        )

        client = AtlassianClient()
        result = client._get("/rest/api/test")
        assert result == {"key": "value"}

    @responses.activate
    def test_post_request(self, mock_credentials: MagicMock) -> None:
        """Test POST request."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/test",
            json={"id": "123"},
            status=201,
        )

        client = AtlassianClient()
        result = client._post("/rest/api/test", json={"name": "test"})
        assert result == {"id": "123"}

    @responses.activate
    def test_put_request(self, mock_credentials: MagicMock) -> None:
        """Test PUT request."""
        responses.add(
            responses.PUT,
            "https://test.atlassian.net/rest/api/test/123",
            json={"updated": True},
            status=200,
        )

        client = AtlassianClient()
        result = client._put("/rest/api/test/123", json={"name": "updated"})
        assert result == {"updated": True}

    @responses.activate
    def test_delete_request(self, mock_credentials: MagicMock) -> None:
        """Test DELETE request."""
        responses.add(
            responses.DELETE,
            "https://test.atlassian.net/rest/api/test/123",
            status=204,
        )

        client = AtlassianClient()
        result = client._delete("/rest/api/test/123")
        assert result is None

    @responses.activate
    def test_request_with_params(self, mock_credentials: MagicMock) -> None:
        """Test request with query parameters."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/search",
            json={"results": []},
            status=200,
        )

        client = AtlassianClient()
        client._get("/rest/api/search", params={"q": "test", "limit": 10})

        assert len(responses.calls) == 1
        assert "q=test" in responses.calls[0].request.url
        assert "limit=10" in responses.calls[0].request.url


class TestAtlassianClientErrorHandling:
    """Tests for error handling."""

    @responses.activate
    def test_401_raises_auth_error(self, mock_credentials: MagicMock) -> None:
        """Test that 401 raises AuthenticationError."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            json={"message": "Unauthorized"},
            status=401,
        )

        client = AtlassianClient()
        with pytest.raises(AuthenticationError) as exc_info:
            client._get("/rest/api/test")

        assert "Authentication failed" in str(exc_info.value)

    @responses.activate
    def test_403_raises_auth_error(self, mock_credentials: MagicMock) -> None:
        """Test that 403 raises AuthenticationError."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            json={"message": "Forbidden"},
            status=403,
        )

        client = AtlassianClient()
        with pytest.raises(AuthenticationError) as exc_info:
            client._get("/rest/api/test")

        assert "Access forbidden" in str(exc_info.value)

    @responses.activate
    def test_404_raises_not_found(self, mock_credentials: MagicMock) -> None:
        """Test that 404 raises NotFoundError."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/issue/FAKE-123",
            json={"errorMessages": ["Issue does not exist"]},
            status=404,
        )

        client = AtlassianClient()
        with pytest.raises(NotFoundError) as exc_info:
            client._get("/rest/api/issue/FAKE-123")

        assert "not found" in str(exc_info.value)

    @responses.activate
    def test_500_raises_provider_error(self, mock_credentials: MagicMock) -> None:
        """Test that 500 raises ProviderError after retries."""
        # Add 4 responses (initial + 3 retries)
        for _ in range(4):
            responses.add(
                responses.GET,
                "https://test.atlassian.net/rest/api/test",
                json={"message": "Internal Server Error"},
                status=500,
            )

        client = AtlassianClient(max_retries=3, backoff_factor=0.01)
        with pytest.raises(ProviderError) as exc_info:
            client._get("/rest/api/test")

        assert exc_info.value.status_code == 500


class TestAtlassianClientRateLimiting:
    """Tests for rate limiting handling."""

    @responses.activate
    def test_429_retries_with_retry_after(self, mock_credentials: MagicMock) -> None:
        """Test that 429 retries using Retry-After header."""
        # First request returns 429 with Retry-After
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            json={"message": "Rate limited"},
            status=429,
            headers={"Retry-After": "1"},
        )
        # Second request succeeds
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            json={"success": True},
            status=200,
        )

        client = AtlassianClient(max_retries=3)
        result = client._get("/rest/api/test")

        assert result == {"success": True}
        assert len(responses.calls) == 2

    @responses.activate
    def test_429_exhausts_retries(self, mock_credentials: MagicMock) -> None:
        """Test that 429 raises RateLimitError after max retries."""
        # All requests return 429
        for _ in range(4):
            responses.add(
                responses.GET,
                "https://test.atlassian.net/rest/api/test",
                json={"message": "Rate limited"},
                status=429,
                headers={"Retry-After": "1"},
            )

        client = AtlassianClient(max_retries=3, backoff_factor=0.01)
        with pytest.raises(RateLimitError) as exc_info:
            client._get("/rest/api/test")

        assert "Rate limit exceeded" in str(exc_info.value)


class TestAtlassianClientRetryLogic:
    """Tests for retry logic with backoff."""

    @responses.activate
    def test_retry_on_500(self, mock_credentials: MagicMock) -> None:
        """Test that 500 errors trigger retry."""
        # First request fails
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            json={"message": "Server Error"},
            status=500,
        )
        # Second request succeeds
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            json={"success": True},
            status=200,
        )

        client = AtlassianClient(max_retries=3, backoff_factor=0.01)
        result = client._get("/rest/api/test")

        assert result == {"success": True}
        assert len(responses.calls) == 2

    @responses.activate
    def test_retry_on_503(self, mock_credentials: MagicMock) -> None:
        """Test that 503 errors trigger retry."""
        # First two requests fail
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            status=503,
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            status=503,
        )
        # Third request succeeds
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            json={"success": True},
            status=200,
        )

        client = AtlassianClient(max_retries=3, backoff_factor=0.01)
        result = client._get("/rest/api/test")

        assert result == {"success": True}
        assert len(responses.calls) == 3

    def test_calculate_backoff(self, mock_credentials: MagicMock) -> None:
        """Test exponential backoff calculation."""
        client = AtlassianClient(backoff_factor=2.0)

        assert client._calculate_backoff(0) == 1.0  # 2^0
        assert client._calculate_backoff(1) == 2.0  # 2^1
        assert client._calculate_backoff(2) == 4.0  # 2^2
        assert client._calculate_backoff(3) == 8.0  # 2^3


class TestAtlassianClientConnectionErrors:
    """Tests for connection error handling."""

    @responses.activate
    def test_timeout_raises_connection_error(self, mock_credentials: MagicMock) -> None:
        """Test that timeout raises ITSMConnectionError."""
        import requests

        # Simulate timeout by raising exception
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            body=requests.exceptions.Timeout("Connection timed out"),
        )
        # Add more for retries
        for _ in range(3):
            responses.add(
                responses.GET,
                "https://test.atlassian.net/rest/api/test",
                body=requests.exceptions.Timeout("Connection timed out"),
            )

        client = AtlassianClient(max_retries=3, backoff_factor=0.01)
        with pytest.raises(ITSMConnectionError) as exc_info:
            client._get("/rest/api/test")

        assert "timed out" in str(exc_info.value)

    @responses.activate
    def test_connection_error_retries(self, mock_credentials: MagicMock) -> None:
        """Test that connection errors trigger retry."""
        import requests

        # First request fails with connection error
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )
        # Second request succeeds
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/test",
            json={"success": True},
            status=200,
        )

        client = AtlassianClient(max_retries=3, backoff_factor=0.01)
        result = client._get("/rest/api/test")

        assert result == {"success": True}


class TestAtlassianClientTestConnection:
    """Tests for test_connection method."""

    @responses.activate
    def test_connection_success(self, mock_credentials: MagicMock) -> None:
        """Test successful connection test."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            json={"baseUrl": "https://test.atlassian.net"},
            status=200,
        )

        client = AtlassianClient()
        assert client.test_connection() is True

    @responses.activate
    def test_connection_fallback_to_myself(self, mock_credentials: MagicMock) -> None:
        """Test connection test falls back to /myself endpoint."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            json={"errorMessages": ["Not found"]},
            status=404,
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/myself",
            json={"accountId": "123"},
            status=200,
        )

        client = AtlassianClient()
        assert client.test_connection() is True

    @responses.activate
    def test_connection_auth_failure(self, mock_credentials: MagicMock) -> None:
        """Test connection test with auth failure."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            json={"message": "Unauthorized"},
            status=401,
        )

        client = AtlassianClient()
        with pytest.raises(AuthenticationError):
            client.test_connection()
