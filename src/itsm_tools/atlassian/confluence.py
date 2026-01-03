"""Confluence adapter implementing the WikiProvider interface.

This module provides a Confluence implementation of the WikiProvider interface,
enabling provider-agnostic wiki/documentation operations.

Example:
    from itsm_tools.atlassian import ConfluenceAdapter

    # Using context manager
    with ConfluenceAdapter(space="DEVOPS") as confluence:
        page = confluence.get_page_by_path("DEVOPS", "Runbooks/Deploy Guide")
        confluence.append_to_page(page.id, "<h2>New Section</h2><p>Content</p>")

    # Or via registry
    from itsm_tools import get_wiki_provider
    confluence = get_wiki_provider("atlassian_confluence", {"space": "DEVOPS"})
"""

import logging
from datetime import datetime
from typing import Any

from itsm_tools.atlassian.base import AtlassianClient
from itsm_tools.core.exceptions import NotFoundError, ProviderError, ValidationError
from itsm_tools.core.interfaces import WikiProvider
from itsm_tools.core.models import Page
from itsm_tools.core.registry import register_adapter

logger = logging.getLogger(__name__)

# Confluence REST API paths
CONFLUENCE_API_V2 = "/wiki/api/v2"
CONFLUENCE_API_V1 = "/wiki/rest/api"


