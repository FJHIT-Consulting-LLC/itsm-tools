"""Tests for ConfluenceAdapter."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import responses

from itsm_tools.atlassian.confluence import ConfluenceAdapter
from itsm_tools.core.exceptions import NotFoundError, ValidationError


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
def confluence_adapter(mock_credentials: MagicMock) -> ConfluenceAdapter:
    """Create a ConfluenceAdapter instance for testing."""
    return ConfluenceAdapter(space="DEVOPS")


@pytest.fixture
def sample_confluence_page_v2() -> dict:
    """Sample Confluence API v2 page response."""
    return {
        "id": "123456",
        "title": "Test Page",
        "spaceId": "789",
        "status": "current",
        "createdAt": "2024-01-15T10:30:00.000Z",
        "version": {
            "number": 3,
            "createdAt": "2024-01-16T14:45:00.000Z",
            "authorId": "user123",
        },
        "body": {
            "storage": {
                "value": "<p>Test content</p>",
                "representation": "storage",
            }
        },
        "parentId": "111222",
        "_links": {
            "webui": "/spaces/DEVOPS/pages/123456/Test+Page",
        },
    }


@pytest.fixture
def sample_confluence_page_v1() -> dict:
    """Sample Confluence API v1 page response."""
    return {
        "id": "123456",
        "title": "Test Page",
        "space": {"key": "DEVOPS"},
        "version": {
            "number": 3,
            "when": "2024-01-16T14:45:00.000Z",
            "by": {
                "email": "author@example.com",
                "displayName": "Test Author",
            },
        },
        "body": {
            "storage": {
                "value": "<p>Test content</p>",
            }
        },
        "history": {
            "createdDate": "2024-01-15T10:30:00.000Z",
        },
        "_links": {
            "webui": "/spaces/DEVOPS/pages/123456/Test+Page",
        },
    }


@pytest.fixture
def sample_space() -> dict:
    """Sample Confluence space response."""
    return {
        "id": "789",
        "key": "DEVOPS",
        "name": "DevOps",
        "type": "global",
    }


class TestConfluenceAdapterInit:
    """Tests for ConfluenceAdapter initialization."""

    def test_init_with_space(self, mock_credentials: MagicMock) -> None:
        """Test initialization with space."""
        adapter = ConfluenceAdapter(space="DEVOPS")
        assert adapter.space == "DEVOPS"
        assert adapter.provider_name == "atlassian_confluence"

    def test_init_with_config(self, mock_credentials: MagicMock) -> None:
        """Test initialization with config dict (registry pattern)."""
        adapter = ConfluenceAdapter(config={"space": "TEST"})
        assert adapter.space == "TEST"

    def test_init_without_space(self, mock_credentials: MagicMock) -> None:
        """Test initialization without space."""
        adapter = ConfluenceAdapter()
        assert adapter.space is None


class TestConfluenceAdapterConnection:
    """Tests for connect/disconnect methods."""

    @responses.activate
    def test_connect(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test connection establishment."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/spaces",
            json={"results": []},
            status=200,
        )

        confluence_adapter.connect()
        assert confluence_adapter._connected is True

    def test_disconnect(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test disconnection."""
        confluence_adapter._connected = True
        confluence_adapter.disconnect()
        assert confluence_adapter._connected is False


class TestConfluenceAdapterGetPage:
    """Tests for get_page method."""

    @responses.activate
    def test_get_page_found(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v2: dict
    ) -> None:
        """Test getting an existing page."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            json=sample_confluence_page_v2,
            status=200,
        )

        page = confluence_adapter.get_page("123456")

        assert page is not None
        assert page.id == "123456"
        assert page.title == "Test Page"
        assert page.content == "<p>Test content</p>"
        assert page.version == 3
        assert page.parent_id == "111222"
        assert page.provider == "atlassian_confluence"

    @responses.activate
    def test_get_page_not_found(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test getting a non-existent page."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/999999",
            json={"errorMessages": ["Page does not exist"]},
            status=404,
        )

        page = confluence_adapter.get_page("999999")
        assert page is None


class TestConfluenceAdapterGetPageByPath:
    """Tests for get_page_by_path method."""

    @responses.activate
    def test_get_page_by_path_found(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v2: dict
    ) -> None:
        """Test getting page by title in space."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/spaces/DEVOPS/pages",
            json={"results": [sample_confluence_page_v2]},
            status=200,
        )

        page = confluence_adapter.get_page_by_path("DEVOPS", "Test Page")

        assert page is not None
        assert page.id == "123456"
        assert page.title == "Test Page"

    @responses.activate
    def test_get_page_by_path_not_found(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test getting page that doesn't exist."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/spaces/DEVOPS/pages",
            json={"results": []},
            status=200,
        )

        page = confluence_adapter.get_page_by_path("DEVOPS", "Nonexistent")
        assert page is None


