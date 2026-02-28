"""OpenCode agent adapter.

Installs skills into ``.opencode/skills/``.
"""

from __future__ import annotations

from shskills.adapters.base import AgentAdapter


class OpenCodeAdapter(AgentAdapter):
    """Adapter for OpenCode CLI."""

    @property
    def agent_name(self) -> str:
        return "opencode"
