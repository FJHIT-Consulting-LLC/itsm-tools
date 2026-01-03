"""Tests for core data models."""

import pytest

from itsm_tools.core.models import (
    Incident,
    Issue,
    Page,
    Result,
    ResultStatus,
    Severity,
    SLAStatus,
)


class TestIssue:
    """Tests for Issue model."""

    def test_create_issue(self) -> None:
        """Test creating an Issue."""
        issue = Issue(
            key="ITI-220",
            summary="Test issue",
            issue_type="Story",
            status="To Do",
        )
        assert issue.key == "ITI-220"
        assert issue.summary == "Test issue"
        assert issue.issue_type == "Story"
        assert issue.status == "To Do"

    def test_issue_optional_fields(self) -> None:
        """Test Issue optional fields have defaults."""
        issue = Issue(
            key="ITI-220",
            summary="Test",
            issue_type="Task",
            status="Open",
        )
        assert issue.description is None
        assert issue.assignee is None
        assert issue.labels == []
        assert issue.raw == {}

    def test_issue_with_labels(self) -> None:
        """Test Issue with labels."""
        issue = Issue(
            key="ITI-220",
            summary="Test",
            issue_type="Task",
            status="Open",
            labels=["automation", "ci"],
        )
        assert issue.labels == ["automation", "ci"]


class TestPage:
    """Tests for Page model."""

    def test_create_page(self) -> None:
        """Test creating a Page."""
        page = Page(
            id="12345",
            title="Test Page",
        )
        assert page.id == "12345"
        assert page.title == "Test Page"
        assert page.version == 1

    def test_page_with_content(self) -> None:
        """Test Page with content."""
        page = Page(
            id="12345",
            title="Test Page",
            content="<h1>Hello</h1>",
            space="DEVOPS",
        )
        assert page.content == "<h1>Hello</h1>"
        assert page.space == "DEVOPS"


class TestIncident:
    """Tests for Incident model."""

    def test_create_incident(self) -> None:
        """Test creating an Incident."""
        incident = Incident(
            key="INC-001",
            summary="Test incident",
            severity=Severity.HIGH,
            status="Open",
        )
        assert incident.key == "INC-001"
        assert incident.severity == Severity.HIGH
        assert incident.status == "Open"

    def test_incident_severity_enum(self) -> None:
        """Test Severity enum values."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.INFO.value == "info"


class TestResult:
    """Tests for Result model."""

    def test_success_result(self) -> None:
        """Test successful Result."""
        result = Result(
            status=ResultStatus.SUCCESS,
            message="Created successfully",
            resource_id="ITI-220",
        )
        assert result.success is True
        assert result.status == ResultStatus.SUCCESS

    def test_failed_result(self) -> None:
        """Test failed Result."""
        result = Result(
            status=ResultStatus.FAILED,
            message="Operation failed",
        )
        assert result.success is False
        assert result.status == ResultStatus.FAILED

    def test_no_change_result(self) -> None:
        """Test no-change Result is considered success."""
        result = Result(
            status=ResultStatus.NO_CHANGE,
            message="Already exists",
        )
        assert result.success is True


class TestSLAStatus:
    """Tests for SLAStatus model."""

    def test_create_sla_status(self) -> None:
        """Test creating SLAStatus."""
        sla = SLAStatus(
            name="Time to First Response",
            remaining=3600,
            breached=False,
        )
        assert sla.name == "Time to First Response"
        assert sla.remaining == 3600
        assert sla.breached is False

    def test_breached_sla(self) -> None:
        """Test breached SLA."""
        sla = SLAStatus(
            name="Resolution Time",
            remaining=0,
            breached=True,
        )
        assert sla.breached is True
