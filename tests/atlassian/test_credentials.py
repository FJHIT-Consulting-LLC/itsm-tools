"""Tests for Atlassian credential management."""

import os
from unittest.mock import MagicMock, patch

import pytest

from itsm_tools.atlassian.credentials import (
    DEFAULT_SERVICE,
    ENV_API_TOKEN,
    ENV_BASE_URL,
    ENV_USER_EMAIL,
    AtlassianCredentials,
    _load_dotenv,
    delete_credentials,
    get_credentials,
    save_credentials,
)


class TestGetCredentials:
    """Tests for get_credentials function."""

    def test_explicit_credentials(self) -> None:
        """Test that explicit credentials take precedence."""
        creds = get_credentials(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
        )
        assert creds.base_url == "https://test.atlassian.net"
        assert creds.email == "test@example.com"
        assert creds.api_token == "test-token"

    def test_trailing_slash_removed(self) -> None:
        """Test that trailing slash is removed from base_url."""
        creds = get_credentials(
            base_url="https://test.atlassian.net/",
            email="test@example.com",
            api_token="test-token",
        )
        assert creds.base_url == "https://test.atlassian.net"

    def test_env_variables(self) -> None:
        """Test credential resolution from environment variables."""
        with patch.dict(
            os.environ,
            {
                ENV_BASE_URL: "https://env.atlassian.net",
                ENV_USER_EMAIL: "env@example.com",
                ENV_API_TOKEN: "env-token",
            },
        ):
            creds = get_credentials()
            assert creds.base_url == "https://env.atlassian.net"
            assert creds.email == "env@example.com"
            assert creds.api_token == "env-token"

    def test_explicit_overrides_env(self) -> None:
        """Test that explicit params override environment variables."""
        with patch.dict(
            os.environ,
            {
                ENV_BASE_URL: "https://env.atlassian.net",
                ENV_USER_EMAIL: "env@example.com",
                ENV_API_TOKEN: "env-token",
            },
        ):
            creds = get_credentials(
                base_url="https://explicit.atlassian.net",
            )
            assert creds.base_url == "https://explicit.atlassian.net"
            assert creds.email == "env@example.com"
            assert creds.api_token == "env-token"

    @patch("itsm_tools.atlassian.credentials.keyring")
    def test_keyring_fallback(self, mock_keyring: MagicMock) -> None:
        """Test credential resolution from keyring."""
        mock_keyring.get_password.side_effect = lambda svc, key: {
            "base_url": "https://keyring.atlassian.net",
            "user_email": "keyring@example.com",
            "api_token": "keyring-token",
        }.get(key)

        with patch.dict(os.environ, {}, clear=True):
            # Remove JIRA_* env vars if present
            for var in [ENV_BASE_URL, ENV_USER_EMAIL, ENV_API_TOKEN]:
                os.environ.pop(var, None)

            creds = get_credentials()
            assert creds.base_url == "https://keyring.atlassian.net"
            assert creds.email == "keyring@example.com"
            assert creds.api_token == "keyring-token"

    def test_missing_credentials_raises(self) -> None:
        """Test that missing credentials raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            for var in [ENV_BASE_URL, ENV_USER_EMAIL, ENV_API_TOKEN]:
                os.environ.pop(var, None)

            with patch("itsm_tools.atlassian.credentials.keyring") as mock_keyring:
                mock_keyring.get_password.return_value = None
                mock_keyring.errors.KeyringError = Exception

                with pytest.raises(ValueError) as exc_info:
                    get_credentials()

                assert "Missing Atlassian credentials" in str(exc_info.value)


class TestSaveCredentials:
    """Tests for save_credentials function."""

    @patch("itsm_tools.atlassian.credentials.keyring")
    def test_save_credentials(self, mock_keyring: MagicMock) -> None:
        """Test saving credentials to keyring."""
        save_credentials(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
        )

        assert mock_keyring.set_password.call_count == 3
        mock_keyring.set_password.assert_any_call(
            DEFAULT_SERVICE, "base_url", "https://test.atlassian.net"
        )
        mock_keyring.set_password.assert_any_call(DEFAULT_SERVICE, "user_email", "test@example.com")
        mock_keyring.set_password.assert_any_call(DEFAULT_SERVICE, "api_token", "test-token")

    @patch("itsm_tools.atlassian.credentials.keyring")
    def test_save_with_custom_service(self, mock_keyring: MagicMock) -> None:
        """Test saving credentials with custom service name."""
        save_credentials(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
            service="custom-service",
        )

        mock_keyring.set_password.assert_any_call(
            "custom-service", "base_url", "https://test.atlassian.net"
        )


class TestDeleteCredentials:
    """Tests for delete_credentials function."""

    @patch("itsm_tools.atlassian.credentials.keyring")
    def test_delete_credentials(self, mock_keyring: MagicMock) -> None:
        """Test deleting credentials from keyring."""
        mock_keyring.errors.PasswordDeleteError = Exception

        delete_credentials()

        assert mock_keyring.delete_password.call_count == 3
        mock_keyring.delete_password.assert_any_call(DEFAULT_SERVICE, "base_url")
        mock_keyring.delete_password.assert_any_call(DEFAULT_SERVICE, "user_email")
        mock_keyring.delete_password.assert_any_call(DEFAULT_SERVICE, "api_token")

    @patch("itsm_tools.atlassian.credentials.keyring")
    def test_delete_handles_missing(self, mock_keyring: MagicMock) -> None:
        """Test that delete handles missing credentials gracefully."""

        class PasswordDeleteError(Exception):
            pass

        mock_keyring.errors.PasswordDeleteError = PasswordDeleteError
        mock_keyring.delete_password.side_effect = PasswordDeleteError

        # Should not raise
        delete_credentials()


class TestLoadDotenv:
    """Tests for _load_dotenv function."""

    def test_load_dotenv_basic(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test loading basic .env file."""
        env_file = tmp_path / ".env"  # type: ignore[operator]
        env_file.write_text("KEY1=value1\nKEY2=value2\n")

        with patch("itsm_tools.atlassian.credentials.Path") as mock_path:
            mock_cwd = MagicMock()
            mock_cwd.parents = []
            mock_path.cwd.return_value = mock_cwd

            # Make the mock return the actual temp file path
            mock_env_file = MagicMock()
            mock_env_file.exists.return_value = True
            mock_env_file.__truediv__ = lambda self, name: (
                env_file if name == ".env" else MagicMock()
            )
            mock_cwd.__truediv__ = lambda self, name: env_file if name == ".env" else MagicMock()

        # Direct test with real file
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)  # type: ignore[arg-type]
            result = _load_dotenv()
            assert result.get("KEY1") == "value1"
            assert result.get("KEY2") == "value2"
        finally:
            os.chdir(original_cwd)

    def test_load_dotenv_with_quotes(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test loading .env file with quoted values."""
        env_file = tmp_path / ".env"  # type: ignore[operator]
        env_file.write_text("KEY1=\"double quoted\"\nKEY2='single quoted'\n")

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)  # type: ignore[arg-type]
            result = _load_dotenv()
            assert result.get("KEY1") == "double quoted"
            assert result.get("KEY2") == "single quoted"
        finally:
            os.chdir(original_cwd)

    def test_load_dotenv_skips_comments(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that comments are skipped in .env file."""
        env_file = tmp_path / ".env"  # type: ignore[operator]
        env_file.write_text("# This is a comment\nKEY1=value1\n# Another comment\n")

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)  # type: ignore[arg-type]
            result = _load_dotenv()
            assert result.get("KEY1") == "value1"
            assert "#" not in result
        finally:
            os.chdir(original_cwd)


class TestAtlassianCredentials:
    """Tests for AtlassianCredentials namedtuple."""

    def test_create_credentials(self) -> None:
        """Test creating AtlassianCredentials."""
        creds = AtlassianCredentials(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
        )
        assert creds.base_url == "https://test.atlassian.net"
        assert creds.email == "test@example.com"
        assert creds.api_token == "test-token"

    def test_credentials_unpacking(self) -> None:
        """Test that credentials can be unpacked."""
        creds = AtlassianCredentials(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
        )
        base_url, email, api_token = creds
        assert base_url == "https://test.atlassian.net"
        assert email == "test@example.com"
        assert api_token == "test-token"
