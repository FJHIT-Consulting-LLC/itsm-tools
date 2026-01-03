"""Command-line interface for itsm-tools.

This module provides a unified CLI for ITSM operations across providers.

Usage:
    # Issue tracking
    itsm issue get ITI-220
    itsm issue create --summary "New feature" --type Story
    itsm issue search 'status = "To Do"'
    itsm issue transition ITI-220 --to "In Progress"
    itsm issue comment ITI-220 "Work started"

    # Wiki/documentation
    itsm wiki get 83820565
    itsm wiki search "deployment guide"
    itsm wiki create --title "New Page" --space DEVOPS --body "<p>Content</p>"

    # Incident management
    itsm incident get SD-100
    itsm incident create --summary "Service down" --severity high
    itsm incident resolve SD-100 --resolution "Fixed root cause"

    # Configuration
    itsm config show
    itsm config set --provider atlassian_jira
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from itsm_tools.core.models import Severity


def get_provider_config() -> dict[str, Any]:
    """Get provider configuration from environment/keyring."""
    # The adapters handle credential resolution internally
    return {}


# =============================================================================
# Issue Commands
# =============================================================================


def cmd_issue_get(args: argparse.Namespace) -> int:
    """Get issue details."""
    from itsm_tools.atlassian import JiraAdapter

    with JiraAdapter() as jira:
        issue = jira.get_issue(args.issue_key)

        if not issue:
            print(f"Issue {args.issue_key} not found", file=sys.stderr)
            return 1

        print(f"Key:         {issue.key}")
        print(f"Summary:     {issue.summary}")
        print(f"Type:        {issue.issue_type}")
        print(f"Status:      {issue.status}")
        print(f"Assignee:    {issue.assignee or 'Unassigned'}")
        print(f"Reporter:    {issue.reporter or 'Unknown'}")
        print(f"Priority:    {issue.priority or 'None'}")
        print(f"Labels:      {', '.join(issue.labels) if issue.labels else 'None'}")
        print(f"Created:     {issue.created_at}")
        print(f"Updated:     {issue.updated_at}")
        if issue.parent_key:
            print(f"Parent:      {issue.parent_key}")
        if issue.url:
            print(f"URL:         {issue.url}")

        if args.json:
            print("\nRaw JSON:")
            print(json.dumps(issue.raw, indent=2, default=str))

    return 0


def cmd_issue_create(args: argparse.Namespace) -> int:
    """Create a new issue."""
    from itsm_tools.atlassian import JiraAdapter

    labels = args.labels.split(",") if args.labels else None

    with JiraAdapter(project=args.project) as jira:
        issue = jira.create_issue(
            summary=args.summary,
            description=args.description,
            issue_type=args.type,
            labels=labels,
            parent_key=args.parent,
        )

        print(f"Created {issue.key}: {issue.summary}")
        if issue.url:
            print(f"URL: {issue.url}")

    return 0


def cmd_issue_search(args: argparse.Namespace) -> int:
    """Search for issues."""
    from itsm_tools.atlassian import JiraAdapter

    with JiraAdapter() as jira:
        issues = jira.search(args.query, max_results=args.limit)

        if not issues:
            print("No issues found")
            return 0

        print(f"Found {len(issues)} issue(s):\n")
        for issue in issues:
            print(f"  {issue.key}: {issue.summary}")
            print(f"    Status: {issue.status} | Type: {issue.issue_type}")

    return 0


def cmd_issue_transition(args: argparse.Namespace) -> int:
    """Transition an issue to a new status."""
    from itsm_tools.atlassian import JiraAdapter

    with JiraAdapter() as jira:
        result = jira.transition(args.issue_key, args.to)

        if result.success:
            print(f"Transitioned {args.issue_key} to '{args.to}'")
            return 0
        else:
            print(f"Failed: {result.message}", file=sys.stderr)
            return 1


def cmd_issue_comment(args: argparse.Namespace) -> int:
    """Add a comment to an issue."""
    from itsm_tools.atlassian import JiraAdapter

    with JiraAdapter() as jira:
        result = jira.comment(args.issue_key, args.body)

        if result.success:
            print(f"Added comment to {args.issue_key}")
            return 0
        else:
            print(f"Failed: {result.message}", file=sys.stderr)
            return 1


def cmd_issue_link(args: argparse.Namespace) -> int:
    """Link two issues together."""
    from itsm_tools.atlassian import JiraAdapter

    with JiraAdapter() as jira:
        result = jira.link_issues(args.source, args.target, args.link_type)

        if result.success:
            print(f"Linked {args.source} -> {args.target} ({args.link_type})")
            return 0
        else:
            print(f"Failed: {result.message}", file=sys.stderr)
            return 1


# =============================================================================
# Wiki Commands
# =============================================================================


def cmd_wiki_get(args: argparse.Namespace) -> int:
    """Get wiki page details."""
    from itsm_tools.atlassian import ConfluenceAdapter

    with ConfluenceAdapter() as wiki:
        page = wiki.get_page(args.page_id)

        if not page:
            print(f"Page {args.page_id} not found", file=sys.stderr)
            return 1

        print(f"ID:          {page.id}")
        print(f"Title:       {page.title}")
        print(f"Space:       {page.space}")
        print(f"Version:     {page.version}")
        print(f"Author:      {page.author or 'Unknown'}")
        print(f"Updated:     {page.updated_at}")
        if page.parent_id:
            print(f"Parent:      {page.parent_id}")
        if page.url:
            print(f"URL:         {page.url}")

        if args.body and page.content:
            print(f"\nContent:\n{page.content}")

    return 0


def cmd_wiki_search(args: argparse.Namespace) -> int:
    """Search for wiki pages."""
    from itsm_tools.atlassian import ConfluenceAdapter

    with ConfluenceAdapter() as wiki:
        pages = wiki.search(args.query, space=args.space, limit=args.limit)

        if not pages:
            print("No pages found")
            return 0

        print(f"Found {len(pages)} page(s):\n")
        for page in pages:
            print(f"  [{page.id}] {page.title}")
            if page.space:
                print(f"    Space: {page.space}")

    return 0


def cmd_wiki_create(args: argparse.Namespace) -> int:
    """Create a new wiki page."""
    from itsm_tools.atlassian import ConfluenceAdapter

    # Read body from file if specified
    body = args.body or ""
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()

    with ConfluenceAdapter(space=args.space) as wiki:
        page = wiki.create_page(
            title=args.title,
            content=body,
            parent_id=args.parent,
        )

        print(f"Created page: {page.title}")
        print(f"ID: {page.id}")
        if page.url:
            print(f"URL: {page.url}")

    return 0


def cmd_wiki_update(args: argparse.Namespace) -> int:
    """Update a wiki page."""
    from itsm_tools.atlassian import ConfluenceAdapter

    # Read body from file if specified
    body = args.body
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()

    if not body:
        print("Body is required (--body or --body-file)", file=sys.stderr)
        return 1

    with ConfluenceAdapter() as wiki:
        page = wiki.update_page(args.page_id, body, title=args.title)

        print(f"Updated page: {page.title}")
        print(f"Version: {page.version}")

    return 0


def cmd_wiki_append(args: argparse.Namespace) -> int:
    """Append content to a wiki page."""
    from itsm_tools.atlassian import ConfluenceAdapter

    # Read content from file if specified
    content = args.content
    if args.content_file:
        with open(args.content_file, encoding="utf-8") as f:
            content = f.read()

    if not content:
        print("Content is required (--content or --content-file)", file=sys.stderr)
        return 1

    with ConfluenceAdapter() as wiki:
        page = wiki.append_to_page(args.page_id, content)

        print(f"Appended to page: {page.title}")
        print(f"Version: {page.version}")

    return 0


# =============================================================================
# Incident Commands
# =============================================================================


def cmd_incident_get(args: argparse.Namespace) -> int:
    """Get incident details."""
    from itsm_tools.atlassian import JSMAdapter

    with JSMAdapter() as jsm:
        incident = jsm.get_incident(args.incident_key)

        if not incident:
            print(f"Incident {args.incident_key} not found", file=sys.stderr)
            return 1

        print(f"Key:         {incident.key}")
        print(f"Summary:     {incident.summary}")
        print(f"Severity:    {incident.severity.value}")
        print(f"Status:      {incident.status}")
        print(f"Service:     {incident.service or 'None'}")
        print(f"Assignee:    {incident.assignee or 'Unassigned'}")
        print(f"Reporter:    {incident.reporter or 'Unknown'}")
        print(f"Labels:      {', '.join(incident.labels) if incident.labels else 'None'}")
        print(f"Created:     {incident.created_at}")
        print(f"Updated:     {incident.updated_at}")
        if incident.resolved_at:
            print(f"Resolved:    {incident.resolved_at}")
        if incident.resolution:
            print(f"Resolution:  {incident.resolution}")
        if incident.linked_issues:
            print(f"Linked:      {', '.join(incident.linked_issues)}")
        if incident.url:
            print(f"URL:         {incident.url}")

        # Show SLA status
        if args.sla:
            sla_statuses = jsm.get_sla_status(incident.key)
            if sla_statuses:
                print("\nSLA Status:")
                for sla in sla_statuses:
                    status = "BREACHED" if sla.breached else "OK"
                    if sla.paused:
                        status = "PAUSED"
                    remaining = f"{sla.remaining}s" if sla.remaining else "N/A"
                    print(f"  {sla.name}: {status} (remaining: {remaining})")

    return 0


def cmd_incident_create(args: argparse.Namespace) -> int:
    """Create a new incident."""
    from itsm_tools.atlassian import JSMAdapter

    severity = Severity(args.severity)
    labels = args.labels.split(",") if args.labels else None

    with JSMAdapter(service_desk=args.service_desk) as jsm:
        incident = jsm.create_incident(
            summary=args.summary,
            description=args.description,
            severity=severity,
            service=args.service,
            labels=labels,
        )

        print(f"Created incident: {incident.key}")
        print(f"Summary: {incident.summary}")
        print(f"Severity: {incident.severity.value}")
        if incident.url:
            print(f"URL: {incident.url}")

    return 0


def cmd_incident_search(args: argparse.Namespace) -> int:
    """Search for incidents."""
    from itsm_tools.atlassian import JSMAdapter

    severity = Severity(args.severity) if args.severity else None

    with JSMAdapter(service_desk=args.service_desk) as jsm:
        incidents = jsm.search_incidents(
            query=args.query,
            status=args.status,
            severity=severity,
            limit=args.limit,
        )

        if not incidents:
            print("No incidents found")
            return 0

        print(f"Found {len(incidents)} incident(s):\n")
        for incident in incidents:
            print(f"  {incident.key}: {incident.summary}")
            print(f"    Severity: {incident.severity.value} | Status: {incident.status}")

    return 0


def cmd_incident_resolve(args: argparse.Namespace) -> int:
    """Resolve an incident."""
    from itsm_tools.atlassian import JSMAdapter

    with JSMAdapter() as jsm:
        result = jsm.resolve_incident(args.incident_key, args.resolution)

        if result.success:
            print(f"Resolved {args.incident_key}")
            return 0
        else:
            print(f"Failed: {result.message}", file=sys.stderr)
            return 1


def cmd_incident_escalate(args: argparse.Namespace) -> int:
    """Escalate an incident to higher severity."""
    from itsm_tools.atlassian import JSMAdapter

    severity = Severity(args.severity)

    with JSMAdapter() as jsm:
        result = jsm.escalate_incident(args.incident_key, severity, args.reason)

        if result.success:
            print(f"Escalated {args.incident_key} to {severity.value}")
            return 0
        else:
            print(f"Failed: {result.message}", file=sys.stderr)
            return 1


def cmd_incident_comment(args: argparse.Namespace) -> int:
    """Add a comment to an incident."""
    from itsm_tools.atlassian import JSMAdapter

    with JSMAdapter() as jsm:
        result = jsm.add_comment(args.incident_key, args.body, internal=args.internal)

        if result.success:
            comment_type = "internal" if args.internal else "public"
            print(f"Added {comment_type} comment to {args.incident_key}")
            return 0
        else:
            print(f"Failed: {result.message}", file=sys.stderr)
            return 1


# =============================================================================
# Config Commands
# =============================================================================


def cmd_config_show(args: argparse.Namespace) -> int:
    """Show current configuration."""
    import os

    from itsm_tools.atlassian.credentials import get_credentials

    print("ITSM Tools Configuration")
    print("=" * 40)

    # Check environment variables
    base_url = os.environ.get("JIRA_BASE_URL")
    email = os.environ.get("JIRA_USER_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")

    if base_url:
        print(f"\nAtlassian (from environment):")
        print(f"  URL:   {base_url}")
        print(f"  Email: {email or '(not set)'}")
        print(f"  Token: {'****' + token[-4:] if token and len(token) > 4 else '(not set)'}")
    else:
        # Try to get from keyring
        try:
            creds = get_credentials()
            print(f"\nAtlassian (from keyring):")
            print(f"  URL:   {creds.base_url}")
            print(f"  Email: {creds.email}")
            print(f"  Token: ****{creds.api_token[-4:]}")
        except ValueError:
            print("\nAtlassian: Not configured")
            print("  Set environment variables or use: itsm config setup")

    return 0


def cmd_config_setup(args: argparse.Namespace) -> int:
    """Interactive credential setup."""
    import getpass

    from itsm_tools.atlassian.credentials import save_credentials

    print("ITSM Tools - Atlassian Configuration")
    print("=" * 40)
    print("\nYou'll need an API token from:")
    print("https://id.atlassian.com/manage-profile/security/api-tokens\n")

    base_url = input("Atlassian URL (e.g., https://yoursite.atlassian.net): ").strip()
    if not base_url:
        print("URL is required", file=sys.stderr)
        return 1

    email = input("Your Atlassian email: ").strip()
    if not email:
        print("Email is required", file=sys.stderr)
        return 1

    api_token = getpass.getpass("API token (hidden): ").strip()
    if not api_token:
        print("API token is required", file=sys.stderr)
        return 1

    # Test credentials
    print("\nTesting credentials...")
    try:
        from itsm_tools.atlassian import JiraAdapter

        adapter = JiraAdapter(
            base_url=base_url,
            email=email,
            api_token=api_token,
        )
        adapter.test_connection()
        print("Connection successful!")
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        return 1

    # Save credentials
    save_credentials(base_url, email, api_token)
    print("\nCredentials saved to system keyring.")

    return 0


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="itsm",
        description="Provider-agnostic ITSM tools CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  itsm issue get ITI-220
  itsm issue create --project ITI --type Story --summary "New feature"
  itsm issue transition ITI-220 --to done

  itsm wiki get 83820565
  itsm wiki search "deployment guide" --space DEVOPS

  itsm incident create --summary "Service down" --severity high
  itsm incident resolve SD-100 --resolution "Fixed"

  itsm config show
  itsm config setup
        """,
    )
    parser.add_argument("--version", action="version", version="itsm-tools 0.1.0")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # =========================================================================
    # Issue subcommands
    # =========================================================================
    issue_parser = subparsers.add_parser("issue", help="Issue tracking commands")
    issue_sub = issue_parser.add_subparsers(dest="issue_command", required=True)

    # issue get
    issue_get = issue_sub.add_parser("get", help="Get issue details")
    issue_get.add_argument("issue_key", help="Issue key (e.g., ITI-220)")
    issue_get.add_argument("--json", action="store_true", help="Include raw JSON")

    # issue create
    issue_create = issue_sub.add_parser("create", help="Create a new issue")
    issue_create.add_argument("--project", required=True, help="Project key")
    issue_create.add_argument("--type", default="Task", help="Issue type (default: Task)")
    issue_create.add_argument("--summary", required=True, help="Issue summary")
    issue_create.add_argument("--description", help="Issue description")
    issue_create.add_argument("--labels", help="Comma-separated labels")
    issue_create.add_argument("--parent", help="Parent issue key (for subtasks)")

    # issue search
    issue_search = issue_sub.add_parser("search", help="Search for issues")
    issue_search.add_argument("query", help="JQL query")
    issue_search.add_argument("--limit", type=int, default=25, help="Max results")

    # issue transition
    issue_trans = issue_sub.add_parser("transition", help="Transition an issue")
    issue_trans.add_argument("issue_key", help="Issue key")
    issue_trans.add_argument("--to", required=True, help="Target status")

    # issue comment
    issue_comment = issue_sub.add_parser("comment", help="Add a comment")
    issue_comment.add_argument("issue_key", help="Issue key")
    issue_comment.add_argument("body", help="Comment text")

    # issue link
    issue_link = issue_sub.add_parser("link", help="Link two issues")
    issue_link.add_argument("source", help="Source issue key")
    issue_link.add_argument("target", help="Target issue key")
    issue_link.add_argument("--link-type", default="Relates", help="Link type")

    # =========================================================================
    # Wiki subcommands
    # =========================================================================
    wiki_parser = subparsers.add_parser("wiki", help="Wiki/documentation commands")
    wiki_sub = wiki_parser.add_subparsers(dest="wiki_command", required=True)

    # wiki get
    wiki_get = wiki_sub.add_parser("get", help="Get page details")
    wiki_get.add_argument("page_id", help="Page ID")
    wiki_get.add_argument("--body", action="store_true", help="Include page body")

    # wiki search
    wiki_search = wiki_sub.add_parser("search", help="Search for pages")
    wiki_search.add_argument("query", help="Search query or CQL")
    wiki_search.add_argument("--space", help="Limit to space")
    wiki_search.add_argument("--limit", type=int, default=25, help="Max results")

    # wiki create
    wiki_create = wiki_sub.add_parser("create", help="Create a new page")
    wiki_create.add_argument("--space", required=True, help="Space key")
    wiki_create.add_argument("--title", required=True, help="Page title")
    wiki_create.add_argument("--body", help="Page body (HTML)")
    wiki_create.add_argument("--body-file", help="Read body from file")
    wiki_create.add_argument("--parent", help="Parent page ID")

    # wiki update
    wiki_update = wiki_sub.add_parser("update", help="Update a page")
    wiki_update.add_argument("page_id", help="Page ID")
    wiki_update.add_argument("--title", help="New title")
    wiki_update.add_argument("--body", help="New body (HTML)")
    wiki_update.add_argument("--body-file", help="Read body from file")

    # wiki append
    wiki_append = wiki_sub.add_parser("append", help="Append to a page")
    wiki_append.add_argument("page_id", help="Page ID")
    wiki_append.add_argument("--content", help="Content to append (HTML)")
    wiki_append.add_argument("--content-file", help="Read content from file")

    # =========================================================================
    # Incident subcommands
    # =========================================================================
    incident_parser = subparsers.add_parser("incident", help="Incident management commands")
    incident_sub = incident_parser.add_subparsers(dest="incident_command", required=True)

    # incident get
    incident_get = incident_sub.add_parser("get", help="Get incident details")
    incident_get.add_argument("incident_key", help="Incident key (e.g., SD-100)")
    incident_get.add_argument("--sla", action="store_true", help="Include SLA status")

    # incident create
    incident_create = incident_sub.add_parser("create", help="Create a new incident")
    incident_create.add_argument("--service-desk", help="Service desk key")
    incident_create.add_argument("--summary", required=True, help="Incident summary")
    incident_create.add_argument("--description", help="Incident description")
    incident_create.add_argument(
        "--severity",
        default="medium",
        choices=["critical", "high", "medium", "low", "info"],
        help="Severity level",
    )
    incident_create.add_argument("--service", help="Affected service")
    incident_create.add_argument("--labels", help="Comma-separated labels")

    # incident search
    incident_search = incident_sub.add_parser("search", help="Search for incidents")
    incident_search.add_argument("query", nargs="?", help="Search query")
    incident_search.add_argument("--service-desk", help="Service desk key")
    incident_search.add_argument("--status", help="Filter by status")
    incident_search.add_argument(
        "--severity",
        choices=["critical", "high", "medium", "low", "info"],
        help="Filter by severity",
    )
    incident_search.add_argument("--limit", type=int, default=25, help="Max results")

    # incident resolve
    incident_resolve = incident_sub.add_parser("resolve", help="Resolve an incident")
    incident_resolve.add_argument("incident_key", help="Incident key")
    incident_resolve.add_argument("--resolution", required=True, help="Resolution notes")

    # incident escalate
    incident_escalate = incident_sub.add_parser("escalate", help="Escalate an incident")
    incident_escalate.add_argument("incident_key", help="Incident key")
    incident_escalate.add_argument(
        "--severity",
        required=True,
        choices=["critical", "high", "medium", "low", "info"],
        help="New severity",
    )
    incident_escalate.add_argument("--reason", help="Escalation reason")

    # incident comment
    incident_comment = incident_sub.add_parser("comment", help="Add a comment")
    incident_comment.add_argument("incident_key", help="Incident key")
    incident_comment.add_argument("body", help="Comment text")
    incident_comment.add_argument("--internal", action="store_true", help="Internal comment")

    # =========================================================================
    # Config subcommands
    # =========================================================================
    config_parser = subparsers.add_parser("config", help="Configuration commands")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)

    # config show
    config_sub.add_parser("show", help="Show current configuration")

    # config setup
    config_sub.add_parser("setup", help="Interactive credential setup")

    # Parse and dispatch
    args = parser.parse_args()

    try:
        # Issue commands
        if args.command == "issue":
            commands = {
                "get": cmd_issue_get,
                "create": cmd_issue_create,
                "search": cmd_issue_search,
                "transition": cmd_issue_transition,
                "comment": cmd_issue_comment,
                "link": cmd_issue_link,
            }
            return commands[args.issue_command](args)

        # Wiki commands
        if args.command == "wiki":
            commands = {
                "get": cmd_wiki_get,
                "search": cmd_wiki_search,
                "create": cmd_wiki_create,
                "update": cmd_wiki_update,
                "append": cmd_wiki_append,
            }
            return commands[args.wiki_command](args)

        # Incident commands
        if args.command == "incident":
            commands = {
                "get": cmd_incident_get,
                "create": cmd_incident_create,
                "search": cmd_incident_search,
                "resolve": cmd_incident_resolve,
                "escalate": cmd_incident_escalate,
                "comment": cmd_incident_comment,
            }
            return commands[args.incident_command](args)

        # Config commands
        if args.command == "config":
            commands = {
                "show": cmd_config_show,
                "setup": cmd_config_setup,
            }
            return commands[args.config_command](args)

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
