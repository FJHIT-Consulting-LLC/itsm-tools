"""Command-line interface for itsm-tools.

This module provides the CLI entry point for itsm-tools.
Full implementation in ITI-226.

Usage:
    itsm issue get ITI-220
    itsm issue search 'status = "To Do"'
    itsm incident create --summary "Alert" --severity medium
    itsm wiki get 83820565
    itsm config show
"""

import sys


def main() -> int:
    """Main CLI entry point."""
    print("itsm-tools CLI")
    print("Version: 0.1.0")
    print()
    print("CLI will be fully implemented in ITI-226.")
    print("For now, use the Python API directly:")
    print()
    print("  from itsm_tools import get_issue_tracker")
    print("  tracker = get_issue_tracker('atlassian_jira', config)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
