"""Tests for JSMAdapter."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import responses

from itsm_tools.atlassian.jsm import JSMAdapter
from itsm_tools.core.exceptions import NotFoundError, ValidationError
from itsm_tools.core.models import Incident, Issue, ResultStatus, Severity


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


@pytest.fixture
def jsm_adapter(mock_credentials: MagicMock) -> JSMAdapter:
    """Create a JSMAdapter instance for testing."""
    return JSMAdapter(service_desk="SD", request_type="Incident")


@pytest.fixture
def sample_incident() -> Incident:
    """Sample Incident model for testing."""
    return Incident(
        key="SD-100",
        summary="Test incident",
        severity=Severity.HIGH,
        status="Open",
        labels=["test"],
        provider="atlassian_jsm",
    )


@pytest.fixture
def sample_jira_incident() -> dict:
    """Sample Jira API incident response."""
    return {
        "key": "SD-100",
        "fields": {
            "summary": "Test incident",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Test description"}],
                    }
                ],
            },
            "issuetype": {"name": "Incident"},
            "status": {"name": "Open"},
            "assignee": {
                "emailAddress": "assignee@example.com",
                "displayName": "Test User",
            },
            "reporter": {
                "emailAddress": "reporter@example.com",
                "displayName": "Reporter User",
            },
            "labels": ["test", "automation"],
            "priority": {"name": "High"},
            "created": "2024-01-15T10:30:00.000Z",
            "updated": "2024-01-16T14:45:00.000Z",
            "components": [{"name": "API Service"}],
            "issuelinks": [
                {"outwardIssue": {"key": "ITI-220"}},
                {"inwardIssue": {"key": "ITI-221"}},
            ],
        },
    }


@pytest.fixture
def sample_service_desks() -> dict:
    """Sample service desks response."""
    return {
        "values": [
            {"id": "1", "projectKey": "SD", "projectName": "Service Desk"},
            {"id": "2", "projectKey": "IT", "projectName": "IT Help Desk"},
        ]
    }


@pytest.fixture
def sample_request_types() -> dict:
    """Sample request types response."""
    return {
        "values": [
            {"id": 10, "name": "Incident"},
            {"id": 11, "name": "Service Request"},
            {"id": 12, "name": "Change"},
        ]
    }


class TestJSMAdapterInit:
    """Tests for JSMAdapter initialization."""

    def test_init_with_service_desk(self, mock_credentials: MagicMock) -> None:
        """Test initialization with service desk."""
        adapter = JSMAdapter(service_desk="SD")
        assert adapter.service_desk == "SD"
        assert adapter.provider_name == "atlassian_jsm"

    def test_init_with_config(self, mock_credentials: MagicMock) -> None:
        """Test initialization with config dict (registry pattern)."""
        adapter = JSMAdapter(config={"service_desk": "IT", "request_type": "Change"})
        assert adapter.service_desk == "IT"
        assert adapter.request_type == "Change"

    def test_init_default_request_type(self, mock_credentials: MagicMock) -> None:
        """Test default request type is Incident."""
        adapter = JSMAdapter()
        assert adapter.request_type == "Incident"


class TestJSMAdapterConnection:
    """Tests for connect/disconnect methods."""

    @responses.activate
    def test_connect(self, jsm_adapter: JSMAdapter) -> None:
        """Test connection establishment."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            json={"baseUrl": "https://test.atlassian.net"},
            status=200,
        )

        jsm_adapter.connect()
        assert jsm_adapter._connected is True

    def test_disconnect(self, jsm_adapter: JSMAdapter) -> None:
        """Test disconnection."""
        jsm_adapter._connected = True
        jsm_adapter.disconnect()
        assert jsm_adapter._connected is False


