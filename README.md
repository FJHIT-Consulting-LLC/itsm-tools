# itsm-tools

Provider-agnostic ITSM integration library for Python.

[![CI](https://github.com/FJHIT-Consulting-LLC/itsm-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/FJHIT-Consulting-LLC/itsm-tools/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

`itsm-tools` provides a unified interface for ITSM operations across multiple providers:

| Interface | Purpose | Providers |
|-----------|---------|-----------|
| **IssueTracker** | Issue/ticket management | Jira, GitHub Issues, Azure DevOps |
| **WikiProvider** | Documentation/wiki | Confluence, Notion, SharePoint |
| **IncidentManager** | Incident management | JSM, ServiceNow, PagerDuty |

The adapter pattern allows you to write provider-agnostic code and switch backends via configuration.

## Installation

```bash
# Install from GitHub
pip install git+https://github.com/FJHIT-Consulting-LLC/itsm-tools.git

# Install with development dependencies
pip install "git+https://github.com/FJHIT-Consulting-LLC/itsm-tools.git#egg=itsm-tools[dev]"
```

## Quick Start

### Issue Tracking

```python
from itsm_tools import get_issue_tracker

# Get configured adapter (provider from env or config)
with get_issue_tracker() as tracker:
    # Create an issue
    issue = tracker.create_issue(
        summary="New feature request",
        description="Implement dark mode",
        issue_type="Story",
        labels=["enhancement", "ui"]
    )
    print(f"Created: {issue.key}")

    # Search for issues
    issues = tracker.search('project = ITI AND status = "To Do"')
    for issue in issues:
        print(f"{issue.key}: {issue.summary}")

    # Transition an issue
    tracker.transition(issue, "In Progress")
```

### Wiki/Documentation

```python
from itsm_tools import get_wiki_provider

with get_wiki_provider() as wiki:
    # Get a page
    page = wiki.get_page("83820565")
    print(f"Title: {page.title}")

    # Append content to a page
    wiki.append_to_page(
        page_id="83820565",
        content="<h2>New Section</h2><p>Auto-generated content</p>"
    )

    # Create a new page
    new_page = wiki.create_page(
        title="API Documentation",
        content="<h1>API Docs</h1>",
        space="DEVOPS"
    )
```

### Incident Management

```python
from itsm_tools import get_incident_manager, Severity

with get_incident_manager() as incidents:
    # Create an incident
    incident = incidents.create_incident(
        summary="Database connection failures",
        description="Production DB showing intermittent connection errors",
        severity=Severity.HIGH,
        service="Production Database",
        labels=["database", "production"]
    )
    print(f"Created incident: {incident.key}")

    # Link to a related issue
    incidents.link_to_issue(incident, "ITI-220")

    # Resolve when fixed
    incidents.resolve_incident(
        incident,
        resolution="Increased connection pool size"
    )
```

## Configuration

### Environment Variables

```bash
# Atlassian credentials
export JIRA_BASE_URL="https://yourcompany.atlassian.net"
export JIRA_USER_EMAIL="you@example.com"
export JIRA_API_TOKEN="your-api-token"

# Default providers
export ITSM_ISSUE_TRACKER_PROVIDER="atlassian_jira"
export ITSM_WIKI_PROVIDER="atlassian_confluence"
export ITSM_INCIDENTS_PROVIDER="atlassian_jsm"
```

### Explicit Configuration

```python
from itsm_tools import get_issue_tracker

config = {
    "base_url": "https://yourcompany.atlassian.net",
    "email": "you@example.com",
    "api_token": "your-token",
    "project": "ITI",
}

tracker = get_issue_tracker("atlassian_jira", config)
```

### Credential Storage

Credentials can be stored securely using the system keyring:

```python
# Credentials are automatically discovered from:
# 1. Environment variables
# 2. System keyring (via `keyring` library)
# 3. .env file in project root
```

## Available Adapters

### Atlassian (Implemented)

| Adapter | Interface | Description |
|---------|-----------|-------------|
| `atlassian_jira` | IssueTracker | Jira Cloud REST API |
| `atlassian_confluence` | WikiProvider | Confluence Cloud REST API |
| `atlassian_jsm` | IncidentManager | Jira Service Management |

### ServiceNow (Planned)

| Adapter | Interface | Description |
|---------|-----------|-------------|
| `servicenow` | IncidentManager | ServiceNow ITSM |
| `servicenow_change` | - | ServiceNow Change Management |
| `servicenow_cmdb` | - | ServiceNow CMDB |

### PagerDuty (Planned)

| Adapter | Interface | Description |
|---------|-----------|-------------|
| `pagerduty` | IncidentManager | PagerDuty Incidents |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Application                            │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Abstract Interfaces                          │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  IssueTracker   │   WikiProvider  │    IncidentManager          │
└────────┬────────┴────────┬────────┴──────────────┬──────────────┘
         │                 │                       │
    ┌────┴────┐       ┌────┴────┐            ┌─────┴─────┐
    ▼         ▼       ▼         ▼            ▼           ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌─────────┐ ┌─────────┐
│ Jira  │ │GitHub │ │Conflu-│ │Notion │ │   JSM   │ │ServiceNow│
│Adapter│ │Issues │ │ence   │ │       │ │ Adapter │ │ Adapter │
└───────┘ └───────┘ └───────┘ └───────┘ └─────────┘ └─────────┘
```

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/FJHIT-Consulting-LLC/itsm-tools.git
cd itsm-tools

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=itsm_tools --cov-report=html

# Run specific test file
pytest tests/core/test_models.py
```

### Code Quality

```bash
# Format code
black src tests

# Lint
pylint src/itsm_tools

# Type check
mypy src/itsm_tools

# Security scan
bandit -r src/itsm_tools
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Related Projects

- [cloud-infrastructure](https://github.com/FJHIT-Consulting-LLC/cloud-infrastructure) - Multi-cloud infrastructure automation using itsm-tools for incident management