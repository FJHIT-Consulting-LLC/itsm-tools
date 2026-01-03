"""Shared pytest fixtures for itsm-tools tests."""

import pytest

from itsm_tools.core.models import Incident, Issue, Page, Severity


@pytest.fixture
def sample_issue() -> Issue:
    """Create a sample Issue for testing."""
    return Issue(
        key="ITI-220",
        summary="Test issue",
        description="Test description",
        issue_type="Story",
        status="To Do",
        assignee="test@example.com",
        labels=["test", "automation"],
        provider="atlassian_jira",
    )


@pytest.fixture
def sample_page() -> Page:
    """Create a sample Page for testing."""
    return Page(
        id="83820565",
        title="Test Page",
        content="<h1>Test</h1><p>Content</p>",
        space="DEVOPS",
        version=1,
        provider="atlassian_confluence",
    )


@pytest.fixture
def sample_incident() -> Incident:
    """Create a sample Incident for testing."""
    return Incident(
        key="INC-001",
        summary="Test incident",
        description="Test incident description",
        severity=Severity.MEDIUM,
        status="Open",
        service="Test Service",
        labels=["test", "automated"],
        provider="atlassian_jsm",
    )