class TestJSMAdapterGetIncident:
    """Tests for get_incident method."""

    @responses.activate
    def test_get_incident_found(self, jsm_adapter: JSMAdapter, sample_jira_incident: dict) -> None:
        """Test getting an existing incident."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/SD-100",
            json=sample_jira_incident,
            status=200,
        )

        incident = jsm_adapter.get_incident("SD-100")

        assert incident is not None
        assert incident.key == "SD-100"
        assert incident.summary == "Test incident"
        assert incident.severity == Severity.HIGH
        assert incident.status == "Open"
        assert incident.assignee == "assignee@example.com"
        assert incident.reporter == "reporter@example.com"
        assert incident.service == "API Service"
        assert "ITI-220" in incident.linked_issues
        assert incident.provider == "atlassian_jsm"

    @responses.activate
    def test_get_incident_not_found(self, jsm_adapter: JSMAdapter) -> None:
        """Test getting a non-existent incident."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/SD-999",
            json={"errorMessages": ["Issue does not exist"]},
            status=404,
        )

        incident = jsm_adapter.get_incident("SD-999")
        assert incident is None


class TestJSMAdapterCreateIncident:
    """Tests for create_incident method."""

    @responses.activate
    def test_create_incident_success(
        self,
        jsm_adapter: JSMAdapter,
        sample_jira_incident: dict,
        sample_service_desks: dict,
        sample_request_types: dict,
    ) -> None:
        """Test successful incident creation."""
        # Mock get service desks
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/servicedeskapi/servicedesk",
            json=sample_service_desks,
            status=200,
        )
        # Mock get request types
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/servicedeskapi/servicedesk/1/requesttype",
            json=sample_request_types,
            status=200,
        )
        # Mock create request
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/servicedeskapi/request",
            json={"issueKey": "SD-101"},
            status=201,
        )
        # Mock get incident for return value
        sample_jira_incident["key"] = "SD-101"
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/SD-101",
            json=sample_jira_incident,
            status=200,
        )

        incident = jsm_adapter.create_incident(
            summary="New incident",
            description="Something broke",
            severity=Severity.HIGH,
            service="API Service",
            labels=["urgent"],
        )

        assert incident.key == "SD-101"

    def test_create_incident_no_service_desk(self, mock_credentials: MagicMock) -> None:
        """Test that create_incident raises error without service desk."""
        adapter = JSMAdapter()  # No default service desk

        with pytest.raises(ValidationError) as exc_info:
            adapter.create_incident(summary="Test")

        assert "Service desk is required" in str(exc_info.value)


class TestJSMAdapterSearchIncidents:
    """Tests for search_incidents method."""

    @responses.activate
    def test_search_incidents(self, jsm_adapter: JSMAdapter, sample_jira_incident: dict) -> None:
        """Test searching for incidents."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/search",
            json={
                "issues": [sample_jira_incident],
                "total": 1,
                "maxResults": 50,
            },
            status=200,
        )

        incidents = jsm_adapter.search_incidents(query="API error")

        assert len(incidents) == 1
        assert incidents[0].key == "SD-100"

    @responses.activate
    def test_search_by_severity(self, jsm_adapter: JSMAdapter, sample_jira_incident: dict) -> None:
        """Test searching by severity."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/search",
            json={"issues": [sample_jira_incident], "total": 1},
            status=200,
        )

        incidents = jsm_adapter.search_incidents(severity=Severity.HIGH)

        assert len(incidents) == 1
        # Verify priority filter was added to JQL
        assert "priority" in responses.calls[0].request.url

    @responses.activate
    def test_search_by_status(self, jsm_adapter: JSMAdapter, sample_jira_incident: dict) -> None:
        """Test searching by status."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/search",
            json={"issues": [sample_jira_incident], "total": 1},
            status=200,
        )

        incidents = jsm_adapter.search_incidents(status="Open")

        assert len(incidents) == 1
        assert "status" in responses.calls[0].request.url

    @responses.activate
    def test_search_no_results(self, jsm_adapter: JSMAdapter) -> None:
        """Test search with no results."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/search",
            json={"issues": [], "total": 0},
            status=200,
        )

        incidents = jsm_adapter.search_incidents(query="nonexistent")
        assert len(incidents) == 0