@register_adapter("atlassian_confluence", WikiProvider)  # type: ignore[type-abstract]
class ConfluenceAdapter(AtlassianClient, WikiProvider):  # type: ignore[misc]
    """Confluence implementation of the WikiProvider interface.

    Provides wiki operations using the Confluence REST API.

    Attributes:
        space: Default space key for creating pages
        provider_name: Provider identifier for logging and errors
    """

    provider_name = "atlassian_confluence"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        space: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Confluence adapter.

        Args:
            config: Configuration dictionary (for registry compatibility)
            space: Default space key for creating pages
            **kwargs: Additional arguments passed to AtlassianClient
        """
        # Extract config values if provided via registry
        if config:
            space = config.get("space", space)
            kwargs.update({k: v for k, v in config.items() if k != "space"})

        super().__init__(**kwargs)
        self.space = space
        self._connected = False

    def connect(self) -> None:
        """Establish connection to Confluence (validates credentials)."""
        if not self._connected:
            # Test connection by fetching spaces
            self._get(f"{CONFLUENCE_API_V2}/spaces", params={"limit": 1})
            self._connected = True
            logger.info("Connected to Confluence at %s", self.base_url)

    def disconnect(self) -> None:
        """Close connection to Confluence."""
        self.close()
        self._connected = False
        logger.info("Disconnected from Confluence")

    def get_page(self, page_id: str) -> Page | None:
        """Get a page by its ID.

        Args:
            page_id: Confluence page ID

        Returns:
            Page object or None if not found
        """
        try:
            data = self._get(
                f"{CONFLUENCE_API_V2}/pages/{page_id}",
                params={"body-format": "storage"},
            )
            return self._parse_page(data)
        except NotFoundError:
            logger.debug("Page %s not found", page_id)
            return None

    def get_page_by_path(self, space: str, path: str) -> Page | None:
        """Get a page by its title within a space.

        Args:
            space: Space key
            path: Page title (exact match)

        Returns:
            Page object or None if not found
        """
        # Search for page by title in space
        try:
            data = self._get(
                f"{CONFLUENCE_API_V2}/spaces/{space}/pages",
                params={"title": path, "body-format": "storage"},
            )
            results = data.get("results", [])
            if results:
                return self._parse_page(results[0])
            return None
        except NotFoundError:
            logger.debug("Page '%s' not found in space %s", path, space)
            return None

    def create_page(
        self,
        title: str,
        content: str,
        space: str | None = None,
        parent_id: str | None = None,
        **kwargs: Any,
    ) -> Page:
        """Create a new Confluence page.

        Args:
            title: Page title
            content: Page content (HTML/storage format)
            space: Space key (uses default if not specified)
            parent_id: Parent page ID for hierarchy
            **kwargs: Additional fields (labels, etc.)

        Returns:
            Created Page object

        Raises:
            ValidationError: If required fields are missing
            ProviderError: If creation fails
        """
        space = space or self.space
        if not space:
            raise ValidationError(
                "Space key is required. Set default space or provide explicitly.",
                field="space",
                provider=self.provider_name,
            )

        # Build page payload
        payload: dict[str, Any] = {
            "spaceId": self._get_space_id(space),
            "status": "current",
            "title": title,
            "body": {
                "representation": "storage",
                "value": content,
            },
        }

        # Add parent if specified
        if parent_id:
            payload["parentId"] = parent_id

        logger.debug("Creating page in %s: %s", space, title)

        data = self._post(f"{CONFLUENCE_API_V2}/pages", json=payload)
        page_id = data.get("id", "")

        logger.info("Created page %s: %s", page_id, title)

        # Add labels if specified
        if kwargs.get("labels"):
            self._add_labels(page_id, kwargs["labels"])

        # Fetch the full page to return complete data
        return self.get_page(page_id) or Page(
            id=page_id,
            title=title,
            content=content,
            space=space,
            provider=self.provider_name,
        )

    def update_page(
        self,
        page_id: str,
        content: str,
        title: str | None = None,
    ) -> Page:
        """Update an existing page.

        Args:
            page_id: Page ID
            content: New page content (HTML/storage format)
            title: New title (optional, keeps existing if not specified)

        Returns:
            Updated Page object
        """
        # Get current page to get version and title
        current = self.get_page(page_id)
        if not current:
            raise NotFoundError(
                f"Page {page_id} not found",
                resource_type="page",
                resource_id=page_id,
                provider=self.provider_name,
            )

        # Build update payload
        payload: dict[str, Any] = {
            "id": page_id,
            "status": "current",
            "title": title or current.title,
            "body": {
                "representation": "storage",
                "value": content,
            },
            "version": {
                "number": current.version + 1,
            },
        }

        logger.debug(
            "Updating page %s (version %d -> %d)", page_id, current.version, current.version + 1
        )

        self._put(f"{CONFLUENCE_API_V2}/pages/{page_id}", json=payload)

        logger.info("Updated page %s", page_id)

        # Fetch updated page
        updated = self.get_page(page_id)
        if not updated:
            raise ProviderError(
                f"Failed to retrieve updated page {page_id}",
                provider=self.provider_name,
            )
        return updated

    def append_to_page(self, page_id: str, content: str) -> Page:
        """Append content to an existing page.

        Args:
            page_id: Page ID
            content: Content to append (HTML/storage format)

        Returns:
            Updated Page object
        """
        # Get current page content
        current = self.get_page(page_id)
        if not current:
            raise NotFoundError(
                f"Page {page_id} not found",
                resource_type="page",
                resource_id=page_id,
                provider=self.provider_name,
            )

        # Append new content
        existing_content = current.content or ""
        new_content = existing_content + content

        return self.update_page(page_id, new_content)

    def search(
        self,
        query: str,
        space: str | None = None,
        limit: int = 25,
    ) -> list[Page]:
        """Search for pages using CQL.

        Args:
            query: Search query (text or CQL)
            space: Limit search to specific space
            limit: Maximum number of results

        Returns:
            List of matching Page objects

        Example:
            # Text search
            pages = confluence.search("deployment guide")

            # CQL search
            pages = confluence.search("type=page AND label=runbook")
        """
        # Build CQL query
        cql_parts = []

        # Check if query is already CQL (contains operators)
        cql_operators = ["=", "~", "AND", "OR", "NOT", "ORDER BY"]
        is_cql = any(op in query for op in cql_operators)

        if is_cql:
            cql_parts.append(query)
        else:
            # Text search
            cql_parts.append(f'text ~ "{query}"')

        if space:
            cql_parts.append(f'space = "{space}"')

        cql = " AND ".join(cql_parts)

        logger.debug("Searching Confluence: %s", cql)

        # Use v1 API for CQL search (v2 doesn't support CQL well)
        data = self._get(
            f"{CONFLUENCE_API_V1}/content/search",
            params={
                "cql": cql,
                "limit": min(limit, 100),
                "expand": "space,version,body.storage",
            },
        )

        pages = []
        for result in data.get("results", []):
            pages.append(self._parse_page_v1(result))

        logger.debug("Found %d pages", len(pages))
        return pages

    def get_page_children(self, page_id: str) -> list[Page]:
        """Get child pages of a page.

        Args:
            page_id: Parent page ID

        Returns:
            List of child Page objects
        """
        data = self._get(
            f"{CONFLUENCE_API_V2}/pages/{page_id}/children",
            params={"body-format": "storage"},
        )

        pages = []
        for result in data.get("results", []):
            pages.append(self._parse_page(result))

        return pages

    def get_space(self, space_key: str) -> dict[str, Any]:
        """Get space details.

        Args:
            space_key: Space key

        Returns:
            Space details dictionary
        """
        data = self._get(
            f"{CONFLUENCE_API_V2}/spaces",
            params={"keys": space_key},
        )
        results = data.get("results", [])
        if not results:
            raise NotFoundError(
                f"Space {space_key} not found",
                resource_type="space",
                resource_id=space_key,
                provider=self.provider_name,
            )
        return dict(results[0])

    def delete_page(self, page_id: str) -> None:
        """Delete a page.

        Args:
            page_id: Page ID to delete
        """
        self._delete(f"{CONFLUENCE_API_V2}/pages/{page_id}")
        logger.info("Deleted page %s", page_id)

    def _get_space_id(self, space_key: str) -> str:
        """Get space ID from space key.

        Args:
            space_key: Space key

        Returns:
            Space ID
        """
        space = self.get_space(space_key)
        return str(space.get("id", ""))

    def _add_labels(self, page_id: str, labels: list[str]) -> None:
        """Add labels to a page.

        Args:
            page_id: Page ID
            labels: Labels to add
        """
        for label in labels:
            self._post(
                f"{CONFLUENCE_API_V2}/pages/{page_id}/labels",
                json={"name": label},
            )
        logger.debug("Added labels %s to page %s", labels, page_id)

    def _parse_page(self, data: dict[str, Any]) -> Page:
        """Parse Confluence API v2 response into Page model.

        Args:
            data: Raw Confluence page response

        Returns:
            Page model instance
        """
        # Parse timestamps
        created_at = None
        updated_at = None
        if data.get("createdAt"):
            created_at = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
        if data.get("version", {}).get("createdAt"):
            updated_at = datetime.fromisoformat(data["version"]["createdAt"].replace("Z", "+00:00"))

        # Get content
        content = None
        if data.get("body", {}).get("storage", {}).get("value"):
            content = data["body"]["storage"]["value"]

        # Get space key
        space = None
        if data.get("spaceId"):
            # V2 API returns spaceId, we'd need another call for key
            # For now, store the ID
            space = str(data.get("spaceId", ""))

        # Get author
        author = None
        if data.get("version", {}).get("authorId"):
            author = data["version"]["authorId"]

        return Page(
            id=str(data.get("id", "")),
            title=data.get("title", ""),
            content=content,
            space=space,
            version=data.get("version", {}).get("number", 1),
            author=author,
            created_at=created_at,
            updated_at=updated_at,
            url=f"{self.base_url}/wiki{data.get('_links', {}).get('webui', '')}",
            parent_id=str(data.get("parentId", "")) if data.get("parentId") else None,
            provider=self.provider_name,
            raw=data,
        )

    def _parse_page_v1(self, data: dict[str, Any]) -> Page:
        """Parse Confluence API v1 response into Page model.

        Args:
            data: Raw Confluence page response (v1 format)

        Returns:
            Page model instance
        """
        # Parse timestamps
        created_at = None
        updated_at = None
        if data.get("history", {}).get("createdDate"):
            created_at = datetime.fromisoformat(
                data["history"]["createdDate"].replace("Z", "+00:00")
            )
        if data.get("version", {}).get("when"):
            updated_at = datetime.fromisoformat(data["version"]["when"].replace("Z", "+00:00"))

        # Get content
        content = None
        if data.get("body", {}).get("storage", {}).get("value"):
            content = data["body"]["storage"]["value"]

        # Get space key
        space = data.get("space", {}).get("key")

        # Get author
        author = None
        if data.get("version", {}).get("by", {}).get("email"):
            author = data["version"]["by"]["email"]
        elif data.get("version", {}).get("by", {}).get("displayName"):
            author = data["version"]["by"]["displayName"]

        return Page(
            id=str(data.get("id", "")),
            title=data.get("title", ""),
            content=content,
            space=space,
            version=data.get("version", {}).get("number", 1),
            author=author,
            created_at=created_at,
            updated_at=updated_at,
            url=f"{self.base_url}/wiki{data.get('_links', {}).get('webui', '')}",
            parent_id=None,  # V1 API doesn't include parent directly
            provider=self.provider_name,
            raw=data,
        )
