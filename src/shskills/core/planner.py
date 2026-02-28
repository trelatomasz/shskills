"""Skill discovery: walk a fetched tree and build SkillInfo objects."""

from __future__ import annotations

import logging
from pathlib import Path

from shskills.config import SKILL_MARKER, SKILLS_ROOT
from shskills.core.fetcher import fetch_skills_tree
from shskills.core.validator import validate_skill_dir
from shskills.exceptions import ValidationError
from shskills.models import SkillInfo, SkillSource

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skill discovery helpers
# ---------------------------------------------------------------------------


def _dest_rel(rel: str, subpath: str | None) -> str:
    """Compute the destination relative path within the agent dest dir.

    When the fetched root *is* the skill dir (rel == "."), use the basename
    of the subpath so the skill is installed as a named directory.
    """
    if rel == ".":
        return Path(subpath).name if subpath else "skill"
    return rel


def _source_rel(rel: str, subpath: str | None) -> str:
    """Compute the source_path relative to SKILLS/ in the remote repo."""
    if subpath and rel != ".":
        return f"{subpath}/{rel}"
    if subpath and rel == ".":
        return subpath
    return rel


def discover_skills(skills_root: Path, subpath: str | None) -> list[SkillInfo]:
    """Walk *skills_root* and return one SkillInfo per discovered skill.

    A skill is any directory that contains a ``SKILL.md`` file.
    Invalid skill directories are skipped with a warning.

    Args:
        skills_root:  Local path to the fetched tree root
                      (i.e. ``<tmpdir>/SKILLS/<subpath>`` or ``<tmpdir>/SKILLS``).
        subpath:      The ``--subpath`` value that was used to fetch, or None.
    """
    skills: list[SkillInfo] = []

    for skill_md in sorted(skills_root.rglob(SKILL_MARKER)):
        skill_dir = skill_md.parent
        try:
            rel_path_obj = skill_dir.relative_to(skills_root)
        except ValueError:
            continue

        rel = rel_path_obj.as_posix()  # forward slashes on all platforms
        dest_rel = _dest_rel(rel, subpath)
        source_rel = _source_rel(rel, subpath)
        name = Path(dest_rel).name

        try:
            frontmatter, files, sha = validate_skill_dir(skill_dir)
        except ValidationError as exc:
            logger.warning("Skipping invalid skill at '%s': %s", rel or subpath, exc)
            continue

        skills.append(
            SkillInfo(
                name=name,
                rel_path=dest_rel,
                source_rel=source_rel,
                local_path=skill_dir,
                frontmatter=frontmatter,
                files=files,
                content_sha256=sha,
            )
        )

    return skills


# ---------------------------------------------------------------------------
# Public API: list_skills
# ---------------------------------------------------------------------------


def list_skills(url: str, subpath: str | None = None, ref: str = "main") -> list[SkillInfo]:
    """Fetch *url* and return all discoverable skills under *subpath*.

    This is a read-only operation: nothing is installed or written locally.

    Args:
        url:      Git repository URL.
        subpath:  Optional path relative to ``SKILLS/`` to limit the search.
        ref:      Branch, tag, or commit SHA.

    Returns:
        List of SkillInfo objects, sorted by their destination relative path.
    """
    source = SkillSource(url=url, ref=ref, subpath=subpath)
    _ = source  # validated; used for type checking only

    with fetch_skills_tree(url, ref, subpath) as skills_root:
        return discover_skills(skills_root, subpath)
