"""Tests for JiraAdapter."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import responses

from itsm_tools.atlassian.jira import JiraAdapter
from itsm_tools.core.exceptions import NotFoundError, ValidationError
from itsm_tools.core.models import Issue, ResultStatus


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
def jira_adapter(mock_credentials: MagicMock) -> JiraAdapter:
    """Create a JiraAdapter instance for testing."""
    return JiraAdapter(project="ITI")


@pytest.fixture
def sample_issue() -> Issue:
    """Sample Issue model for testing."""
    return Issue(
        key="ITI-220",
        summary="Test issue",
        issue_type="Story",
        status="To Do",
        labels=["test"],
        provider="atlassian_jira",
    )


@pytest.fixture
def sample_jira_issue() -> dict:
    """Sample Jira API issue response."""
    return {
        "key": "ITI-220",
        "fields": {
            "summary": "Test issue",
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
            "issuetype": {"name": "Story"},
            "status": {"name": "To Do"},
            "assignee": {
                "emailAddress": "assignee@example.com",
                "displayName": "Test User",
            },
            "reporter": {
                "emailAddress": "reporter@example.com",
                "displayName": "Reporter User",
            },
            "labels": ["test", "automation"],
            "priority": {"name": "Medium"},
            "created": "2024-01-15T10:30:00.000Z",
            "updated": "2024-01-16T14:45:00.000Z",
            "parent": {"key": "ITI-100"},
        },
    }


class TestJiraAdapterInit:
    """Tests for JiraAdapter initialization."""

    def test_init_with_project(self, mock_credentials: MagicMock) -> None:
        """Test initialization with project."""
        adapter = JiraAdapter(project="ITI")
        assert adapter.project == "ITI"
        assert adapter.provider_name == "atlassian_jira"

    def test_init_with_config(self, mock_credentials: MagicMock) -> None:
        """Test initialization with config dict (registry pattern)."""
        adapter = JiraAdapter(config={"project": "TEST"})
        assert adapter.project == "TEST"

    def test_init_without_project(self, mock_credentials: MagicMock) -> None:
        """Test initialization without project."""
        adapter = JiraAdapter()
        assert adapter.project is None


class TestJiraAdapterConnection:
    """Tests for connect/disconnect methods."""

    @responses.activate
    def test_connect(self, jira_adapter: JiraAdapter) -> None:
        """Test connection establishment."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/serverInfo",
            json={"baseUrl": "https://test.atlassian.net"},
            status=200,
        )

        jira_adapter.connect()
        assert jira_adapter._connected is True

    def test_disconnect(self, jira_adapter: JiraAdapter) -> None:
        """Test disconnection."""
        jira_adapter._connected = True
        jira_adapter.disconnect()
        assert jira_adapter._connected is False


class TestJiraAdapterGetIssue:
    """Tests for get_issue method."""

    @responses.activate
    def test_get_issue_found(self, jira_adapter: JiraAdapter, sample_jira_issue: dict) -> None:
        """Test getting an existing issue."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220",
            json=sample_jira_issue,
            status=200,
        )

        issue = jira_adapter.get_issue("ITI-220")

        assert issue is not None
        assert issue.key == "ITI-220"
        assert issue.summary == "Test issue"
        assert issue.issue_type == "Story"
        assert issue.status == "To Do"
        assert issue.assignee == "assignee@example.com"
        assert issue.reporter == "reporter@example.com"
        assert issue.labels == ["test", "automation"]
        assert issue.priority == "Medium"
        assert issue.parent_key == "ITI-100"
        assert issue.provider == "atlassian_jira"

    @responses.activate
    def test_get_issue_not_found(self, jira_adapter: JiraAdapter) -> None:
        """Test getting a non-existent issue."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/FAKE-999",
            json={"errorMessages": ["Issue does not exist"]},
            status=404,
        )

        issue = jira_adapter.get_issue("FAKE-999")
        assert issue is None


