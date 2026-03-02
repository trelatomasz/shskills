"""Skill directory validation and SKILL.md front-matter parsing."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from shskills.config import MAX_FILE_BYTES, SKILL_MARKER
from shskills.exceptions import ValidationError
from shskills.models import SkillFrontmatter

# ---------------------------------------------------------------------------
# Front-matter parsing
# ---------------------------------------------------------------------------

# Matches a YAML-style --- delimited block at the start of the file.
_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.DOTALL)
_FIELD_RE = re.compile(r"^([A-Za-z_]\w*)\s*:\s*(.+)$", re.MULTILINE)


def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract key/value pairs from a ``---`` delimited front-matter block.

    Returns an empty dict when no front-matter block is present.
    Values are stripped of surrounding whitespace and quote characters.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}
    fm_text = match.group(1)
    return {k: v.strip().strip("\"'") for k, v in _FIELD_RE.findall(fm_text)}


def parse_skill_frontmatter(skill_dir: Path) -> SkillFrontmatter:
    """Parse SKILL.md in *skill_dir* and return a SkillFrontmatter.

    Falls back to the directory name as ``name`` when the field is absent.
    """
    skill_md = skill_dir / SKILL_MARKER
    raw = skill_md.read_text(encoding="utf-8")
    fields = parse_frontmatter(raw)

    name = fields.get("name", skill_dir.name)
    description = fields.get("description", "")
    version = fields.get("version", "1.0.0")

    return SkillFrontmatter(name=name, description=description, version=version)


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

_UNSAFE_SEGMENTS: frozenset[str] = frozenset({"", ".", ".."})


def assert_path_safe(path: Path, label: str = "path") -> None:
    """Raise ValidationError if *path* contains unsafe segments or is absolute."""
    if os.path.isabs(path):
        raise ValidationError(f"Unsafe {label}: absolute path '{path}'")
    for part in path.parts:
        if part in _UNSAFE_SEGMENTS:
            raise ValidationError(f"Unsafe {label}: segment '{part}' is not allowed in '{path}'")


def assert_no_symlinks(skill_dir: Path) -> None:
    """Raise ValidationError if any entry inside *skill_dir* is a symlink."""
    for entry in skill_dir.rglob("*"):
        if entry.is_symlink():
            raise ValidationError(
                f"Symlink detected in skill '{skill_dir.name}': {entry.relative_to(skill_dir)}"
            )


# ---------------------------------------------------------------------------
# File listing and size checks
# ---------------------------------------------------------------------------


def list_skill_files(skill_dir: Path) -> list[str]:
    """Return sorted relative paths inside *skill_dir* (recursive, files only).

    Paths use POSIX separators (``/``) on all platforms so that the list and
    the SHA-256 computed from it are platform-independent.
    """
    return sorted(
        entry.relative_to(skill_dir).as_posix()
        for entry in skill_dir.rglob("*")
        if entry.is_file() and not entry.is_symlink()
    )


def assert_file_sizes(skill_dir: Path, file_names: list[str]) -> None:
    """Raise ValidationError if any file exceeds MAX_FILE_BYTES."""
    for name in file_names:
        size = (skill_dir / name).stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValidationError(
                f"File '{name}' in skill '{skill_dir.name}' is {size} bytes (max {MAX_FILE_BYTES})"
            )


# ---------------------------------------------------------------------------
# SHA-256 digest
# ---------------------------------------------------------------------------


def compute_skill_sha256(skill_dir: Path, file_names: list[str]) -> str:
    """Compute a deterministic SHA-256 over all skill file contents.

    Files are processed in sorted order so the result is stable.
    Each file contributes its name (UTF-8) followed by its raw bytes.
    """
    h = hashlib.sha256()
    for name in sorted(file_names):
        h.update(name.encode("utf-8"))
        h.update((skill_dir / name).read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Top-level skill validation
# ---------------------------------------------------------------------------


def validate_skill_dir(skill_dir: Path) -> tuple[SkillFrontmatter, list[str], str]:
    """Fully validate *skill_dir* and return ``(frontmatter, files, sha256)``.

    Raises ValidationError on any structural problem.
    """
    if not skill_dir.is_dir():
        raise ValidationError(f"Not a directory: {skill_dir}")

    skill_md = skill_dir / SKILL_MARKER
    if not skill_md.exists():
        raise ValidationError(f"Missing {SKILL_MARKER} in '{skill_dir}'")

    assert_no_symlinks(skill_dir)

    files = list_skill_files(skill_dir)
    assert_file_sizes(skill_dir, files)

    frontmatter = parse_skill_frontmatter(skill_dir)
    sha = compute_skill_sha256(skill_dir, files)

    return frontmatter, files, sha
