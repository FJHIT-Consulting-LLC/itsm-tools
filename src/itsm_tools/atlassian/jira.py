"""Jira adapter implementing the IssueTracker interface.

This module provides a Jira implementation of the IssueTracker interface,
enabling provider-agnostic issue tracking operations.

Example:
    from itsm_tools.atlassian import JiraAdapter

    # Using context manager
    with JiraAdapter(project="ITI") as jira:
        issue = jira.get_issue("ITI-220")
        jira.transition(issue, "In Progress")

    # Or via registry
    from itsm_tools import get_issue_tracker
    jira = get_issue_tracker("atlassian_jira", {"project": "ITI"})
"""

import logging
from datetime import datetime
from typing import Any

from itsm_tools.atlassian.base import AtlassianClient
from itsm_tools.core.exceptions import NotFoundError, ProviderError, ValidationError
from itsm_tools.core.interfaces import IssueTracker
from itsm_tools.core.models import Issue, Result, ResultStatus
from itsm_tools.core.registry import register_adapter

logger = logging.getLogger(__name__)

# Jira REST API v3 paths
JIRA_API_V3 = "/rest/api/3"
JIRA_API_V2 = "/rest/api/2"


@register_adapter("atlassian_jira", IssueTracker)  # type: ignore[type-abstract]
class JiraAdapter(AtlassianClient, IssueTracker):  # type: ignore[misc]
    """Jira implementation of the IssueTracker interface.

    Provides issue tracking operations using the Jira REST API v3.

    Attributes:
        project: Default project key for creating issues
        provider_name: Provider identifier for logging and errors
    """

    provider_name = "atlassian_jira"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        project: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Jira adapter.

        Args:
            config: Configuration dictionary (for registry compatibility)
            project: Default project key for creating issues
            **kwargs: Additional arguments passed to AtlassianClient
        """
        # Extract config values if provided via registry
        if config:
            project = config.get("project", project)
            kwargs.update({k: v for k, v in config.items() if k != "project"})

        super().__init__(**kwargs)
        self.project = project
        self._connected = False

    def connect(self) -> None:
        """Establish connection to Jira (validates credentials)."""
        if not self._connected:
            self.test_connection()
            self._connected = True
            logger.info("Connected to Jira at %s", self.base_url)

    def disconnect(self) -> None:
        """Close connection to Jira."""
        self.close()
        self._connected = False
        logger.info("Disconnected from Jira")

    def get_issue(self, issue_key: str) -> Issue | None:
        """Get an issue by its key.

        Args:
            issue_key: Jira issue key (e.g., 'ITI-220')

        Returns:
            Issue object or None if not found
        """
        try:
            data = self._get(
                f"{JIRA_API_V3}/issue/{issue_key}",
                params={"expand": "renderedFields"},
            )
            return self._parse_issue(data)
        except NotFoundError:
            logger.debug("Issue %s not found", issue_key)
            return None

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
        """Create a new Jira issue.

        Args:
            summary: Issue title
            description: Issue description (supports markdown)
            issue_type: Issue type (Task, Story, Bug, Epic, Sub-task)
            project: Project key (uses default if not specified)
            labels: List of labels to apply
            parent_key: Parent issue key for subtasks
            **kwargs: Additional Jira fields (priority, assignee, etc.)

        Returns:
            Created Issue object

        Raises:
            ValidationError: If required fields are missing
            ProviderError: If creation fails
        """
        project = project or self.project
        if not project:
            raise ValidationError(
                "Project key is required. Set default project or provide explicitly.",
                field="project",
                provider=self.provider_name,
            )

        # Build issue fields
        fields: dict[str, Any] = {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        # Add description in Atlassian Document Format (ADF)
        if description:
            fields["description"] = self._to_adf(description)

        # Add labels
        if labels:
            fields["labels"] = labels

        # Add parent for subtasks
        if parent_key:
            fields["parent"] = {"key": parent_key}

        # Add additional fields
        for key, value in kwargs.items():
            if key == "priority":
                fields["priority"] = {"name": value}
            elif key == "assignee":
                fields["assignee"] = (
                    {"accountId": value} if "@" not in value else {"emailAddress": value}
                )
            elif key == "components":
                fields["components"] = [{"name": c} for c in value]
            else:
                fields[key] = value

        logger.debug("Creating issue in %s: %s", project, summary)

        data = self._post(f"{JIRA_API_V3}/issue", json={"fields": fields})
        issue_key = data.get("key", "")

        logger.info("Created issue %s: %s", issue_key, summary)

        # Fetch the full issue to return complete data
        return self.get_issue(issue_key) or Issue(
            key=issue_key,
            summary=summary,
            issue_type=issue_type,
            status="To Do",
            labels=labels or [],
            provider=self.provider_name,
        )

    def search(
        self,
        query: str,
        max_results: int = 50,
        fields: list[str] | None = None,
    ) -> list[Issue]:
        """Search for issues using JQL.

        Args:
            query: JQL query string
            max_results: Maximum number of results (default 50, max 100)
            fields: Specific fields to return

        Returns:
            List of matching Issue objects

        Example:
            # Find open bugs in ITI project
            issues = jira.search("project = ITI AND type = Bug AND status != Done")

            # Find issues assigned to me
            issues = jira.search("assignee = currentUser() ORDER BY updated DESC")
        """
        params: dict[str, Any] = {
            "jql": query,
            "maxResults": min(max_results, 100),
            "expand": "renderedFields",
        }

        if fields:
            params["fields"] = ",".join(fields)

        logger.debug("Searching Jira: %s", query)

        data = self._get(f"{JIRA_API_V3}/search", params=params)

        issues = []
        for issue_data in data.get("issues", []):
            issues.append(self._parse_issue(issue_data))

        logger.debug("Found %d issues", len(issues))
        return issues

    def transition(self, issue: Issue | str, status: str) -> Result:
        """Transition an issue to a new status.

        Args:
            issue: Issue object or issue key
            status: Target status name (e.g., 'In Progress', 'Done')

        Returns:
            Result indicating success or failure
        """
        issue_key = issue.key if isinstance(issue, Issue) else issue

        # Get available transitions
        transitions_data = self._get(f"{JIRA_API_V3}/issue/{issue_key}/transitions")
        transitions = transitions_data.get("transitions", [])

        # Find matching transition
        target_transition = None
        for t in transitions:
            if t.get("name", "").lower() == status.lower():
                target_transition = t
                break
            if t.get("to", {}).get("name", "").lower() == status.lower():
                target_transition = t
                break

        if not target_transition:
            available = [t.get("name") for t in transitions]
            return Result(
                status=ResultStatus.FAILED,
                message=f"Transition to '{status}' not available. Available: {available}",
                resource_id=issue_key,
                details={"available_transitions": available},
            )

        # Execute transition
        self._post(
            f"{JIRA_API_V3}/issue/{issue_key}/transitions",
            json={"transition": {"id": target_transition["id"]}},
        )

        logger.info("Transitioned %s to %s", issue_key, status)

        return Result(
            status=ResultStatus.SUCCESS,
            message=f"Transitioned to {status}",
            resource_id=issue_key,
            resource_url=f"{self.base_url}/browse/{issue_key}",
        )

    def comment(self, issue: Issue | str, body: str) -> Result:
        """Add a comment to an issue.

        Args:
            issue: Issue object or issue key
            body: Comment body (supports markdown)

        Returns:
            Result indicating success or failure
        """
        issue_key = issue.key if isinstance(issue, Issue) else issue

        self._post(
            f"{JIRA_API_V3}/issue/{issue_key}/comment",
            json={"body": self._to_adf(body)},
        )

        logger.info("Added comment to %s", issue_key)

        return Result(
            status=ResultStatus.SUCCESS,
            message="Comment added",
            resource_id=issue_key,
            resource_url=f"{self.base_url}/browse/{issue_key}",
        )

    def link_issues(
        self,
        source: Issue | str,
        target: Issue | str,
        link_type: str = "Relates",
    ) -> Result:
        """Link two issues together.

        Args:
            source: Source issue (outward)
            target: Target issue (inward)
            link_type: Type of link (e.g., 'Relates', 'Blocks', 'Clones')

        Returns:
            Result indicating success or failure
        """
        source_key = source.key if isinstance(source, Issue) else source
        target_key = target.key if isinstance(target, Issue) else target

        self._post(
            f"{JIRA_API_V3}/issueLink",
            json={
                "type": {"name": link_type},
                "outwardIssue": {"key": source_key},
                "inwardIssue": {"key": target_key},
            },
        )

        logger.info("Linked %s -> %s (%s)", source_key, target_key, link_type)

        return Result(
            status=ResultStatus.SUCCESS,
            message=f"Linked {source_key} {link_type.lower()} {target_key}",
            resource_id=source_key,
        )

    def update_issue(
        self,
        issue: Issue | str,
        summary: str | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
        **kwargs: Any,
    ) -> Issue:
        """Update an existing issue.

        Args:
            issue: Issue object or issue key
            summary: New summary (optional)
            description: New description (optional)
            labels: New labels (optional, replaces existing)
            **kwargs: Additional fields to update

        Returns:
            Updated Issue object
        """
        issue_key = issue.key if isinstance(issue, Issue) else issue

        fields: dict[str, Any] = {}

        if summary:
            fields["summary"] = summary
        if description:
            fields["description"] = self._to_adf(description)
        if labels is not None:
            fields["labels"] = labels

        for key, value in kwargs.items():
            if key == "priority":
                fields["priority"] = {"name": value}
            elif key == "assignee":
                fields["assignee"] = {"accountId": value}
            else:
                fields[key] = value

        if fields:
            self._put(f"{JIRA_API_V3}/issue/{issue_key}", json={"fields": fields})
            logger.info("Updated issue %s", issue_key)

        updated_issue = self.get_issue(issue_key)
        if not updated_issue:
            raise ProviderError(
                f"Failed to retrieve updated issue {issue_key}",
                provider=self.provider_name,
            )
        return updated_issue

    def add_labels(self, issue: Issue | str, labels: list[str]) -> Result:
        """Add labels to an issue without removing existing ones.

        Args:
            issue: Issue object or issue key
            labels: Labels to add

        Returns:
            Result indicating success or failure
        """
        issue_key = issue.key if isinstance(issue, Issue) else issue

        self._put(
            f"{JIRA_API_V3}/issue/{issue_key}",
            json={"update": {"labels": [{"add": label} for label in labels]}},
        )

        logger.info("Added labels %s to %s", labels, issue_key)

        return Result(
            status=ResultStatus.SUCCESS,
            message=f"Added labels: {', '.join(labels)}",
            resource_id=issue_key,
        )

    def get_project(self, project_key: str) -> dict[str, Any]:
        """Get project details.

        Args:
            project_key: Jira project key

        Returns:
            Project details dictionary
        """
        return self._get(f"{JIRA_API_V3}/project/{project_key}")

    def _parse_issue(self, data: dict[str, Any]) -> Issue:
        """Parse Jira API response into Issue model.

        Args:
            data: Raw Jira issue response

        Returns:
            Issue model instance
        """
        fields = data.get("fields", {})

        # Parse timestamps
        created_at = None
        updated_at = None
        if fields.get("created"):
            created_at = datetime.fromisoformat(fields["created"].replace("Z", "+00:00"))
        if fields.get("updated"):
            updated_at = datetime.fromisoformat(fields["updated"].replace("Z", "+00:00"))

        # Parse assignee/reporter
        assignee = None
        reporter = None
        if fields.get("assignee"):
            assignee = fields["assignee"].get("emailAddress") or fields["assignee"].get(
                "displayName"
            )
        if fields.get("reporter"):
            reporter = fields["reporter"].get("emailAddress") or fields["reporter"].get(
                "displayName"
            )

        # Parse description from ADF
        description = None
        if fields.get("description"):
            description = self._from_adf(fields["description"])

        # Parse parent key
        parent_key = None
        if fields.get("parent"):
            parent_key = fields["parent"].get("key")

        return Issue(
            key=data.get("key", ""),
            summary=fields.get("summary", ""),
            description=description,
            issue_type=fields.get("issuetype", {}).get("name", ""),
            status=fields.get("status", {}).get("name", ""),
            assignee=assignee,
            reporter=reporter,
            labels=fields.get("labels", []),
            priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
            created_at=created_at,
            updated_at=updated_at,
            url=f"{self.base_url}/browse/{data.get('key', '')}",
            parent_key=parent_key,
            provider=self.provider_name,
            raw=data,
        )

    def _to_adf(self, text: str) -> dict[str, Any]:
        """Convert plain text/markdown to Atlassian Document Format.

        Args:
            text: Plain text or simple markdown

        Returns:
            ADF document structure
        """
        # Simple conversion - create paragraph nodes for each line
        paragraphs = []
        for line in text.split("\n"):
            if line.strip():
                paragraphs.append(
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": line}],
                    }
                )
            else:
                # Empty paragraph for blank lines
                paragraphs.append({"type": "paragraph", "content": []})

        return {
            "type": "doc",
            "version": 1,
            "content": paragraphs,
        }

    def _from_adf(self, adf: dict[str, Any]) -> str:
        """Convert Atlassian Document Format to plain text.

        Args:
            adf: ADF document structure

        Returns:
            Plain text representation
        """
        if not adf or not isinstance(adf, dict):
            return ""

        lines = []
        for content in adf.get("content", []):
            line = self._extract_text_from_adf_node(content)
            lines.append(line)

        return "\n".join(lines)

    def _extract_text_from_adf_node(self, node: dict[str, Any]) -> str:
        """Recursively extract text from an ADF node.

        Args:
            node: ADF node

        Returns:
            Extracted text
        """
        if not node:
            return ""

        node_type = node.get("type", "")

        if node_type == "text":
            return str(node.get("text", ""))

        if node_type in ("paragraph", "heading", "listItem", "blockquote"):
            texts = []
            for child in node.get("content", []):
                texts.append(self._extract_text_from_adf_node(child))
            return "".join(texts)

        if node_type in ("bulletList", "orderedList"):
            items = []
            for child in node.get("content", []):
                item_text = self._extract_text_from_adf_node(child)
                items.append(f"• {item_text}" if node_type == "bulletList" else item_text)
            return "\n".join(items)

        if node_type == "codeBlock":
            texts = []
            for child in node.get("content", []):
                texts.append(self._extract_text_from_adf_node(child))
            return "```\n" + "".join(texts) + "\n```"

        # Default: recurse into content
        texts = []
        for child in node.get("content", []):
            texts.append(self._extract_text_from_adf_node(child))
        return "".join(texts)