class TestJiraAdapterCreateIssue:
    """Tests for create_issue method."""

    @responses.activate
    def test_create_issue_success(self, jira_adapter: JiraAdapter, sample_jira_issue: dict) -> None:
        """Test successful issue creation."""
        # Mock create response
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issue",
            json={"key": "ITI-221", "id": "12345"},
            status=201,
        )
        # Mock get issue for return value
        sample_jira_issue["key"] = "ITI-221"
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/ITI-221",
            json=sample_jira_issue,
            status=200,
        )

        issue = jira_adapter.create_issue(
            summary="New test issue",
            description="Test description",
            issue_type="Story",
            labels=["test"],
        )

        assert issue.key == "ITI-221"
        assert len(responses.calls) == 2

    @responses.activate
    def test_create_issue_with_parent(
        self, jira_adapter: JiraAdapter, sample_jira_issue: dict
    ) -> None:
        """Test creating a subtask with parent."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issue",
            json={"key": "ITI-222", "id": "12346"},
            status=201,
        )
        sample_jira_issue["key"] = "ITI-222"
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/ITI-222",
            json=sample_jira_issue,
            status=200,
        )

        issue = jira_adapter.create_issue(
            summary="Subtask",
            issue_type="Sub-task",
            parent_key="ITI-220",
        )

        assert issue.key == "ITI-222"
        # Verify parent was included in request
        request_body = responses.calls[0].request.body
        assert b"parent" in request_body

    def test_create_issue_no_project(self, mock_credentials: MagicMock) -> None:
        """Test that create_issue raises error without project."""
        adapter = JiraAdapter()  # No default project

        with pytest.raises(ValidationError) as exc_info:
            adapter.create_issue(summary="Test")

        assert "Project key is required" in str(exc_info.value)


class TestJiraAdapterSearch:
    """Tests for search method."""

    @responses.activate
    def test_search_issues(self, jira_adapter: JiraAdapter, sample_jira_issue: dict) -> None:
        """Test searching for issues."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/search",
            json={
                "issues": [sample_jira_issue],
                "total": 1,
                "maxResults": 50,
            },
            status=200,
        )

        issues = jira_adapter.search("project = ITI AND status = 'To Do'")

        assert len(issues) == 1
        assert issues[0].key == "ITI-220"
        assert "jql=project" in responses.calls[0].request.url

    @responses.activate
    def test_search_no_results(self, jira_adapter: JiraAdapter) -> None:
        """Test search with no results."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/search",
            json={"issues": [], "total": 0, "maxResults": 50},
            status=200,
        )

        issues = jira_adapter.search("project = FAKE")
        assert len(issues) == 0

    @responses.activate
    def test_search_with_max_results(self, jira_adapter: JiraAdapter) -> None:
        """Test search respects max_results."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/search",
            json={"issues": [], "total": 0, "maxResults": 10},
            status=200,
        )

        jira_adapter.search("project = ITI", max_results=10)

        assert "maxResults=10" in responses.calls[0].request.url


class TestJiraAdapterTransition:
    """Tests for transition method."""

    @responses.activate
    def test_transition_success(self, jira_adapter: JiraAdapter) -> None:
        """Test successful transition."""
        # Mock get transitions
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220/transitions",
            json={
                "transitions": [
                    {"id": "21", "name": "In Progress", "to": {"name": "In Progress"}},
                    {"id": "31", "name": "Done", "to": {"name": "Done"}},
                ]
            },
            status=200,
        )
        # Mock execute transition
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220/transitions",
            status=204,
        )

        result = jira_adapter.transition("ITI-220", "In Progress")

        assert result.status == ResultStatus.SUCCESS
        assert "Transitioned" in result.message

    @responses.activate
    def test_transition_not_available(self, jira_adapter: JiraAdapter) -> None:
        """Test transition to unavailable status."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220/transitions",
            json={
                "transitions": [
                    {"id": "21", "name": "In Progress", "to": {"name": "In Progress"}},
                ]
            },
            status=200,
        )

        result = jira_adapter.transition("ITI-220", "Invalid Status")

        assert result.status == ResultStatus.FAILED
        assert "not available" in result.message

    @responses.activate
    def test_transition_with_issue_object(
        self, jira_adapter: JiraAdapter, sample_issue: Issue
    ) -> None:
        """Test transition with Issue object."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220/transitions",
            json={
                "transitions": [
                    {"id": "21", "name": "Done", "to": {"name": "Done"}},
                ]
            },
            status=200,
        )
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220/transitions",
            status=204,
        )

        result = jira_adapter.transition(sample_issue, "Done")
        assert result.status == ResultStatus.SUCCESS


