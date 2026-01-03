"""Jira Service Management adapter implementing the IncidentManager interface.

This module provides a JSM implementation of the IncidentManager interface,
enabling provider-agnostic incident management operations.

Example:
    from itsm_tools.atlassian import JSMAdapter

    # Using context manager
    with JSMAdapter(service_desk="SD") as jsm:
        incident = jsm.get_incident("SD-100")
        jsm.resolve_incident(incident, "Root cause identified and fixed")

    # Or via registry
    from itsm_tools import get_incident_manager
    jsm = get_incident_manager("atlassian_jsm", {"service_desk": "SD"})
"""

import logging
from datetime import datetime
from typing import Any

from itsm_tools.atlassian.base import AtlassianClient
from itsm_tools.core.exceptions import NotFoundError, ProviderError, ValidationError
from itsm_tools.core.interfaces import IncidentManager
from itsm_tools.core.models import Incident, Issue, Result, ResultStatus, Severity, SLAStatus
from itsm_tools.core.registry import register_adapter

logger = logging.getLogger(__name__)

# API paths
JIRA_API_V3 = "/rest/api/3"
JSM_API = "/rest/servicedeskapi"

# Severity to Priority mapping (JSM uses priorities)
SEVERITY_PRIORITY_MAP = {
    Severity.CRITICAL: "Highest",
    Severity.HIGH: "High",
    Severity.MEDIUM: "Medium",
    Severity.LOW: "Low",
    Severity.INFO: "Lowest",
}

PRIORITY_SEVERITY_MAP = {
    "Highest": Severity.CRITICAL,
    "High": Severity.HIGH,
    "Medium": Severity.MEDIUM,
    "Low": Severity.LOW,
    "Lowest": Severity.INFO,
}


