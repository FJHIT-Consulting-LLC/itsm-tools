"""
itsm-tools: Provider-agnostic ITSM integration library.

This package provides abstract interfaces for common ITSM operations
(issue tracking, wiki/documentation, incident management) with adapters
for multiple providers (Atlassian, ServiceNow, PagerDuty, etc.).

Example Usage:
    from itsm_tools import get_issue_tracker, get_incident_manager

    # Get configured adapters
    tracker = get_issue_tracker()
    incidents = get_incident_manager()

    # Use provider-agnostic interface
    issue = tracker.create_issue(
        summary="New feature request",
        description="Details here...",
        issue_type="Story"
    )

    incident = incidents.create_incident(
        summary="System alert",
        severity=Severity.HIGH,
        service="Production API"
    )
"""

from itsm_tools.core.exceptions import (
    AuthenticationError,
    ITSMError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from itsm_tools.core.interfaces import (
    IncidentManager,
    IssueTracker,
    WikiProvider,
)
from itsm_tools.core.models import (
    Incident,
    Issue,
    Page,
    Result,
    ResultStatus,
    Severity,
)
from itsm_tools.core.registry import (
    get_incident_manager,
    get_issue_tracker,
    get_wiki_provider,
    register_adapter,
)

__version__ = "0.1.0"

__all__ = [
    # Models
    "Issue",
    "Page",
    "Incident",
    "Severity",
    "Result",
    "ResultStatus",
    # Interfaces
    "IssueTracker",
    "WikiProvider",
    "IncidentManager",
    # Registry
    "get_issue_tracker",
    "get_wiki_provider",
    "get_incident_manager",
    "register_adapter",
    # Exceptions
    "ITSMError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "ValidationError",
]
