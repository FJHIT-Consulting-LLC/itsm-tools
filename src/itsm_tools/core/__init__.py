"""Core interfaces and models for itsm-tools."""

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

__all__ = [
    "Issue",
    "Page",
    "Incident",
    "Severity",
    "Result",
    "ResultStatus",
    "IssueTracker",
    "WikiProvider",
    "IncidentManager",
    "get_issue_tracker",
    "get_wiki_provider",
    "get_incident_manager",
    "register_adapter",
    "ITSMError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "ValidationError",
]