class TestConfluenceAdapterCreatePage:
    """Tests for create_page method."""

    @responses.activate
    def test_create_page_success(
        self,
        confluence_adapter: ConfluenceAdapter,
        sample_confluence_page_v2: dict,
        sample_space: dict,
    ) -> None:
        """Test successful page creation."""
        # Mock get space
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/spaces",
            json={"results": [sample_space]},
            status=200,
        )
        # Mock create page
        responses.add(
            responses.POST,
            "https://test.atlassian.net/wiki/api/v2/pages",
            json={"id": "123456"},
            status=201,
        )
        # Mock get page for return value
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            json=sample_confluence_page_v2,
            status=200,
        )

        page = confluence_adapter.create_page(
            title="Test Page",
            content="<p>Test content</p>",
        )

        assert page.id == "123456"
        assert page.title == "Test Page"

    @responses.activate
    def test_create_page_with_parent(
        self,
        confluence_adapter: ConfluenceAdapter,
        sample_confluence_page_v2: dict,
        sample_space: dict,
    ) -> None:
        """Test creating a child page."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/spaces",
            json={"results": [sample_space]},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://test.atlassian.net/wiki/api/v2/pages",
            json={"id": "123457"},
            status=201,
        )
        sample_confluence_page_v2["id"] = "123457"
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/123457",
            json=sample_confluence_page_v2,
            status=200,
        )

        page = confluence_adapter.create_page(
            title="Child Page",
            content="<p>Child content</p>",
            parent_id="123456",
        )

        assert page.id == "123457"
        # Verify parent was included in request
        request_body = responses.calls[1].request.body
        assert b"parentId" in request_body

    def test_create_page_no_space(self, mock_credentials: MagicMock) -> None:
        """Test that create_page raises error without space."""
        adapter = ConfluenceAdapter()  # No default space

        with pytest.raises(ValidationError) as exc_info:
            adapter.create_page(title="Test", content="<p>Test</p>")

        assert "Space key is required" in str(exc_info.value)


class TestConfluenceAdapterUpdatePage:
    """Tests for update_page method."""

    @responses.activate
    def test_update_page(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v2: dict
    ) -> None:
        """Test updating a page."""
        # Mock get current page
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            json=sample_confluence_page_v2,
            status=200,
        )
        # Mock update
        responses.add(
            responses.PUT,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            json=sample_confluence_page_v2,
            status=200,
        )
        # Mock get updated page
        sample_confluence_page_v2["body"]["storage"]["value"] = "<p>Updated content</p>"
        sample_confluence_page_v2["version"]["number"] = 4
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            json=sample_confluence_page_v2,
            status=200,
        )

        page = confluence_adapter.update_page(
            "123456",
            "<p>Updated content</p>",
        )

        assert page.version == 4

    @responses.activate
    def test_update_page_not_found(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test updating non-existent page raises error."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/999999",
            json={"errorMessages": ["Page not found"]},
            status=404,
        )

        with pytest.raises(NotFoundError):
            confluence_adapter.update_page("999999", "<p>Content</p>")


class TestConfluenceAdapterAppendToPage:
    """Tests for append_to_page method."""

    @responses.activate
    def test_append_to_page(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v2: dict
    ) -> None:
        """Test appending content to a page."""
        # Mock get current page (twice - once for append, once for update)
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            json=sample_confluence_page_v2,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            json=sample_confluence_page_v2,
            status=200,
        )
        # Mock update
        responses.add(
            responses.PUT,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            json=sample_confluence_page_v2,
            status=200,
        )
        # Mock get updated page
        sample_confluence_page_v2["body"]["storage"]["value"] = "<p>Test content</p><p>Appended</p>"
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            json=sample_confluence_page_v2,
            status=200,
        )

        page = confluence_adapter.append_to_page("123456", "<p>Appended</p>")

        assert page is not None


class TestConfluenceAdapterSearch:
    """Tests for search method."""

    @responses.activate
    def test_search_text(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v1: dict
    ) -> None:
        """Test text search."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/rest/api/content/search",
            json={"results": [sample_confluence_page_v1]},
            status=200,
        )

        pages = confluence_adapter.search("deployment guide")

        assert len(pages) == 1
        assert pages[0].title == "Test Page"
        # Verify CQL was used
        assert "cql=" in responses.calls[0].request.url

    @responses.activate
    def test_search_cql(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v1: dict
    ) -> None:
        """Test CQL search."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/rest/api/content/search",
            json={"results": [sample_confluence_page_v1]},
            status=200,
        )

        pages = confluence_adapter.search("type=page AND label=runbook")

        assert len(pages) == 1

    @responses.activate
    def test_search_no_results(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test search with no results."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/rest/api/content/search",
            json={"results": []},
            status=200,
        )

        pages = confluence_adapter.search("nonexistent")
        assert len(pages) == 0

    @responses.activate
    def test_search_with_space(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v1: dict
    ) -> None:
        """Test search limited to space."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/rest/api/content/search",
            json={"results": [sample_confluence_page_v1]},
            status=200,
        )

        confluence_adapter.search("test", space="DEVOPS")

        # Verify space was added to CQL
        assert "DEVOPS" in responses.calls[0].request.url