class TestJiraAdapterComment:
    """Tests for comment method."""

    @responses.activate
    def test_add_comment(self, jira_adapter: JiraAdapter) -> None:
        """Test adding a comment."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220/comment",
            json={"id": "10001"},
            status=201,
        )

        result = jira_adapter.comment("ITI-220", "Test comment")

        assert result.status == ResultStatus.SUCCESS
        assert "Comment added" in result.message


class TestJiraAdapterLinkIssues:
    """Tests for link_issues method."""

    @responses.activate
    def test_link_issues(self, jira_adapter: JiraAdapter) -> None:
        """Test linking two issues."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/rest/api/3/issueLink",
            json={},
            status=201,
        )

        result = jira_adapter.link_issues("ITI-220", "ITI-221", "Blocks")

        assert result.status == ResultStatus.SUCCESS
        assert "Linked" in result.message


class TestJiraAdapterUpdateIssue:
    """Tests for update_issue method."""

    @responses.activate
    def test_update_issue(self, jira_adapter: JiraAdapter, sample_jira_issue: dict) -> None:
        """Test updating an issue."""
        responses.add(
            responses.PUT,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220",
            status=204,
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220",
            json=sample_jira_issue,
            status=200,
        )

        issue = jira_adapter.update_issue(
            "ITI-220",
            summary="Updated summary",
            labels=["updated"],
        )

        assert issue.key == "ITI-220"


class TestJiraAdapterAddLabels:
    """Tests for add_labels method."""

    @responses.activate
    def test_add_labels(self, jira_adapter: JiraAdapter) -> None:
        """Test adding labels."""
        responses.add(
            responses.PUT,
            "https://test.atlassian.net/rest/api/3/issue/ITI-220",
            status=204,
        )

        result = jira_adapter.add_labels("ITI-220", ["new-label", "another"])

        assert result.status == ResultStatus.SUCCESS
        assert "new-label" in result.message


class TestJiraAdapterADF:
    """Tests for ADF conversion methods."""

    def test_to_adf_simple(self, jira_adapter: JiraAdapter) -> None:
        """Test converting plain text to ADF."""
        adf = jira_adapter._to_adf("Hello world")

        assert adf["type"] == "doc"
        assert adf["version"] == 1
        assert len(adf["content"]) == 1
        assert adf["content"][0]["type"] == "paragraph"
        assert adf["content"][0]["content"][0]["text"] == "Hello world"

    def test_to_adf_multiline(self, jira_adapter: JiraAdapter) -> None:
        """Test converting multiline text to ADF."""
        adf = jira_adapter._to_adf("Line 1\nLine 2\nLine 3")

        assert len(adf["content"]) == 3

    def test_from_adf_simple(self, jira_adapter: JiraAdapter) -> None:
        """Test converting ADF to plain text."""
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

        text = jira_adapter._from_adf(adf)
        assert text == "Hello world"

    def test_from_adf_empty(self, jira_adapter: JiraAdapter) -> None:
        """Test converting empty ADF."""
        assert jira_adapter._from_adf({}) == ""
        assert jira_adapter._from_adf(None) == ""  # type: ignore


class TestJiraAdapterRegistry:
    """Tests for registry integration."""

    def test_adapter_registered(self) -> None:
        """Test that JiraAdapter is registered with the registry."""
        from itsm_tools.core.registry import _issue_tracker_registry

        # Import atlassian module to trigger registration
        import itsm_tools.atlassian  # noqa: F401

        assert "atlassian_jira" in _issue_tracker_registry


class TestJiraAdapterParseIssue:
    """Tests for _parse_issue method."""

    def test_parse_issue_with_timestamps(
        self, jira_adapter: JiraAdapter, sample_jira_issue: dict
    ) -> None:
        """Test parsing issue with timestamps."""
        issue = jira_adapter._parse_issue(sample_jira_issue)

        assert issue.created_at is not None
        assert issue.updated_at is not None
        assert isinstance(issue.created_at, datetime)

    def test_parse_issue_minimal(self, jira_adapter: JiraAdapter) -> None:
        """Test parsing minimal issue data."""
        minimal_data = {
            "key": "ITI-999",
            "fields": {
                "summary": "Minimal issue",
                "issuetype": {"name": "Task"},
                "status": {"name": "Open"},
            },
        }

        issue = jira_adapter._parse_issue(minimal_data)

        assert issue.key == "ITI-999"
        assert issue.summary == "Minimal issue"
        assert issue.assignee is None
        assert issue.labels == []
