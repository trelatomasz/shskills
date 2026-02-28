"""Gemini agent adapter.

Installs skills into ``.gemini/skills/``.
"""

from __future__ import annotations

from shskills.adapters.base import AgentAdapter


class GeminiAdapter(AgentAdapter):
    """Adapter for Google Gemini CLI."""

    @property
    def agent_name(self) -> str:
        return "gemini"