@register_adapter("atlassian_jsm", IncidentManager)  # type: ignore[type-abstract]
class JSMAdapter(AtlassianClient, IncidentManager):  # type: ignore[misc]
    """Jira Service Management implementation of the IncidentManager interface.

    Provides incident management operations using the JSM REST API.

    Attributes:
        service_desk: Default service desk key/ID for creating incidents
        request_type: Default request type for incidents
        provider_name: Provider identifier for logging and errors
    """

    provider_name = "atlassian_jsm"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        service_desk: str | None = None,
        request_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the JSM adapter.

        Args:
            config: Configuration dictionary (for registry compatibility)
            service_desk: Default service desk key/ID for creating incidents
            request_type: Default request type for incidents (e.g., "Incident")
            **kwargs: Additional arguments passed to AtlassianClient
        """
        # Extract config values if provided via registry
        if config:
            service_desk = config.get("service_desk", service_desk)
            request_type = config.get("request_type", request_type)
            kwargs.update(
                {k: v for k, v in config.items() if k not in ("service_desk", "request_type")}
            )

        super().__init__(**kwargs)
        self.service_desk = service_desk
        self.request_type = request_type or "Incident"
        self._connected = False
        self._service_desk_id: str | None = None
        self._request_type_id: int | None = None

    def connect(self) -> None:
        """Establish connection to JSM (validates credentials)."""
        if not self._connected:
            self.test_connection()
            self._connected = True
            logger.info("Connected to Jira Service Management at %s", self.base_url)

    def disconnect(self) -> None:
        """Close connection to JSM."""
        self.close()
        self._connected = False
        logger.info("Disconnected from Jira Service Management")

    def get_incident(self, incident_key: str) -> Incident | None:
        """Get an incident by its key.

        Args:
            incident_key: JSM request/incident key (e.g., 'SD-100')

        Returns:
            Incident object or None if not found
        """
        try:
            # Use Jira API to get issue details
            data = self._get(
                f"{JIRA_API_V3}/issue/{incident_key}",
                params={"expand": "renderedFields"},
            )
            return self._parse_incident(data)
        except NotFoundError:
            logger.debug("Incident %s not found", incident_key)
            return None

    def create_incident(
        self,
        summary: str,
        description: str | None = None,
        severity: Severity = Severity.MEDIUM,
        service: str | None = None,
        labels: list[str] | None = None,
        **kwargs: Any,
    ) -> Incident:
        """Create a new incident in JSM.

        Args:
            summary: Incident title
            description: Incident description
            severity: Severity level (maps to priority in JSM)
            service: Affected service/component
            labels: List of labels to apply
            **kwargs: Additional fields (reporter_email, request_type, etc.)

        Returns:
            Created Incident object

        Raises:
            ValidationError: If required fields are missing
            ProviderError: If creation fails
        """
        service_desk = kwargs.get("service_desk") or self.service_desk
        if not service_desk:
            raise ValidationError(
                "Service desk is required. Set default service_desk or provide explicitly.",
                field="service_desk",
                provider=self.provider_name,
            )

        # Get service desk ID if we have a key
        service_desk_id = self._get_service_desk_id(service_desk)

        # Get request type ID
        request_type = kwargs.get("request_type") or self.request_type
        request_type_id = self._get_request_type_id(service_desk_id, request_type)

        # Build request payload
        request_field_values: dict[str, Any] = {
            "summary": summary,
        }

        # Add description
        if description:
            request_field_values["description"] = description

        # Add components (service)
        if service:
            request_field_values["components"] = [{"name": service}]

        # Add labels
        if labels:
            request_field_values["labels"] = labels

        # Map severity to priority
        priority = SEVERITY_PRIORITY_MAP.get(severity, "Medium")
        request_field_values["priority"] = {"name": priority}

        payload: dict[str, Any] = {
            "serviceDeskId": service_desk_id,
            "requestTypeId": request_type_id,
            "requestFieldValues": request_field_values,
        }

        # Add reporter if specified
        if kwargs.get("reporter_email"):
            payload["raiseOnBehalfOf"] = kwargs["reporter_email"]

        logger.debug("Creating incident in service desk %s: %s", service_desk, summary)

        data = self._post(f"{JSM_API}/request", json=payload)
        incident_key = data.get("issueKey", "")

        logger.info("Created incident %s: %s", incident_key, summary)

        # Fetch the full incident to return complete data
        return self.get_incident(incident_key) or Incident(
            key=incident_key,
            summary=summary,
            severity=severity,
            status="Open",
            labels=labels or [],
            provider=self.provider_name,
        )

    def search_incidents(
        self,
        query: str | None = None,
        status: str | None = None,
        severity: Severity | None = None,
        limit: int = 50,
    ) -> list[Incident]:
        """Search for incidents using JQL.

        Args:
            query: JQL query string or text search
            status: Filter by status (e.g., 'Open', 'Resolved')
            severity: Filter by severity (maps to priority)
            limit: Maximum number of results (max 100)

        Returns:
            List of matching Incident objects

        Example:
            # Find open critical incidents
            incidents = jsm.search_incidents(severity=Severity.CRITICAL, status="Open")

            # Custom JQL search
            incidents = jsm.search_incidents("project = SD AND reporter = currentUser()")
        """
        # Build JQL query
        jql_parts = []

        # Add service desk project filter if configured
        if self.service_desk:
            jql_parts.append(f'project = "{self.service_desk}"')

        # Check if query is already JQL (contains operators)
        if query:
            jql_operators = ["=", "~", "AND", "OR", "NOT", "ORDER BY"]
            is_jql = any(op in query for op in jql_operators)
            if is_jql:
                jql_parts.append(f"({query})")
            else:
                jql_parts.append(f'text ~ "{query}"')

        # Add status filter
        if status:
            jql_parts.append(f'status = "{status}"')

        # Add severity/priority filter
        if severity:
            priority = SEVERITY_PRIORITY_MAP.get(severity, "Medium")
            jql_parts.append(f'priority = "{priority}"')

        # Default to incident request types
        jql_parts.append('type = "Service Request" OR type = "Incident"')

        jql = " AND ".join(jql_parts) if jql_parts else 'type = "Incident"'

        logger.debug("Searching incidents: %s", jql)

        params: dict[str, Any] = {
            "jql": jql,
            "maxResults": min(limit, 100),
            "expand": "renderedFields",
        }

        data = self._get(f"{JIRA_API_V3}/search", params=params)

        incidents = []
        for issue_data in data.get("issues", []):
            incidents.append(self._parse_incident(issue_data))

        logger.debug("Found %d incidents", len(incidents))
        return incidents

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
        incident_key = incident.key if isinstance(incident, Incident) else incident

        # Add resolution comment
        self.add_comment(incident_key, f"Resolution: {resolution}", internal=True)

        # Get available transitions
        transitions_data = self._get(f"{JIRA_API_V3}/issue/{incident_key}/transitions")
        transitions = transitions_data.get("transitions", [])

        # Find resolve/done transition
        resolve_transition = None
        for t in transitions:
            name = t.get("name", "").lower()
            to_status = t.get("to", {}).get("name", "").lower()
            if any(
                word in name or word in to_status
                for word in ["resolve", "done", "close", "complete"]
            ):
                resolve_transition = t
                break

        if not resolve_transition:
            available = [t.get("name") for t in transitions]
            return Result(
                status=ResultStatus.FAILED,
                message=f"No resolve transition available. Available: {available}",
                resource_id=incident_key,
                details={"available_transitions": available},
            )

        # Execute transition with resolution field if available
        transition_payload: dict[str, Any] = {
            "transition": {"id": resolve_transition["id"]},
        }

        # Try to set resolution field
        if resolve_transition.get("fields", {}).get("resolution"):
            transition_payload["fields"] = {"resolution": {"name": "Done"}}

        self._post(
            f"{JIRA_API_V3}/issue/{incident_key}/transitions",
            json=transition_payload,
        )

        logger.info("Resolved incident %s", incident_key)

        return Result(
            status=ResultStatus.SUCCESS,
            message=f"Incident resolved: {resolution[:50]}...",
            resource_id=incident_key,
            resource_url=f"{self.base_url}/browse/{incident_key}",
        )

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
        incident_key = incident.key if isinstance(incident, Incident) else incident

        # Map severity to priority
        new_priority = SEVERITY_PRIORITY_MAP.get(new_severity, "Medium")

        # Update priority
        self._put(
            f"{JIRA_API_V3}/issue/{incident_key}",
            json={"fields": {"priority": {"name": new_priority}}},
        )

        # Add escalation comment
        comment = f"Incident escalated to {new_severity.value}"
        if reason:
            comment += f"\nReason: {reason}"
        self.add_comment(incident_key, comment, internal=True)

        logger.info("Escalated incident %s to %s", incident_key, new_severity.value)

        return Result(
            status=ResultStatus.SUCCESS,
            message=f"Escalated to {new_severity.value}",
            resource_id=incident_key,
            resource_url=f"{self.base_url}/browse/{incident_key}",
        )

    def link_to_issue(
        self,
        incident: Incident | str,
        issue: Issue | str,
    ) -> Result:
        """Link an incident to a Jira issue.

        Args:
            incident: Incident object or incident key
            issue: Issue object or issue key

        Returns:
            Result indicating success or failure
        """
        incident_key = incident.key if isinstance(incident, Incident) else incident
        issue_key = issue.key if isinstance(issue, Issue) else issue

        self._post(
            f"{JIRA_API_V3}/issueLink",
            json={
                "type": {"name": "Relates"},
                "inwardIssue": {"key": incident_key},
                "outwardIssue": {"key": issue_key},
            },
        )

        logger.info("Linked incident %s to issue %s", incident_key, issue_key)

        return Result(
            status=ResultStatus.SUCCESS,
            message=f"Linked {incident_key} to {issue_key}",
            resource_id=incident_key,
        )

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
        incident_key = incident.key if isinstance(incident, Incident) else incident

        # Use JSM API for internal/public comment distinction
        payload: dict[str, Any] = {
            "body": body,
            "public": not internal,
        }

        try:
            # Try JSM API first for proper internal/public handling
            self._post(
                f"{JSM_API}/request/{incident_key}/comment",
                json=payload,
            )
        except ProviderError:
            # Fall back to regular Jira API if JSM API fails
            self._post(
                f"{JIRA_API_V3}/issue/{incident_key}/comment",
                json={"body": self._to_adf(body)},
            )

        logger.info(
            "Added %s comment to %s",
            "internal" if internal else "public",
            incident_key,
        )

        return Result(
            status=ResultStatus.SUCCESS,
            message=f"{'Internal' if internal else 'Public'} comment added",
            resource_id=incident_key,
            resource_url=f"{self.base_url}/browse/{incident_key}",
        )

    def get_sla_status(self, incident: Incident | str) -> list[SLAStatus]:
        """Get SLA status for an incident.

        Args:
            incident: Incident object or incident key

        Returns:
            List of SLA statuses
        """
        incident_key = incident.key if isinstance(incident, Incident) else incident

        try:
            data = self._get(f"{JSM_API}/request/{incident_key}/sla")
            sla_statuses = []

            for sla in data.get("values", []):
                ongoing = sla.get("ongoingCycle", {})
                completed = (
                    sla.get("completedCycles", [{}])[-1] if sla.get("completedCycles") else {}
                )

                cycle = ongoing or completed

                # Parse target time
                target = None
                if cycle.get("goalDuration", {}).get("millis"):
                    target_ms = cycle["goalDuration"]["millis"]
                    if cycle.get("startTime", {}).get("epochMillis"):
                        start_ms = cycle["startTime"]["epochMillis"]
                        target = datetime.fromtimestamp((start_ms + target_ms) / 1000)

                # Calculate elapsed and remaining
                elapsed = None
                remaining = None
                if cycle.get("elapsedTime", {}).get("millis"):
                    elapsed = cycle["elapsedTime"]["millis"] // 1000
                if cycle.get("remainingTime", {}).get("millis"):
                    remaining = cycle["remainingTime"]["millis"] // 1000

                sla_statuses.append(
                    SLAStatus(
                        name=sla.get("name", "Unknown SLA"),
                        target=target,
                        elapsed=elapsed,
                        remaining=remaining,
                        breached=cycle.get("breached", False),
                        paused=cycle.get("paused", False),
                    )
                )

            return sla_statuses

        except (NotFoundError, ProviderError) as e:
            logger.debug("Could not get SLA for %s: %s", incident_key, e)
            return []

    def _get_service_desk_id(self, service_desk: str) -> str:
        """Get service desk ID from key.

        Args:
            service_desk: Service desk key or ID

        Returns:
            Service desk ID
        """
        # If it's already numeric, use it directly
        if service_desk.isdigit():
            return service_desk

        # Look up by project key
        try:
            data = self._get(f"{JSM_API}/servicedesk")
            for desk in data.get("values", []):
                if desk.get("projectKey") == service_desk:
                    return str(desk.get("id", ""))
        except ProviderError:
            pass

        # Fall back to assuming it's a valid ID
        return service_desk

    def _get_request_type_id(self, service_desk_id: str, request_type: str) -> int:
        """Get request type ID from name.

        Args:
            service_desk_id: Service desk ID
            request_type: Request type name

        Returns:
            Request type ID
        """
        # If it's already numeric, use it directly
        if request_type.isdigit():
            return int(request_type)

        # Look up by name
        try:
            data = self._get(f"{JSM_API}/servicedesk/{service_desk_id}/requesttype")
            for rt in data.get("values", []):
                if rt.get("name", "").lower() == request_type.lower():
                    return int(rt.get("id", 0))
        except ProviderError:
            pass

        # Return first request type as fallback
        try:
            data = self._get(f"{JSM_API}/servicedesk/{service_desk_id}/requesttype")
            if data.get("values"):
                return int(data["values"][0].get("id", 1))
        except ProviderError:
            pass

        return 1  # Default fallback

    def _parse_incident(self, data: dict[str, Any]) -> Incident:
        """Parse Jira API response into Incident model.

        Args:
            data: Raw Jira issue response

        Returns:
            Incident model instance
        """
        fields = data.get("fields", {})

        # Parse timestamps
        created_at = None
        updated_at = None
        resolved_at = None
        if fields.get("created"):
            created_at = datetime.fromisoformat(fields["created"].replace("Z", "+00:00"))
        if fields.get("updated"):
            updated_at = datetime.fromisoformat(fields["updated"].replace("Z", "+00:00"))
        if fields.get("resolutiondate"):
            resolved_at = datetime.fromisoformat(fields["resolutiondate"].replace("Z", "+00:00"))

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

        # Parse severity from priority
        priority_name = fields.get("priority", {}).get("name", "Medium")
        severity = PRIORITY_SEVERITY_MAP.get(priority_name, Severity.MEDIUM)

        # Parse service from components
        service = None
        if fields.get("components"):
            service = fields["components"][0].get("name")

        # Parse linked issues
        linked_issues = []
        for link in fields.get("issuelinks", []):
            if link.get("outwardIssue"):
                linked_issues.append(link["outwardIssue"].get("key", ""))
            if link.get("inwardIssue"):
                linked_issues.append(link["inwardIssue"].get("key", ""))

        # Parse resolution
        resolution = None
        if fields.get("resolution"):
            resolution = fields["resolution"].get("name")

        return Incident(
            key=data.get("key", ""),
            summary=fields.get("summary", ""),
            description=description,
            severity=severity,
            status=fields.get("status", {}).get("name", ""),
            service=service,
            assignee=assignee,
            reporter=reporter,
            labels=fields.get("labels", []),
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            resolution=resolution,
            url=f"{self.base_url}/browse/{data.get('key', '')}",
            linked_issues=linked_issues,
            provider=self.provider_name,
            raw=data,
        )

    def _to_adf(self, text: str) -> dict[str, Any]:
        """Convert plain text to Atlassian Document Format.

        Args:
            text: Plain text

        Returns:
            ADF document structure
        """
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

        texts = []
        for child in node.get("content", []):
            texts.append(self._extract_text_from_adf_node(child))
        return "".join(texts)
