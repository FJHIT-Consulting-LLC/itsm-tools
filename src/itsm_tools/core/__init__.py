"""Core interfaces and models for itsm-tools."""

from itsm_tools.core.models import (
    Issue,
    Page,
    Incident,
    Severity,
    Result,
    ResultStatus,
)
from itsm_tools.core.interfaces import (
    IssueTracker,
    WikiProvider,
    IncidentManager,
)
from itsm_tools.core.registry import (
    get_issue_tracker,
    get_wiki_provider,
    get_incident_manager,
    register_adapter,
)
from itsm_tools.core.exceptions import (
    ITSMError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    ValidationError,
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
