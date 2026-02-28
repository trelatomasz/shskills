"""Custom agent adapter.

Used when ``--agent custom`` is specified.  Requires ``--dest`` to be set.
Files are copied verbatim; no agent-specific transformation is applied.
"""

from __future__ import annotations

from shskills.adapters.base import AgentAdapter


class CustomAdapter(AgentAdapter):
    """Generic pass-through adapter for user-defined destinations."""

    @property
    def agent_name(self) -> str:
        return "custom"
