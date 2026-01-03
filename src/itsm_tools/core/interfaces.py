"""Abstract interfaces for ITSM operations.

These interfaces define the contract that all provider adapters must implement.
This enables provider-agnostic code that can work with Atlassian, ServiceNow,
PagerDuty, or any other ITSM platform.
"""

from abc import ABC, abstractmethod
from typing import Any

from itsm_tools.core.models import (
    Issue,
    Page,
    Incident,
    Result,
    Severity,
    SLAStatus,
)


class IssueTracker(ABC):
    """Abstract interface for issue/ticket tracking systems.

    Implementations: JiraAdapter, GitHubIssuesAdapter, AzureDevOpsAdapter
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the issue tracker."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the issue tracker."""

    def __enter__(self) -> "IssueTracker":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()

    @abstractmethod
    def get_issue(self, issue_key: str) -> Issue | None:
        """Get an issue by its key.

        Args:
            issue_key: Unique issue identifier (e.g., 'ITI-220')

        Returns:
            Issue object or None if not found
        """

    @abstractmethod
    def create_issue(
        self,
        summary: str,
        description: str | None = None,
        issue_type: str = "Task",
        project: str | None = None,
        labels: list[str] | None = None,
        parent_key: str | None = None,
        **kwargs: Any,
    ) -> Issue:
        """Create a new issue.

        Args:
            summary: Issue title
            description: Issue description
            issue_type: Type of issue (Task, Story, Bug, etc.)
            project: Project key (uses default if not specified)
            labels: List of labels to apply
            parent_key: Parent issue key for subtasks
            **kwargs: Provider-specific arguments

        Returns:
            Created Issue object
        """

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 50,
        fields: list[str] | None = None,
    ) -> list[Issue]:
        """Search for issues.

        Args:
            query: Search query (JQL for Jira, search syntax for others)
            max_results: Maximum number of results
            fields: Specific fields to return

        Returns:
            List of matching Issue objects
        """

    @abstractmethod
    def transition(self, issue: Issue | str, status: str) -> Result:
        """Transition an issue to a new status.

        Args:
            issue: Issue object or issue key
            status: Target status name

        Returns:
            Result indicating success or failure
        """

    @abstractmethod
    def comment(self, issue: Issue | str, body: str) -> Result:
        """Add a comment to an issue.

        Args:
            issue: Issue object or issue key
            body: Comment body

        Returns:
            Result indicating success or failure
        """

    @abstractmethod
    def link_issues(
        self,
        source: Issue | str,
        target: Issue | str,
        link_type: str = "relates to",
    ) -> Result:
        """Link two issues together.

        Args:
            source: Source issue
            target: Target issue
            link_type: Type of link

        Returns:
            Result indicating success or failure
        """


class WikiProvider(ABC):
    """Abstract interface for wiki/documentation systems.

    Implementations: ConfluenceAdapter, NotionAdapter, SharePointAdapter
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the wiki provider."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the wiki provider."""

    def __enter__(self) -> "WikiProvider":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()

    @abstractmethod
    def get_page(self, page_id: str) -> Page | None:
        """Get a page by its ID.

        Args:
            page_id: Unique page identifier

        Returns:
            Page object or None if not found
        """

    @abstractmethod
    def get_page_by_path(self, space: str, path: str) -> Page | None:
        """Get a page by its path within a space.

        Args:
            space: Space/container identifier
            path: Page path or title

        Returns:
            Page object or None if not found
        """

    @abstractmethod
    def create_page(
        self,
        title: str,
        content: str,
        space: str | None = None,
        parent_id: str | None = None,
        **kwargs: Any,
    ) -> Page:
        """Create a new page.

        Args:
            title: Page title
            content: Page content (HTML or markdown)
            space: Space identifier (uses default if not specified)
            parent_id: Parent page ID
            **kwargs: Provider-specific arguments

        Returns:
            Created Page object
        """

    @abstractmethod
    def update_page(
        self,
        page_id: str,
        content: str,
        title: str | None = None,
    ) -> Page:
        """Update an existing page.

        Args:
            page_id: Page identifier
            content: New page content
            title: New title (optional)

        Returns:
            Updated Page object
        """

    @abstractmethod
    def append_to_page(self, page_id: str, content: str) -> Page:
        """Append content to an existing page.

        Args:
            page_id: Page identifier
            content: Content to append

        Returns:
            Updated Page object
        """

    @abstractmethod
    def search(
        self,
        query: str,
        space: str | None = None,
        limit: int = 25,
    ) -> list[Page]:
        """Search for pages.

        Args:
            query: Search query
            space: Limit search to specific space
            limit: Maximum number of results

        Returns:
            List of matching Page objects
        """


class IncidentManager(ABC):
    """Abstract interface for incident management systems.

    Implementations: JSMAdapter, ServiceNowAdapter, PagerDutyAdapter
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the incident manager."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the incident manager."""

    def __enter__(self) -> "IncidentManager":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()

    @abstractmethod
    def get_incident(self, incident_key: str) -> Incident | None:
        """Get an incident by its key.

        Args:
            incident_key: Unique incident identifier

        Returns:
            Incident object or None if not found
        """

    @abstractmethod
    def create_incident(
        self,
        summary: str,
        description: str | None = None,
        severity: Severity = Severity.MEDIUM,
        service: str | None = None,
        labels: list[str] | None = None,
        **kwargs: Any,
    ) -> Incident:
        """Create a new incident.

        Args:
            summary: Incident title
            description: Incident description
            severity: Severity level
            service: Affected service/component
            labels: List of labels to apply
            **kwargs: Provider-specific arguments

        Returns:
            Created Incident object
        """

    @abstractmethod
    def search_incidents(
        self,
        query: str | None = None,
        status: str | None = None,
        severity: Severity | None = None,
        limit: int = 50,
    ) -> list[Incident]:
        """Search for incidents.

        Args:
            query: Search query
            status: Filter by status
            severity: Filter by severity
            limit: Maximum number of results

        Returns:
            List of matching Incident objects
        """

    @abstractmethod
    def resolve_incident(
        self,
        incident: Incident | str,
        resolution: str,
    ) -> Result:
        """Resolve an incident.

        Args:
            incident: Incident object or incident key
            resolution: Resolution notes

        Returns:
            Result indicating success or failure
        """

    @abstractmethod
    def escalate_incident(
        self,
        incident: Incident | str,
        new_severity: Severity,
        reason: str | None = None,
    ) -> Result:
        """Escalate an incident to a higher severity.

        Args:
            incident: Incident object or incident key
            new_severity: New severity level
            reason: Reason for escalation

        Returns:
            Result indicating success or failure
        """

    @abstractmethod
    def link_to_issue(
        self,
        incident: Incident | str,
        issue: Issue | str,
    ) -> Result:
        """Link an incident to an issue.

        Args:
            incident: Incident object or incident key
            issue: Issue object or issue key

        Returns:
            Result indicating success or failure
        """

    @abstractmethod
    def add_comment(
        self,
        incident: Incident | str,
        body: str,
        internal: bool = False,
    ) -> Result:
        """Add a comment to an incident.

        Args:
            incident: Incident object or incident key
            body: Comment body
            internal: Whether comment is internal (not visible to customers)

        Returns:
            Result indicating success or failure
        """

    @abstractmethod
    def get_sla_status(self, incident: Incident | str) -> list[SLAStatus]:
        """Get SLA status for an incident.

        Args:
            incident: Incident object or incident key

        Returns:
            List of SLA statuses
        """