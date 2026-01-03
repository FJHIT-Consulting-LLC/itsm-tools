"""Cross-platform credential management for Atlassian APIs.

Credentials are resolved in the following order:
1. Explicit parameters passed to the client
2. Environment variables (JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN)
3. System keyring (via keyring library)
4. .env file in current directory or parent directories

Example:
    from itsm_tools.atlassian.credentials import get_credentials

    # Auto-discover credentials
    base_url, email, token = get_credentials()

    # Or with explicit service name
    base_url, email, token = get_credentials(service="confluence-cli")
"""

import logging
import os
from pathlib import Path
from typing import NamedTuple

import keyring

logger = logging.getLogger(__name__)

# Default keyring service name
DEFAULT_SERVICE = "itsm-tools-atlassian"

# Environment variable names
ENV_BASE_URL = "JIRA_BASE_URL"
ENV_USER_EMAIL = "JIRA_USER_EMAIL"
ENV_API_TOKEN = "JIRA_API_TOKEN"  # noqa: S105

# Keyring account names
KEYRING_BASE_URL = "base_url"
KEYRING_EMAIL = "user_email"
KEYRING_TOKEN = "api_token"  # noqa: S105


class AtlassianCredentials(NamedTuple):
    """Atlassian API credentials."""

    base_url: str
    email: str
    api_token: str


def get_credentials(
    base_url: str | None = None,
    email: str | None = None,
    api_token: str | None = None,
    service: str = DEFAULT_SERVICE,
) -> AtlassianCredentials:
    """Get Atlassian credentials from various sources.

    Resolution order:
    1. Explicit parameters
    2. Environment variables
    3. System keyring
    4. .env file

    Args:
        base_url: Explicit base URL (overrides other sources)
        email: Explicit email (overrides other sources)
        api_token: Explicit API token (overrides other sources)
        service: Keyring service name

    Returns:
        AtlassianCredentials tuple with base_url, email, api_token

    Raises:
        ValueError: If credentials cannot be found
    """
    # 1. Use explicit parameters if provided
    resolved_url = base_url
    resolved_email = email
    resolved_token = api_token

    # 2. Fall back to environment variables
    if not resolved_url:
        resolved_url = os.environ.get(ENV_BASE_URL)
    if not resolved_email:
        resolved_email = os.environ.get(ENV_USER_EMAIL)
    if not resolved_token:
        resolved_token = os.environ.get(ENV_API_TOKEN)

    # 3. Fall back to keyring
    if not resolved_url:
        resolved_url = _get_from_keyring(service, KEYRING_BASE_URL)
    if not resolved_email:
        resolved_email = _get_from_keyring(service, KEYRING_EMAIL)
    if not resolved_token:
        resolved_token = _get_from_keyring(service, KEYRING_TOKEN)

    # 4. Fall back to .env file
    if not all([resolved_url, resolved_email, resolved_token]):
        env_vars = _load_dotenv()
        if not resolved_url:
            resolved_url = env_vars.get(ENV_BASE_URL)
        if not resolved_email:
            resolved_email = env_vars.get(ENV_USER_EMAIL)
        if not resolved_token:
            resolved_token = env_vars.get(ENV_API_TOKEN)

    # Validate that we have all required credentials
    missing = []
    if not resolved_url:
        missing.append("base_url")
    if not resolved_email:
        missing.append("email")
    if not resolved_token:
        missing.append("api_token")

    if missing:
        raise ValueError(
            f"Missing Atlassian credentials: {', '.join(missing)}. "
            f"Set environment variables ({ENV_BASE_URL}, {ENV_USER_EMAIL}, {ENV_API_TOKEN}), "
            f"use the keyring, or provide credentials explicitly."
        )

    # Type narrowing: after validation, all values are guaranteed to be non-None
    assert resolved_url is not None
    assert resolved_email is not None
    assert resolved_token is not None

    return AtlassianCredentials(
        base_url=resolved_url.rstrip("/"),
        email=resolved_email,
        api_token=resolved_token,
    )


def save_credentials(
    base_url: str,
    email: str,
    api_token: str,
    service: str = DEFAULT_SERVICE,
) -> None:
    """Save credentials to the system keyring.

    Args:
        base_url: Atlassian instance URL
        email: User email
        api_token: API token
        service: Keyring service name
    """
    keyring.set_password(service, KEYRING_BASE_URL, base_url)
    keyring.set_password(service, KEYRING_EMAIL, email)
    keyring.set_password(service, KEYRING_TOKEN, api_token)
    logger.info("Credentials saved to keyring (service: %s)", service)


def delete_credentials(service: str = DEFAULT_SERVICE) -> None:
    """Delete credentials from the system keyring.

    Args:
        service: Keyring service name
    """
    for account in [KEYRING_BASE_URL, KEYRING_EMAIL, KEYRING_TOKEN]:
        try:
            keyring.delete_password(service, account)
        except keyring.errors.PasswordDeleteError:
            pass  # Already deleted or doesn't exist
    logger.info("Credentials deleted from keyring (service: %s)", service)


def _get_from_keyring(service: str, account: str) -> str | None:
    """Get a value from the system keyring.

    Args:
        service: Keyring service name
        account: Account/key name

    Returns:
        Value from keyring or None if not found
    """
    try:
        return keyring.get_password(service, account)
    except keyring.errors.KeyringError as e:
        logger.debug("Keyring error for %s/%s: %s", service, account, e)
        return None


def _load_dotenv() -> dict[str, str]:
    """Load variables from .env file.

    Searches current directory and parent directories for .env file.

    Returns:
        Dictionary of environment variables from .env file
    """
    env_vars: dict[str, str] = {}

    # Search for .env file starting from current directory
    current = Path.cwd()
    for directory in [current, *current.parents]:
        env_file = directory / ".env"
        if env_file.exists():
            logger.debug("Loading .env from %s", env_file)
            try:
                with open(env_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if not line or line.startswith("#"):
                            continue
                        # Parse KEY=value
                        if "=" in line:
                            key, _, value = line.partition("=")
                            key = key.strip()
                            value = value.strip()
                            # Remove quotes if present
                            if value and value[0] in ('"', "'") and value[-1] == value[0]:
                                value = value[1:-1]
                            env_vars[key] = value
            except OSError as e:
                logger.debug("Error reading .env file: %s", e)
            break  # Only load from first .env found

    return env_vars
