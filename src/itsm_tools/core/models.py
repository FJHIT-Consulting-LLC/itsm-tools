"""Provider-agnostic data models for ITSM operations."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Incident severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ResultStatus(str, Enum):
    """Operation result status."""

    SUCCESS = "success"
    FAILED = "failed"
    NO_CHANGE = "no_change"
    DRY_RUN = "dry_run"


class Issue(BaseModel):
    """Provider-agnostic issue representation."""

    key: str = Field(description="Unique issue identifier (e.g., 'ITI-220')")
    summary: str = Field(description="Issue title/summary")
    description: str | None = Field(default=None, description="Issue description")
    issue_type: str = Field(description="Issue type (e.g., 'Story', 'Bug', 'Task')")
    status: str = Field(description="Current status (e.g., 'To Do', 'In Progress')")
    assignee: str | None = Field(default=None, description="Assigned user")
    reporter: str | None = Field(default=None, description="User who created the issue")
    labels: list[str] = Field(default_factory=list, description="Issue labels/tags")
    priority: str | None = Field(default=None, description="Issue priority")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")
    url: str | None = Field(default=None, description="Web URL for the issue")
    parent_key: str | None = Field(default=None, description="Parent issue key (for subtasks)")
    provider: str | None = Field(default=None, description="Provider name (e.g., 'atlassian_jira')")
    raw: dict[str, Any] = Field(default_factory=dict, description="Raw provider response")

    class Config:
        """Pydantic configuration."""

        extra = "allow"


class Page(BaseModel):
    """Provider-agnostic wiki page representation."""

    id: str = Field(description="Unique page identifier")
    title: str = Field(description="Page title")
    content: str | None = Field(default=None, description="Page content (HTML or markdown)")
    space: str | None = Field(default=None, description="Space/container identifier")
    version: int = Field(default=1, description="Page version number")
    author: str | None = Field(default=None, description="Page author")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")
    url: str | None = Field(default=None, description="Web URL for the page")
    parent_id: str | None = Field(default=None, description="Parent page ID")
    provider: str | None = Field(default=None, description="Provider name")
    raw: dict[str, Any] = Field(default_factory=dict, description="Raw provider response")

    class Config:
        """Pydantic configuration."""

        extra = "allow"


class Incident(BaseModel):
    """Provider-agnostic incident representation."""

    key: str = Field(description="Unique incident identifier")
    summary: str = Field(description="Incident title/summary")
    description: str | None = Field(default=None, description="Incident description")
    severity: Severity = Field(description="Incident severity level")
    status: str = Field(description="Current status (e.g., 'Open', 'Resolved')")
    service: str | None = Field(default=None, description="Affected service/component")
    assignee: str | None = Field(default=None, description="Assigned responder")
    reporter: str | None = Field(default=None, description="User who reported the incident")
    labels: list[str] = Field(default_factory=list, description="Incident labels/tags")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")
    resolved_at: datetime | None = Field(default=None, description="Resolution timestamp")
    resolution: str | None = Field(default=None, description="Resolution notes")
    url: str | None = Field(default=None, description="Web URL for the incident")
    linked_issues: list[str] = Field(default_factory=list, description="Linked issue keys")
    provider: str | None = Field(default=None, description="Provider name")
    raw: dict[str, Any] = Field(default_factory=dict, description="Raw provider response")

    class Config:
        """Pydantic configuration."""

        extra = "allow"


class Result(BaseModel):
    """Operation result with status and details."""

    status: ResultStatus = Field(description="Operation result status")
    message: str | None = Field(default=None, description="Result message")
    resource_id: str | None = Field(default=None, description="Created/modified resource ID")
    resource_url: str | None = Field(default=None, description="Resource URL")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")

    @property
    def success(self) -> bool:
        """Check if operation was successful."""
        return self.status in (ResultStatus.SUCCESS, ResultStatus.NO_CHANGE)

    class Config:
        """Pydantic configuration."""

        extra = "allow"


class SLAStatus(BaseModel):
    """SLA status for an incident."""

    name: str = Field(description="SLA name")
    target: datetime | None = Field(default=None, description="SLA target time")
    elapsed: int | None = Field(default=None, description="Elapsed time in seconds")
    remaining: int | None = Field(default=None, description="Remaining time in seconds")
    breached: bool = Field(default=False, description="Whether SLA is breached")
    paused: bool = Field(default=False, description="Whether SLA is paused")

    class Config:
        """Pydantic configuration."""

        extra = "allow"