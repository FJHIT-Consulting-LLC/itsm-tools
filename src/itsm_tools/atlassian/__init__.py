"""Atlassian adapters for Jira, Confluence, and JSM.

This module provides adapters for:
- JiraAdapter: Issue tracking via Jira REST API
- ConfluenceAdapter: Wiki/documentation via Confluence REST API
- JSMAdapter: Incident management via Jira Service Management API

Base classes:
- AtlassianClient: Base HTTP client with auth and retry logic
- AtlassianCredentials: Credential management

Example:
    from itsm_tools.atlassian import JiraAdapter, ConfluenceAdapter, JSMAdapter

    with JiraAdapter(config) as jira:
        issue = jira.get_issue("ITI-220")
"""

from itsm_tools.atlassian.base import AtlassianClient
from itsm_tools.atlassian.credentials import (
    AtlassianCredentials,
    delete_credentials,
    get_credentials,
    save_credentials,
)

# Adapters will be implemented in ITI-222, ITI-223, ITI-224
# For now, export placeholder to allow package import

__all__ = [
    # Base classes
    "AtlassianClient",
    "AtlassianCredentials",
    "get_credentials",
    "save_credentials",
    "delete_credentials",
    # Adapters (placeholders)
    "JiraAdapter",
    "ConfluenceAdapter",
    "JSMAdapter",
]


# Placeholder classes - will be implemented in subsequent stories
def JiraAdapter(*args, **kwargs):  # type: ignore  # noqa: N802
    """Placeholder for JiraAdapter - implement in ITI-222."""
    raise NotImplementedError("JiraAdapter will be implemented in ITI-222")


def ConfluenceAdapter(*args, **kwargs):  # type: ignore  # noqa: N802
    """Placeholder for ConfluenceAdapter - implement in ITI-223."""
    raise NotImplementedError("ConfluenceAdapter will be implemented in ITI-223")


def JSMAdapter(*args, **kwargs):  # type: ignore  # noqa: N802
    """Placeholder for JSMAdapter - implement in ITI-224."""
    raise NotImplementedError("JSMAdapter will be implemented in ITI-224")
