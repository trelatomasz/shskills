"""Unit tests for shskills.core.fetcher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shskills.core.fetcher import _is_commit_sha, _run, _sparse_target
from shskills.exceptions import FetchError

# ---------------------------------------------------------------------------
# _is_commit_sha
# ---------------------------------------------------------------------------


class TestIsCommitSha:
    def test_full_lowercase_sha(self) -> None:
        assert _is_commit_sha("a" * 40) is True

    def test_full_uppercase_sha(self) -> None:
        assert _is_commit_sha("A" * 40) is True

    def test_mixed_case_sha(self) -> None:
        assert _is_commit_sha("a1B2c3D4" * 5) is True

    def test_short_sha_is_false(self) -> None:
        assert _is_commit_sha("abc123") is False

    def test_branch_name_is_false(self) -> None:
        assert _is_commit_sha("main") is False

    def test_tag_name_is_false(self) -> None:
        assert _is_commit_sha("v1.0.0") is False

    def test_39_chars_is_false(self) -> None:
        assert _is_commit_sha("a" * 39) is False

    def test_41_chars_is_false(self) -> None:
        assert _is_commit_sha("a" * 41) is False

    def test_non_hex_chars_is_false(self) -> None:
        assert _is_commit_sha("z" * 40) is False


# ---------------------------------------------------------------------------
# _sparse_target
# ---------------------------------------------------------------------------


class TestSparseTarget:
    def test_no_subpath(self) -> None:
        assert _sparse_target(None) == "SKILLS"

    def test_single_segment(self) -> None:
        assert _sparse_target("common") == "SKILLS/common"

    def test_nested_subpath(self) -> None:
        assert _sparse_target("common/welcome_note") == "SKILLS/common/welcome_note"


# ---------------------------------------------------------------------------
# _run
# ---------------------------------------------------------------------------


class TestRun:
    def test_raises_fetch_error_on_nonzero_exit(self) -> None:
        with pytest.raises(FetchError, match="Command failed"):
            _run(["false"])  # 'false' always exits 1

    def test_success_returns_completed_process(self) -> None:
        result = _run(["true"])
        assert result.returncode == 0

    def test_error_includes_command(self) -> None:
        try:
            _run(["git", "this-is-not-a-valid-subcommand"])
        except FetchError as exc:
            assert "git" in str(exc)


# ---------------------------------------------------------------------------
# fetch_skills_tree (mocked git)
# ---------------------------------------------------------------------------


class TestFetchSkillsTree:
    def test_raises_on_missing_skills_path(self, tmp_path: Path) -> None:
        """After clone, if SKILLS/ is absent, FetchError is raised."""
        from shskills.core.fetcher import fetch_skills_tree

        def fake_run(cmd: list[str], cwd: Path | None = None) -> MagicMock:
            # Simulate successful git calls but write nothing to disk
            m = MagicMock()
            m.returncode = 0
            return m

        from shskills.models import SkillSource

        with (
            patch("shskills.core.fetcher._run", side_effect=fake_run),
            pytest.raises(FetchError, match="not found"),
            fetch_skills_tree(SkillSource(url="https://example.com/repo.git", ref="main")) as _,
        ):
            pass

    def test_yields_correct_path(self, tmp_path: Path) -> None:
        """Context manager yields the expected SKILLS path when it exists."""
        from shskills.core.fetcher import fetch_skills_tree

        created_skills_path: list[Path] = []

        def fake_run(cmd: list[str], cwd: Path | None = None) -> MagicMock:
            # When clone is called (no -C flag), create the SKILLS dir inside dest
            if "clone" in cmd:
                dest = Path(cmd[-1])
                (dest / "SKILLS").mkdir(parents=True, exist_ok=True)
            m = MagicMock()
            m.returncode = 0
            return m

        from shskills.models import SkillSource

        with (
            patch("shskills.core.fetcher._run", side_effect=fake_run),
            fetch_skills_tree(SkillSource(url="https://example.com/repo.git", ref="main")) as p,
        ):
            created_skills_path.append(p)

        assert len(created_skills_path) == 1
        assert created_skills_path[0].name == "SKILLS"

    def test_tmpdir_cleaned_up(self, tmp_path: Path) -> None:
        """Temporary directory is deleted even when FetchError is raised."""
        from shskills.core.fetcher import fetch_skills_tree

        seen_tmpdirs: list[Path] = []

        def fake_run(cmd: list[str], cwd: Path | None = None) -> MagicMock:
            if "clone" in cmd:
                dest = Path(cmd[-1])
                seen_tmpdirs.append(dest)
                # do NOT create SKILLS/ → will trigger FetchError
            m = MagicMock()
            m.returncode = 0
            return m

        from shskills.models import SkillSource

        with (
            pytest.raises(FetchError),
            patch("shskills.core.fetcher._run", side_effect=fake_run),
            fetch_skills_tree(SkillSource(url="https://example.com/r.git", ref="main")) as _,
        ):
            pass

        # The tmpdir should have been cleaned up by TemporaryDirectory context manager
        if seen_tmpdirs:
            assert not seen_tmpdirs[0].exists()
