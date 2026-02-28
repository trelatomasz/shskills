"""Agent adapters for shskills."""

from shskills.adapters.base import AgentAdapter
from shskills.adapters.claude import ClaudeAdapter
from shskills.adapters.codex import CodexAdapter
from shskills.adapters.custom import CustomAdapter
from shskills.adapters.gemini import GeminiAdapter
from shskills.adapters.opencode import OpenCodeAdapter

_REGISTRY: dict[str, type[AgentAdapter]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "gemini": GeminiAdapter,
    "opencode": OpenCodeAdapter,
    "custom": CustomAdapter,
}


def get_adapter(agent: str) -> AgentAdapter:
    """Return an instantiated AgentAdapter for *agent*.

    Raises KeyError when *agent* is not registered.
    """
    cls = _REGISTRY.get(agent)
    if cls is None:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"No adapter registered for agent '{agent}'. Known: {known}")
    return cls()


__all__ = [
    "AgentAdapter",
    "ClaudeAdapter",
    "CodexAdapter",
    "GeminiAdapter",
    "OpenCodeAdapter",
    "CustomAdapter",
    "get_adapter",
]