class TestJSMAdapterResolveIncident:
    """Tests for resolve_incident method."""

    @responses.activate
    def test_resolve_incident_success(self, jsm_adapter: JSMAdapter) -> None:
        """Test successful incident resolution."""
        # Mock add comment
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/servicedeskapi/request/SD-100/comment",
            json={"id": "10001"},
            status=201,
        )
        # Mock get transitions
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/SD-100/transitions",
            json={
                "transitions": [
                    {"id": "21", "name": "Resolve", "to": {"name": "Resolved"}},
                    {"id": "31", "name": "Close", "to": {"name": "Closed"}},
                ]
            },
            status=200,
        )
        # Mock execute transition
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issue/SD-100/transitions",
            status=204,
        )

        result = jsm_adapter.resolve_incident("SD-100", "Fixed the root cause")

        assert result.status == ResultStatus.SUCCESS
        assert "resolved" in result.message.lower()

    @responses.activate
    def test_resolve_incident_no_transition(self, jsm_adapter: JSMAdapter) -> None:
        """Test resolve when no resolve transition available."""
        # Mock add comment
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/servicedeskapi/request/SD-100/comment",
            json={"id": "10001"},
            status=201,
        )
        # Mock get transitions (no resolve)
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/SD-100/transitions",
            json={
                "transitions": [
                    {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
                ]
            },
            status=200,
        )

        result = jsm_adapter.resolve_incident("SD-100", "Fixed")

        assert result.status == ResultStatus.FAILED
        assert "available" in result.message.lower()

    @responses.activate
    def test_resolve_with_incident_object(
        self, jsm_adapter: JSMAdapter, sample_incident: Incident
    ) -> None:
        """Test resolve with Incident object."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/servicedeskapi/request/SD-100/comment",
            json={"id": "10001"},
            status=201,
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/SD-100/transitions",
            json={
                "transitions": [
                    {"id": "21", "name": "Done", "to": {"name": "Done"}},
                ]
            },
            status=200,
        )
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issue/SD-100/transitions",
            status=204,
        )

        result = jsm_adapter.resolve_incident(sample_incident, "Fixed")
        assert result.status == ResultStatus.SUCCESS


class TestJSMAdapterEscalateIncident:
    """Tests for escalate_incident method."""

    @responses.activate
    def test_escalate_incident(self, jsm_adapter: JSMAdapter) -> None:
        """Test escalating an incident."""
        # Mock update priority
        responses.add(
            responses.PUT,
            "https://test.atlassian.net/rest/api/3/issue/SD-100",
            status=204,
        )
        # Mock add comment
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/servicedeskapi/request/SD-100/comment",
            json={"id": "10001"},
            status=201,
        )

        result = jsm_adapter.escalate_incident(
            "SD-100",
            Severity.CRITICAL,
            reason="Customer impact increased",
        )

        assert result.status == ResultStatus.SUCCESS
        assert "critical" in result.message.lower()


class TestJSMAdapterLinkToIssue:
    """Tests for link_to_issue method."""

    @responses.activate
    def test_link_to_issue(self, jsm_adapter: JSMAdapter) -> None:
        """Test linking incident to issue."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issueLink",
            json={},
            status=201,
        )

        result = jsm_adapter.link_to_issue("SD-100", "ITI-220")

        assert result.status == ResultStatus.SUCCESS
        assert "Linked" in result.message

    @responses.activate
    def test_link_to_issue_with_objects(
        self, jsm_adapter: JSMAdapter, sample_incident: Incident
    ) -> None:
        """Test linking with Issue object."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issueLink",
            json={},
            status=201,
        )

        issue = Issue(
            key="ITI-220",
            summary="Related bug",
            issue_type="Bug",
            status="Open",
            labels=[],
        )

        result = jsm_adapter.link_to_issue(sample_incident, issue)
        assert result.status == ResultStatus.SUCCESS


class TestJSMAdapterAddComment:
    """Tests for add_comment method."""

    @responses.activate
    def test_add_public_comment(self, jsm_adapter: JSMAdapter) -> None:
        """Test adding a public comment."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/servicedeskapi/request/SD-100/comment",
            json={"id": "10001"},
            status=201,
        )

        result = jsm_adapter.add_comment("SD-100", "Update for customer", internal=False)

        assert result.status == ResultStatus.SUCCESS
        assert "Public" in result.message

    @responses.activate
    def test_add_internal_comment(self, jsm_adapter: JSMAdapter) -> None:
        """Test adding an internal comment."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/servicedeskapi/request/SD-100/comment",
            json={"id": "10001"},
            status=201,
        )

        result = jsm_adapter.add_comment("SD-100", "Internal note", internal=True)

        assert result.status == ResultStatus.SUCCESS
        assert "Internal" in result.message

    @responses.activate
    def test_add_comment_fallback_to_jira(self, jsm_adapter: JSMAdapter) -> None:
        """Test fallback to Jira API when JSM API fails."""
        # JSM API fails
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/servicedeskapi/request/SD-100/comment",
            json={"errorMessage": "Not a service desk request"},
            status=400,
        )
        # Jira API succeeds
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issue/SD-100/comment",
            json={"id": "10001"},
            status=201,
        )

        result = jsm_adapter.add_comment("SD-100", "Test comment")
        assert result.status == ResultStatus.SUCCESS


class TestJSMAdapterGetSLAStatus:
    """Tests for get_sla_status method."""

    @responses.activate
    def test_get_sla_status(self, jsm_adapter: JSMAdapter) -> None:
        """Test getting SLA status."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/servicedeskapi/request/SD-100/sla",
            json={
                "values": [
                    {
                        "name": "Time to First Response",
                        "ongoingCycle": {
                            "startTime": {"epochMillis": 1705315800000},
                            "goalDuration": {"millis": 3600000},
                            "elapsedTime": {"millis": 1800000},
                            "remainingTime": {"millis": 1800000},
                            "breached": False,
                            "paused": False,
                        },
                    },
                    {
                        "name": "Time to Resolution",
                        "ongoingCycle": {
                            "startTime": {"epochMillis": 1705315800000},
                            "goalDuration": {"millis": 14400000},
                            "elapsedTime": {"millis": 3600000},
                            "remainingTime": {"millis": 10800000},
                            "breached": False,
                            "paused": False,
                        },
                    },
                ]
            },
            status=200,
        )

        sla_statuses = jsm_adapter.get_sla_status("SD-100")

        assert len(sla_statuses) == 2
        assert sla_statuses[0].name == "Time to First Response"
        assert sla_statuses[0].elapsed == 1800  # seconds
        assert sla_statuses[0].remaining == 1800
        assert sla_statuses[0].breached is False
        assert sla_statuses[1].name == "Time to Resolution"

    @responses.activate
    def test_get_sla_status_not_found(self, jsm_adapter: JSMAdapter) -> None:
        """Test SLA status for non-JSM issue returns empty list."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/servicedeskapi/request/ITI-220/sla",
            json={"errorMessage": "Not a service desk request"},
            status=404,
        )

        sla_statuses = jsm_adapter.get_sla_status("ITI-220")
        assert sla_statuses == []


class TestJSMAdapterParseIncident:
    """Tests for _parse_incident method."""

    def test_parse_incident_with_timestamps(
        self, jsm_adapter: JSMAdapter, sample_jira_incident: dict
    ) -> None:
        """Test parsing incident with timestamps."""
        incident = jsm_adapter._parse_incident(sample_jira_incident)

        assert incident.created_at is not None
        assert incident.updated_at is not None
        assert isinstance(incident.created_at, datetime)

    def test_parse_incident_minimal(self, jsm_adapter: JSMAdapter) -> None:
        """Test parsing minimal incident data."""
        minimal_data = {
            "key": "SD-999",
            "fields": {
                "summary": "Minimal incident",
                "status": {"name": "Open"},
                "priority": {"name": "Medium"},
            },
        }

        incident = jsm_adapter._parse_incident(minimal_data)

        assert incident.key == "SD-999"
        assert incident.summary == "Minimal incident"
        assert incident.severity == Severity.MEDIUM
        assert incident.assignee is None
        assert incident.service is None

    def test_parse_incident_with_resolution(self, jsm_adapter: JSMAdapter) -> None:
        """Test parsing resolved incident."""
        resolved_data = {
            "key": "SD-100",
            "fields": {
                "summary": "Resolved incident",
                "status": {"name": "Done"},
                "priority": {"name": "Low"},
                "resolution": {"name": "Done"},
                "resolutiondate": "2024-01-17T10:00:00.000Z",
            },
        }

        incident = jsm_adapter._parse_incident(resolved_data)

        assert incident.resolution == "Done"
        assert incident.resolved_at is not None


class TestJSMAdapterRegistry:
    """Tests for registry integration."""

    def test_adapter_registered(self) -> None:
        """Test that JSMAdapter is registered with the registry."""
        from itsm_tools.core.registry import _incident_manager_registry

        # Import atlassian module to trigger registration
        import itsm_tools.atlassian  # noqa: F401

        assert "atlassian_jsm" in _incident_manager_registry


class TestJSMAdapterServiceDeskLookup:
    """Tests for service desk and request type lookup."""

    @responses.activate
    def test_get_service_desk_id_by_key(
        self, jsm_adapter: JSMAdapter, sample_service_desks: dict
    ) -> None:
        """Test looking up service desk ID by project key."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/servicedeskapi/servicedesk",
            json=sample_service_desks,
            status=200,
        )

        desk_id = jsm_adapter._get_service_desk_id("SD")
        assert desk_id == "1"

    def test_get_service_desk_id_numeric(self, jsm_adapter: JSMAdapter) -> None:
        """Test that numeric IDs are returned directly."""
        desk_id = jsm_adapter._get_service_desk_id("123")
        assert desk_id == "123"

    @responses.activate
    def test_get_request_type_id_by_name(
        self, jsm_adapter: JSMAdapter, sample_request_types: dict
    ) -> None:
        """Test looking up request type ID by name."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/servicedeskapi/servicedesk/1/requesttype",
            json=sample_request_types,
            status=200,
        )

        type_id = jsm_adapter._get_request_type_id("1", "Incident")
        assert type_id == 10

    def test_get_request_type_id_numeric(self, jsm_adapter: JSMAdapter) -> None:
        """Test that numeric request type IDs are returned directly."""
        type_id = jsm_adapter._get_request_type_id("1", "42")
        assert type_id == 42


class TestJSMAdapterADF:
    """Tests for ADF conversion methods."""

    def test_to_adf(self, jsm_adapter: JSMAdapter) -> None:
        """Test converting text to ADF."""
        adf = jsm_adapter._to_adf("Hello world")

        assert adf["type"] == "doc"
        assert adf["version"] == 1
        assert len(adf["content"]) == 1
        assert adf["content"][0]["content"][0]["text"] == "Hello world"

    def test_from_adf(self, jsm_adapter: JSMAdapter) -> None:
        """Test converting ADF to text."""
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello world"}],
                }
            ],
        }

        text = jsm_adapter._from_adf(adf)
        assert text == "Hello world"

    def test_from_adf_empty(self, jsm_adapter: JSMAdapter) -> None:
        """Test converting empty ADF."""
        assert jsm_adapter._from_adf({}) == ""
        assert jsm_adapter._from_adf(None) == ""  # type: ignore
