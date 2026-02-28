"""Claude agent adapter.

Installs skills into ``.claude/skills/``.  SKILL.md files are copied verbatim;
Claude Code reads them directly as slash-command markdown files.
"""

from __future__ import annotations

from shskills.adapters.base import AgentAdapter


class ClaudeAdapter(AgentAdapter):
    """Adapter for Claude Code (Anthropic CLI)."""

    @property
    def agent_name(self) -> str:
        return "claude"
