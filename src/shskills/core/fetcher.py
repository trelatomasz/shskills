"""Git-based skills fetcher using sparse checkout."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from shskills.config import SKILLS_ROOT
from shskills.exceptions import FetchError
from shskills.models import SkillSource


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command, raising FetchError on non-zero exit."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    if result.returncode != 0:
        pretty_cmd = " ".join(cmd)
        detail = result.stderr.strip() or result.stdout.strip()
        raise FetchError(f"Command failed: {pretty_cmd}\n{detail}")
    return result


def _is_commit_sha(ref: str) -> bool:
    """Return True when ref looks like a full 40-character hex commit SHA."""
    return len(ref) == 40 and all(c in "0123456789abcdefABCDEF" for c in ref)


def _sparse_target(subpath: str | None) -> str:
    """Build the sparse-checkout path (relative to repo root)."""
    if subpath:
        return f"{SKILLS_ROOT}/{subpath}"
    return SKILLS_ROOT


# ---------------------------------------------------------------------------
# Fetch implementations
# ---------------------------------------------------------------------------


def _fetch_branch_or_tag(url: str, ref: str, dest: Path, sparse_target: str) -> None:
    """Clone a branch or tag with depth=1 and sparse checkout."""
    _run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--no-checkout",
            "--branch",
            ref,
            url,
            str(dest),
        ]
    )
    _run(["git", "-C", str(dest), "sparse-checkout", "init", "--cone"])
    _run(["git", "-C", str(dest), "sparse-checkout", "set", sparse_target])
    _run(["git", "-C", str(dest), "checkout"])


def _fetch_at_sha(url: str, sha: str, dest: Path, sparse_target: str) -> None:
    """Clone without depth limit (required for arbitrary commit SHA checkout)."""
    _run(
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            url,
            str(dest),
        ]
    )
    _run(["git", "-C", str(dest), "sparse-checkout", "init", "--cone"])
    _run(["git", "-C", str(dest), "sparse-checkout", "set", sparse_target])
    _run(["git", "-C", str(dest), "checkout", sha])


# ---------------------------------------------------------------------------
# Public context manager
# ---------------------------------------------------------------------------


@contextmanager
def fetch_skills_tree(source: SkillSource) -> Iterator[Path]:
    """Clone the remote repo (sparse) and yield the local SKILLS/<subpath> path.

    The temporary directory is always cleaned up on exit regardless of errors.

    Args:
        source:  SkillSource describing the repository URL, ref, and subpath.

    Yields:
        Absolute Path to the fetched skills root (SKILLS/<subpath> or SKILLS/).

    Raises:
        FetchError: if git operations fail or the expected path is absent.
    """
    target = _sparse_target(source.subpath)

    with tempfile.TemporaryDirectory(prefix="shskills-") as tmpdir:
        tmp = Path(tmpdir)

        if _is_commit_sha(source.ref):
            _fetch_at_sha(source.url, source.ref, tmp, target)
        else:
            _fetch_branch_or_tag(source.url, source.ref, tmp, target)

        skills_path = tmp / target
        if not skills_path.exists():
            raise FetchError(
                f"Path '{target}' not found in repository '{source.url}' at ref '{source.ref}'"
            )

        yield skills_path
