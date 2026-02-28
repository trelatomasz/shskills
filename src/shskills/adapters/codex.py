"""Codex agent adapter.

Installs skills into ``.codex/skills/``.
"""

from __future__ import annotations

from shskills.adapters.base import AgentAdapter


class CodexAdapter(AgentAdapter):
    """Adapter for OpenAI Codex CLI."""

    @property
    def agent_name(self) -> str:
        return "codex"
