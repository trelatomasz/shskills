"""Pydantic v2 models for shskills."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Source / discovery
# ---------------------------------------------------------------------------


class SkillSource(BaseModel):
    """Identifies a remote skills tree."""

    url: str
    ref: str = "main"
    subpath: str | None = None


class SkillFrontmatter(BaseModel):
    """Parsed metadata from a SKILL.md front-matter block."""

    name: str
    description: str = ""
    version: str = "1.0.0"


class SkillInfo(BaseModel):
    """A skill discovered in a local (fetched) tree. Not persisted."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    """Basename of the skill directory."""

    rel_path: str
    """Path relative to the subpath root (i.e. the fetched tree root).
    Used as the destination sub-path within the agent dest dir."""

    source_rel: str
    """Path relative to SKILLS/ in the remote repo.  Stored in manifest."""

    local_path: Path
    """Absolute path of the skill directory in the local tmpdir."""

    frontmatter: SkillFrontmatter
    files: list[str]
    """Sorted filenames present in the skill directory."""

    content_sha256: str
    """SHA-256 of all file contents (deterministic, for idempotency)."""


# ---------------------------------------------------------------------------
# Install plan
# ---------------------------------------------------------------------------


class InstallActionKind(str, Enum):
    INSTALL = "install"
    UPDATE = "update"
    SKIP = "skip"
    CONFLICT = "conflict"


class InstallAction(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    skill: SkillInfo
    dest_rel: str
    """Relative path within the destination directory."""

    kind: InstallActionKind
    reason: str = ""


class InstallPlan(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: SkillSource
    agent: str
    dest: Path
    actions: list[InstallAction]
    dry_run: bool = False
    force: bool = False
    clean: bool = False
    strict: bool = False


# ---------------------------------------------------------------------------
# Manifest (persisted)
# ---------------------------------------------------------------------------


class InstalledSkill(BaseModel):
    """Manifest record for one installed skill."""

    name: str
    source_path: str
    """Relative path from SKILLS/ in the remote repo."""

    dest_path: str
    """Relative path from the project root to the installed skill directory."""

    content_sha256: str
    installed_at: datetime
    files: list[str]


class Manifest(BaseModel):
    """Content of .shskills-manifest.json."""

    version: str = "1"
    agent: str
    dest: str
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    source: SkillSource
    skills: dict[str, InstalledSkill] = {}
    """Keys are dest_rel paths (relative to the dest dir)."""


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


class InstallResult(BaseModel):
    installed: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []
    conflicts: list[str] = []
    errors: list[str] = []
    cleaned: list[str] = []

    @property
    def success(self) -> bool:
        return not self.errors and not self.conflicts

    @property
    def total_changes(self) -> int:
        return len(self.installed) + len(self.updated) + len(self.cleaned)


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


class DoctorSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class DoctorIssue(BaseModel):
    severity: DoctorSeverity
    message: str


class DoctorReport(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: str
    dest: Path
    issues: list[DoctorIssue] = []
    installed_count: int = 0

    @property
    def healthy(self) -> bool:
        return not any(i.severity == DoctorSeverity.ERROR for i in self.issues)
