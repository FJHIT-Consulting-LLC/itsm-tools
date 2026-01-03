"""Adapter registry for dynamic provider discovery and instantiation."""

from typing import Any, Type, TypeVar

from itsm_tools.core.interfaces import IssueTracker, WikiProvider, IncidentManager
from itsm_tools.core.exceptions import ITSMError

T = TypeVar("T", IssueTracker, WikiProvider, IncidentManager)

# Global registries for each interface type
_issue_tracker_registry: dict[str, Type[IssueTracker]] = {}
_wiki_provider_registry: dict[str, Type[WikiProvider]] = {}
_incident_manager_registry: dict[str, Type[IncidentManager]] = {}


def register_adapter(
    name: str,
    interface: Type[T],
) -> Any:
    """Decorator to register an adapter implementation.

    Args:
        name: Adapter name (e.g., 'atlassian_jira', 'servicenow')
        interface: Interface class the adapter implements

    Returns:
        Decorator function

    Example:
        @register_adapter('atlassian_jira', IssueTracker)
        class JiraAdapter(IssueTracker):
            ...
    """

    def decorator(cls: Type[T]) -> Type[T]:
        if interface == IssueTracker:
            _issue_tracker_registry[name] = cls  # type: ignore
        elif interface == WikiProvider:
            _wiki_provider_registry[name] = cls  # type: ignore
        elif interface == IncidentManager:
            _incident_manager_registry[name] = cls  # type: ignore
        else:
            raise ValueError(f"Unknown interface type: {interface}")
        return cls

    return decorator


def get_issue_tracker(
    provider: str | None = None,
    config: dict[str, Any] | None = None,
) -> IssueTracker:
    """Get an issue tracker adapter instance.

    Args:
        provider: Provider name (e.g., 'atlassian_jira'). If None, uses default.
        config: Provider configuration

    Returns:
        IssueTracker implementation instance

    Raises:
        ITSMError: If provider not found or configuration invalid
    """
    # Import adapters to trigger registration
    _import_adapters()

    if provider is None:
        provider = _get_default_provider("issue_tracker")

    if provider not in _issue_tracker_registry:
        available = list(_issue_tracker_registry.keys())
        raise ITSMError(
            f"Issue tracker '{provider}' not found. Available: {available}",
            provider=provider,
        )

    adapter_class = _issue_tracker_registry[provider]
    return adapter_class(config or {})


def get_wiki_provider(
    provider: str | None = None,
    config: dict[str, Any] | None = None,
) -> WikiProvider:
    """Get a wiki provider adapter instance.

    Args:
        provider: Provider name (e.g., 'atlassian_confluence'). If None, uses default.
        config: Provider configuration

    Returns:
        WikiProvider implementation instance

    Raises:
        ITSMError: If provider not found or configuration invalid
    """
    _import_adapters()

    if provider is None:
        provider = _get_default_provider("wiki")

    if provider not in _wiki_provider_registry:
        available = list(_wiki_provider_registry.keys())
        raise ITSMError(
            f"Wiki provider '{provider}' not found. Available: {available}",
            provider=provider,
        )

    adapter_class = _wiki_provider_registry[provider]
    return adapter_class(config or {})


def get_incident_manager(
    provider: str | None = None,
    config: dict[str, Any] | None = None,
) -> IncidentManager:
    """Get an incident manager adapter instance.

    Args:
        provider: Provider name (e.g., 'atlassian_jsm'). If None, uses default.
        config: Provider configuration

    Returns:
        IncidentManager implementation instance

    Raises:
        ITSMError: If provider not found or configuration invalid
    """
    _import_adapters()

    if provider is None:
        provider = _get_default_provider("incidents")

    if provider not in _incident_manager_registry:
        available = list(_incident_manager_registry.keys())
        raise ITSMError(
            f"Incident manager '{provider}' not found. Available: {available}",
            provider=provider,
        )

    adapter_class = _incident_manager_registry[provider]
    return adapter_class(config or {})


def list_adapters() -> dict[str, list[str]]:
    """List all registered adapters.

    Returns:
        Dictionary mapping interface types to registered adapter names
    """
    _import_adapters()
    return {
        "issue_tracker": list(_issue_tracker_registry.keys()),
        "wiki": list(_wiki_provider_registry.keys()),
        "incidents": list(_incident_manager_registry.keys()),
    }


def _import_adapters() -> None:
    """Import all adapter modules to trigger registration."""
    # These imports register adapters via decorators
    try:
        import itsm_tools.atlassian  # noqa: F401
    except ImportError:
        pass

    try:
        import itsm_tools.servicenow  # noqa: F401
    except ImportError:
        pass

    try:
        import itsm_tools.pagerduty  # noqa: F401
    except ImportError:
        pass


def _get_default_provider(interface_type: str) -> str:
    """Get the default provider for an interface type.

    This can be configured via environment variables or config file.

    Args:
        interface_type: Interface type ('issue_tracker', 'wiki', 'incidents')

    Returns:
        Default provider name

    Raises:
        ITSMError: If no default configured and no providers available
    """
    import os

    # Check environment variables
    env_var = f"ITSM_{interface_type.upper()}_PROVIDER"
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value

    # Fallback to first registered provider
    if interface_type == "issue_tracker" and _issue_tracker_registry:
        return next(iter(_issue_tracker_registry.keys()))
    if interface_type == "wiki" and _wiki_provider_registry:
        return next(iter(_wiki_provider_registry.keys()))
    if interface_type == "incidents" and _incident_manager_registry:
        return next(iter(_incident_manager_registry.keys()))

    raise ITSMError(
        f"No default provider configured for {interface_type}. "
        f"Set {env_var} environment variable or specify provider explicitly."
    )