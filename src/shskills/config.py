"""Runtime constants and configuration helpers."""

from __future__ import annotations

from pathlib import Path

# Mapping from agent name to default installation destination (relative to cwd).
AGENT_DEST_MAP: dict[str, str] = {
    "claude": ".claude/skills",
    "codex": ".codex/skills",
    "gemini": ".gemini/skills",
    "opencode": ".opencode/skills",
}

KNOWN_AGENTS: frozenset[str] = frozenset(AGENT_DEST_MAP.keys()) | {"custom"}

# Top-level directory name inside the remote repository that contains skills.
SKILLS_ROOT: str = "SKILLS"

# Filename that marks a directory as a skill.
SKILL_MARKER: str = "SKILL.md"

# Name of the manifest file written inside each agent destination directory.
MANIFEST_FILENAME: str = ".shskills-manifest.json"

# Default git ref when none is specified.
DEFAULT_REF: str = "main"

# Maximum allowed size (bytes) for a single skill file.
MAX_FILE_BYTES: int = 512 * 1024  # 512 KB


def resolve_dest(agent: str, dest: str | Path | None) -> Path:
    """Return the resolved destination Path for an agent + optional override.

    Raises ConfigError for unknown agents or when 'custom' is used without --dest.
    """
    from shskills.exceptions import ConfigError  # local import avoids circular dep

    if dest is not None:
        return Path(dest)
    if agent == "custom":
        raise ConfigError("--dest is required when --agent is 'custom'")
    if agent not in AGENT_DEST_MAP:
        known = ", ".join(sorted(KNOWN_AGENTS))
        raise ConfigError(f"Unknown agent '{agent}'. Known agents: {known}")
    return Path(AGENT_DEST_MAP[agent])