class TestConfluenceAdapterGetPageChildren:
    """Tests for get_page_children method."""

    @responses.activate
    def test_get_page_children(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v2: dict
    ) -> None:
        """Test getting child pages."""
        child1 = sample_confluence_page_v2.copy()
        child1["id"] = "111"
        child1["title"] = "Child 1"
        child2 = sample_confluence_page_v2.copy()
        child2["id"] = "222"
        child2["title"] = "Child 2"

        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/pages/123456/children",
            json={"results": [child1, child2]},
            status=200,
        )

        children = confluence_adapter.get_page_children("123456")

        assert len(children) == 2
        assert children[0].id == "111"
        assert children[1].id == "222"


class TestConfluenceAdapterGetSpace:
    """Tests for get_space method."""

    @responses.activate
    def test_get_space(self, confluence_adapter: ConfluenceAdapter, sample_space: dict) -> None:
        """Test getting space details."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/spaces",
            json={"results": [sample_space]},
            status=200,
        )

        space = confluence_adapter.get_space("DEVOPS")

        assert space["key"] == "DEVOPS"
        assert space["name"] == "DevOps"

    @responses.activate
    def test_get_space_not_found(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test getting non-existent space."""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/wiki/api/v2/spaces",
            json={"results": []},
            status=200,
        )

        with pytest.raises(NotFoundError):
            confluence_adapter.get_space("FAKE")


class TestConfluenceAdapterDeletePage:
    """Tests for delete_page method."""

    @responses.activate
    def test_delete_page(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test deleting a page."""
        responses.add(
            responses.DELETE,
            "https://test.atlassian.net/wiki/api/v2/pages/123456",
            status=204,
        )

        confluence_adapter.delete_page("123456")

        assert len(responses.calls) == 1


class TestConfluenceAdapterParsePage:
    """Tests for page parsing methods."""

    def test_parse_page_v2_with_timestamps(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v2: dict
    ) -> None:
        """Test parsing v2 page with timestamps."""
        page = confluence_adapter._parse_page(sample_confluence_page_v2)

        assert page.created_at is not None
        assert page.updated_at is not None
        assert isinstance(page.created_at, datetime)

    def test_parse_page_v2_minimal(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test parsing minimal v2 page data."""
        minimal_data = {
            "id": "999",
            "title": "Minimal Page",
        }

        page = confluence_adapter._parse_page(minimal_data)

        assert page.id == "999"
        assert page.title == "Minimal Page"
        assert page.content is None
        assert page.version == 1

    def test_parse_page_v1_with_author(
        self, confluence_adapter: ConfluenceAdapter, sample_confluence_page_v1: dict
    ) -> None:
        """Test parsing v1 page with author info."""
        page = confluence_adapter._parse_page_v1(sample_confluence_page_v1)

        assert page.author == "author@example.com"
        assert page.space == "DEVOPS"


class TestConfluenceAdapterRegistry:
    """Tests for registry integration."""

    def test_adapter_registered(self) -> None:
        """Test that ConfluenceAdapter is registered with the registry."""
        from itsm_tools.core.registry import _wiki_provider_registry

        # Import atlassian module to trigger registration
        import itsm_tools.atlassian  # noqa: F401

        assert "atlassian_confluence" in _wiki_provider_registry


class TestConfluenceAdapterAddLabels:
    """Tests for _add_labels method."""

    @responses.activate
    def test_add_labels(self, confluence_adapter: ConfluenceAdapter) -> None:
        """Test adding labels to a page."""
        responses.add(
            responses.POST,
            "https://test.atlassian.net/wiki/api/v2/pages/123456/labels",
            json={},
            status=201,
        )
        responses.add(
            responses.POST,
            "https://test.atlassian.net/wiki/api/v2/pages/123456/labels",
            json={},
            status=201,
        )

        confluence_adapter._add_labels("123456", ["label1", "label2"])

        assert len(responses.calls) == 2
