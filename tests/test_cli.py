"""Tests for the CLI module."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from itsm_tools.cli import (
    cmd_config_show,
    cmd_incident_comment,
    cmd_incident_create,
    cmd_incident_escalate,
    cmd_incident_get,
    cmd_incident_resolve,
    cmd_incident_search,
    cmd_issue_comment,
    cmd_issue_create,
    cmd_issue_get,
    cmd_issue_link,
    cmd_issue_search,
    cmd_issue_transition,
    cmd_wiki_append,
    cmd_wiki_create,
    cmd_wiki_get,
    cmd_wiki_search,
    cmd_wiki_update,
    main,
)
from itsm_tools.core.models import (
    Incident,
    Issue,
    Page,
    Result,
    ResultStatus,
    Severity,
    SLAStatus,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_issue() -> Issue:
    """Create a sample issue for testing."""
    return Issue(
        key="ITI-123",
        summary="Test issue",
        description="Test description",
        issue_type="Story",
        status="To Do",
        assignee="test@example.com",
        reporter="reporter@example.com",
        priority="High",
        labels=["test", "cli"],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        url="https://example.atlassian.net/browse/ITI-123",
        raw={},
    )


@pytest.fixture
def sample_page() -> Page:
    """Create a sample page for testing."""
    return Page(
        id="12345",
        title="Test Page",
        space_key="TEST",
        body="<p>Test content</p>",
        version=1,
        url="https://example.atlassian.net/wiki/spaces/TEST/pages/12345",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        raw={},
    )


@pytest.fixture
def sample_incident() -> Incident:
    """Create a sample incident for testing."""
    return Incident(
        key="SD-100",
        summary="Production outage",
        description="Server is down",
        status="Open",
        severity=Severity.HIGH,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        reporter="reporter@example.com",
        assignee="oncall@example.com",
        url="https://example.atlassian.net/servicedesk/customer/portal/1/SD-100",
        raw={},
    )


@pytest.fixture
def sample_result() -> Result:
    """Create a sample result for testing."""
    return Result(
        status=ResultStatus.SUCCESS,
        message="Operation completed successfully",
        data={"key": "value"},
    )


# =============================================================================
# Issue Command Tests
# =============================================================================


class TestIssueCommands:
    """Tests for issue commands."""

    def test_cmd_issue_get_success(self, sample_issue: Issue) -> None:
        """Test getting an issue successfully."""
        mock_jira = MagicMock()
        mock_jira.get_issue.return_value = sample_issue
        mock_jira.__enter__ = MagicMock(return_value=mock_jira)
        mock_jira.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(issue_key="ITI-123", json=False)

        with patch("itsm_tools.atlassian.JiraAdapter", return_value=mock_jira):
            result = cmd_issue_get(args)

        assert result == 0
        mock_jira.get_issue.assert_called_once_with("ITI-123")

    def test_cmd_issue_get_not_found(self) -> None:
        """Test getting a non-existent issue."""
        mock_jira = MagicMock()
        mock_jira.get_issue.return_value = None
        mock_jira.__enter__ = MagicMock(return_value=mock_jira)
        mock_jira.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(issue_key="ITI-999", json=False)

        with patch("itsm_tools.atlassian.JiraAdapter", return_value=mock_jira):
            result = cmd_issue_get(args)

        assert result == 1

    def test_cmd_issue_create_success(self, sample_issue: Issue) -> None:
        """Test creating an issue successfully."""
        mock_jira = MagicMock()
        mock_jira.create_issue.return_value = sample_issue
        mock_jira.__enter__ = MagicMock(return_value=mock_jira)
        mock_jira.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(
            project="ITI",
            summary="Test issue",
            description="Test description",
            type="Story",
            labels="test,cli",
            parent=None,
        )

        with patch("itsm_tools.atlassian.JiraAdapter", return_value=mock_jira):
            result = cmd_issue_create(args)

        assert result == 0
        mock_jira.create_issue.assert_called_once()

    def test_cmd_issue_search_success(self, sample_issue: Issue) -> None:
        """Test searching issues successfully."""
        mock_jira = MagicMock()
        mock_jira.search.return_value = [sample_issue]
        mock_jira.__enter__ = MagicMock(return_value=mock_jira)
        mock_jira.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(query='project = "ITI"', limit=50)

        with patch("itsm_tools.atlassian.JiraAdapter", return_value=mock_jira):
            result = cmd_issue_search(args)

        assert result == 0
        mock_jira.search.assert_called_once()

    def test_cmd_issue_transition_success(self, sample_result: Result) -> None:
        """Test transitioning an issue successfully."""
        mock_jira = MagicMock()
        mock_jira.transition.return_value = sample_result
        mock_jira.__enter__ = MagicMock(return_value=mock_jira)
        mock_jira.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(issue_key="ITI-123", to="In Progress")

        with patch("itsm_tools.atlassian.JiraAdapter", return_value=mock_jira):
            result = cmd_issue_transition(args)

        assert result == 0
        mock_jira.transition.assert_called_once_with("ITI-123", "In Progress")

    def test_cmd_issue_comment_success(self, sample_result: Result) -> None:
        """Test adding a comment successfully."""
        mock_jira = MagicMock()
        mock_jira.comment.return_value = sample_result
        mock_jira.__enter__ = MagicMock(return_value=mock_jira)
        mock_jira.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(issue_key="ITI-123", body="Test comment")

        with patch("itsm_tools.atlassian.JiraAdapter", return_value=mock_jira):
            result = cmd_issue_comment(args)

        assert result == 0
        mock_jira.comment.assert_called_once_with("ITI-123", "Test comment")

    def test_cmd_issue_link_success(self, sample_result: Result) -> None:
        """Test linking issues successfully."""
        mock_jira = MagicMock()
        mock_jira.link_issues.return_value = sample_result
        mock_jira.__enter__ = MagicMock(return_value=mock_jira)
        mock_jira.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(
            source="ITI-123", target="ITI-456", link_type="Blocks"
        )

        with patch("itsm_tools.atlassian.JiraAdapter", return_value=mock_jira):
            result = cmd_issue_link(args)

        assert result == 0
        mock_jira.link_issues.assert_called_once_with("ITI-123", "ITI-456", "Blocks")


# =============================================================================
# Wiki Command Tests
# =============================================================================


class TestWikiCommands:
    """Tests for wiki commands."""

    def test_cmd_wiki_get_success(self, sample_page: Page) -> None:
        """Test getting a page successfully."""
        mock_confluence = MagicMock()
        mock_confluence.get_page.return_value = sample_page
        mock_confluence.__enter__ = MagicMock(return_value=mock_confluence)
        mock_confluence.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(page_id="12345", json=False, body=False)

        with patch(
            "itsm_tools.atlassian.ConfluenceAdapter", return_value=mock_confluence
        ):
            result = cmd_wiki_get(args)

        assert result == 0
        mock_confluence.get_page.assert_called_once_with("12345")

    def test_cmd_wiki_get_not_found(self) -> None:
        """Test getting a non-existent page."""
        mock_confluence = MagicMock()
        mock_confluence.get_page.return_value = None
        mock_confluence.__enter__ = MagicMock(return_value=mock_confluence)
        mock_confluence.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(page_id="99999", json=False, body=False)

        with patch(
            "itsm_tools.atlassian.ConfluenceAdapter", return_value=mock_confluence
        ):
            result = cmd_wiki_get(args)

        assert result == 1

    def test_cmd_wiki_search_success(self, sample_page: Page) -> None:
        """Test searching pages successfully."""
        mock_confluence = MagicMock()
        mock_confluence.search.return_value = [sample_page]
        mock_confluence.__enter__ = MagicMock(return_value=mock_confluence)
        mock_confluence.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(query="test", space=None, limit=25, json=False)

        with patch(
            "itsm_tools.atlassian.ConfluenceAdapter", return_value=mock_confluence
        ):
            result = cmd_wiki_search(args)

        assert result == 0
        mock_confluence.search.assert_called_once()

    def test_cmd_wiki_create_success(self, sample_page: Page) -> None:
        """Test creating a page successfully."""
        mock_confluence = MagicMock()
        mock_confluence.create_page.return_value = sample_page
        mock_confluence.__enter__ = MagicMock(return_value=mock_confluence)
        mock_confluence.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(
            title="New Page",
            space="TEST",
            body="<p>Content</p>",
            body_file=None,
            parent=None,
        )

        with patch(
            "itsm_tools.atlassian.ConfluenceAdapter", return_value=mock_confluence
        ):
            result = cmd_wiki_create(args)

        assert result == 0
        mock_confluence.create_page.assert_called_once()

    def test_cmd_wiki_update_success(self, sample_page: Page) -> None:
        """Test updating a page successfully."""
        mock_confluence = MagicMock()
        mock_confluence.update_page.return_value = sample_page
        mock_confluence.__enter__ = MagicMock(return_value=mock_confluence)
        mock_confluence.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(
            page_id="12345",
            title=None,
            body="<p>Updated content</p>",
            body_file=None,
        )

        with patch(
            "itsm_tools.atlassian.ConfluenceAdapter", return_value=mock_confluence
        ):
            result = cmd_wiki_update(args)

        assert result == 0

    def test_cmd_wiki_append_success(self, sample_page: Page) -> None:
        """Test appending to a page successfully."""
        mock_confluence = MagicMock()
        mock_confluence.append_to_page.return_value = sample_page
        mock_confluence.__enter__ = MagicMock(return_value=mock_confluence)
        mock_confluence.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(
            page_id="12345", content="<p>More content</p>", content_file=None
        )

        with patch(
            "itsm_tools.atlassian.ConfluenceAdapter", return_value=mock_confluence
        ):
            result = cmd_wiki_append(args)

        assert result == 0
        mock_confluence.append_to_page.assert_called_once_with(
            "12345", "<p>More content</p>"
        )


# =============================================================================
# Incident Command Tests
# =============================================================================


class TestIncidentCommands:
    """Tests for incident commands."""

    def test_cmd_incident_get_success(self, sample_incident: Incident) -> None:
        """Test getting an incident successfully."""
        mock_jsm = MagicMock()
        mock_jsm.get_incident.return_value = sample_incident
        mock_jsm.get_sla_status.return_value = None
        mock_jsm.__enter__ = MagicMock(return_value=mock_jsm)
        mock_jsm.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(incident_key="SD-100", json=False, sla=False)

        with patch("itsm_tools.atlassian.JSMAdapter", return_value=mock_jsm):
            result = cmd_incident_get(args)

        assert result == 0
        mock_jsm.get_incident.assert_called_once_with("SD-100")

    def test_cmd_incident_get_with_sla(self, sample_incident: Incident) -> None:
        """Test getting an incident with SLA info."""
        sla_status = SLAStatus(
            name="Time to Resolution",
            status="ONGOING",
            remaining_time_millis=3600000,
            elapsed_time_millis=1800000,
            breached=False,
            raw={},
        )

        mock_jsm = MagicMock()
        mock_jsm.get_incident.return_value = sample_incident
        mock_jsm.get_sla_status.return_value = [sla_status]
        mock_jsm.__enter__ = MagicMock(return_value=mock_jsm)
        mock_jsm.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(incident_key="SD-100", json=False, sla=True)

        with patch("itsm_tools.atlassian.JSMAdapter", return_value=mock_jsm):
            result = cmd_incident_get(args)

        assert result == 0
        mock_jsm.get_sla_status.assert_called_once_with("SD-100")

    def test_cmd_incident_get_not_found(self) -> None:
        """Test getting a non-existent incident."""
        mock_jsm = MagicMock()
        mock_jsm.get_incident.return_value = None
        mock_jsm.__enter__ = MagicMock(return_value=mock_jsm)
        mock_jsm.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(incident_key="SD-999", json=False, sla=False)

        with patch("itsm_tools.atlassian.JSMAdapter", return_value=mock_jsm):
            result = cmd_incident_get(args)

        assert result == 1

    def test_cmd_incident_create_success(self, sample_incident: Incident) -> None:
        """Test creating an incident successfully."""
        mock_jsm = MagicMock()
        mock_jsm.create_incident.return_value = sample_incident
        mock_jsm.__enter__ = MagicMock(return_value=mock_jsm)
        mock_jsm.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(
            summary="Production outage",
            description="Server is down",
            severity="high",
            service=None,
            service_desk=None,
            labels=None,
        )

        with patch("itsm_tools.atlassian.JSMAdapter", return_value=mock_jsm):
            result = cmd_incident_create(args)

        assert result == 0
        mock_jsm.create_incident.assert_called_once()

    def test_cmd_incident_search_success(self, sample_incident: Incident) -> None:
        """Test searching incidents successfully."""
        mock_jsm = MagicMock()
        mock_jsm.search_incidents.return_value = [sample_incident]
        mock_jsm.__enter__ = MagicMock(return_value=mock_jsm)
        mock_jsm.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(
            query="status = Open",
            severity=None,
            status=None,
            service_desk=None,
            limit=50,
        )

        with patch("itsm_tools.atlassian.JSMAdapter", return_value=mock_jsm):
            result = cmd_incident_search(args)

        assert result == 0
        mock_jsm.search_incidents.assert_called_once()

    def test_cmd_incident_resolve_success(self, sample_result: Result) -> None:
        """Test resolving an incident successfully."""
        mock_jsm = MagicMock()
        mock_jsm.resolve_incident.return_value = sample_result
        mock_jsm.__enter__ = MagicMock(return_value=mock_jsm)
        mock_jsm.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(incident_key="SD-100", resolution="Fixed root cause")

        with patch("itsm_tools.atlassian.JSMAdapter", return_value=mock_jsm):
            result = cmd_incident_resolve(args)

        assert result == 0
        mock_jsm.resolve_incident.assert_called_once_with("SD-100", "Fixed root cause")

    def test_cmd_incident_resolve_failure(self) -> None:
        """Test resolving an incident that fails."""
        failure_result = Result(
            status=ResultStatus.FAILED,
            message="No resolve transition available",
            data={},
        )

        mock_jsm = MagicMock()
        mock_jsm.resolve_incident.return_value = failure_result
        mock_jsm.__enter__ = MagicMock(return_value=mock_jsm)
        mock_jsm.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(incident_key="SD-100", resolution="Fixed")

        with patch("itsm_tools.atlassian.JSMAdapter", return_value=mock_jsm):
            result = cmd_incident_resolve(args)

        assert result == 1

    def test_cmd_incident_escalate_success(self, sample_result: Result) -> None:
        """Test escalating an incident successfully."""
        mock_jsm = MagicMock()
        mock_jsm.escalate_incident.return_value = sample_result
        mock_jsm.__enter__ = MagicMock(return_value=mock_jsm)
        mock_jsm.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(
            incident_key="SD-100", severity="critical", reason="Need senior help"
        )

        with patch("itsm_tools.atlassian.JSMAdapter", return_value=mock_jsm):
            result = cmd_incident_escalate(args)

        assert result == 0
        mock_jsm.escalate_incident.assert_called_once()

    def test_cmd_incident_comment_success(self, sample_result: Result) -> None:
        """Test adding a comment to an incident."""
        mock_jsm = MagicMock()
        mock_jsm.add_comment.return_value = sample_result
        mock_jsm.__enter__ = MagicMock(return_value=mock_jsm)
        mock_jsm.__exit__ = MagicMock(return_value=False)

        args = argparse.Namespace(
            incident_key="SD-100", body="Investigation ongoing", internal=False
        )

        with patch("itsm_tools.atlassian.JSMAdapter", return_value=mock_jsm):
            result = cmd_incident_comment(args)

        assert result == 0
        mock_jsm.add_comment.assert_called_once()


# =============================================================================
# Config Command Tests
# =============================================================================


class TestConfigCommands:
    """Tests for config commands."""

    def test_cmd_config_show_no_credentials(self) -> None:
        """Test showing configuration when no credentials exist."""
        args = argparse.Namespace()

        # Mock environment variables and keyring
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "itsm_tools.atlassian.credentials.get_credentials",
                side_effect=ValueError("No credentials found"),
            ):
                result = cmd_config_show(args)

        # Should return 0 even if no credentials
        assert result == 0

    def test_cmd_config_show_with_env_vars(self) -> None:
        """Test showing configuration from environment variables."""
        args = argparse.Namespace()

        env_vars = {
            "JIRA_BASE_URL": "https://example.atlassian.net",
            "JIRA_USER_EMAIL": "test@example.com",
            "JIRA_API_TOKEN": "secret-token",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            result = cmd_config_show(args)

        assert result == 0


# =============================================================================
# Main Entry Point Tests
# =============================================================================


class TestMain:
    """Tests for main entry point."""

    def test_main_no_args(self) -> None:
        """Test main with no arguments shows help."""
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["itsm"]):
                main()

        # argparse exits with 2 for missing required args
        assert exc_info.value.code == 2

    def test_main_help(self) -> None:
        """Test main --help."""
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["itsm", "--help"]):
                main()

        assert exc_info.value.code == 0

    def test_main_issue_subcommand_help(self) -> None:
        """Test issue subcommand help."""
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["itsm", "issue", "--help"]):
                main()

        assert exc_info.value.code == 0

    def test_main_wiki_subcommand_help(self) -> None:
        """Test wiki subcommand help."""
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["itsm", "wiki", "--help"]):
                main()

        assert exc_info.value.code == 0

    def test_main_incident_subcommand_help(self) -> None:
        """Test incident subcommand help."""
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["itsm", "incident", "--help"]):
                main()

        assert exc_info.value.code == 0