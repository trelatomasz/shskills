"""Unit tests for shskills.core.planner."""

from __future__ import annotations

from pathlib import Path

import pytest

from shskills.core.planner import _dest_rel, _sanitize_segment, _source_rel, discover_skills
from tests.conftest import write_skill

# ---------------------------------------------------------------------------
# _dest_rel
# ---------------------------------------------------------------------------


class TestSanitizeSegment:
    def test_passthrough_clean(self) -> None:
        assert _sanitize_segment("welcome_note") == "welcome_note"

    def test_double_underscore_collapsed(self) -> None:
        assert _sanitize_segment("my__skill") == "my_skill"

    def test_triple_underscore_collapsed(self) -> None:
        assert _sanitize_segment("aws___group") == "aws_group"

    def test_many_underscores_collapsed(self) -> None:
        assert _sanitize_segment("a____b") == "a_b"

    def test_no_underscores_unchanged(self) -> None:
        assert _sanitize_segment("authenticate") == "authenticate"


class TestDestRel:
    def test_simple(self) -> None:
        assert _dest_rel("welcome_note", None) == "welcome_note"

    def test_nested(self) -> None:
        assert _dest_rel("common/welcome_note", None) == "common__welcome_note"

    def test_deeply_nested(self) -> None:
        assert _dest_rel("aws/auth/authenticate_skill", None) == "aws_auth__authenticate_skill"

    def test_dot_with_subpath(self) -> None:
        # subpath pointed directly at the skill dir
        assert _dest_rel(".", "common/welcome_note") == "welcome_note"

    def test_dot_without_subpath(self) -> None:
        assert _dest_rel(".", None) == "skill"

    def test_nested_subpath_with_dot(self) -> None:
        assert _dest_rel(".", "tools/deploy") == "deploy"

    def test_sanitizes_double_underscore_in_leaf(self) -> None:
        assert _dest_rel("my__skill", None) == "my_skill"

    def test_sanitizes_double_underscore_in_prefix(self) -> None:
        assert _dest_rel("common/my__skill", None) == "common__my_skill"

    def test_sanitizes_double_underscore_in_group_segment(self) -> None:
        assert _dest_rel("aws___group/skill", None) == "aws_group__skill"


# ---------------------------------------------------------------------------
# _source_rel
# ---------------------------------------------------------------------------


class TestSourceRel:
    def test_no_subpath(self) -> None:
        assert _source_rel("common/welcome_note", None) == "common/welcome_note"

    def test_with_subpath_appends_prefix(self) -> None:
        assert _source_rel("welcome_note", "common") == "common/welcome_note"

    def test_with_subpath_dot(self) -> None:
        assert _source_rel(".", "common/welcome_note") == "common/welcome_note"

    def test_single_segment_no_subpath(self) -> None:
        assert _source_rel("alpha", None) == "alpha"


# ---------------------------------------------------------------------------
# discover_skills
# ---------------------------------------------------------------------------


class TestDiscoverSkills:
    def test_finds_flat_skill(self, tmp_path: Path) -> None:
        write_skill(tmp_path, "alpha")
        skills = discover_skills(tmp_path, subpath=None)
        assert len(skills) == 1
        assert skills[0].name == "alpha"

    def test_finds_nested_skills(self, tmp_path: Path) -> None:
        write_skill(tmp_path / "group_a", "skill_1")
        write_skill(tmp_path / "group_b", "skill_2")

        skills = discover_skills(tmp_path, subpath=None)
        rel_paths = {s.rel_path for s in skills}
        assert "group_a__skill_1" in rel_paths
        assert "group_b__skill_2" in rel_paths

    def test_empty_tree_returns_empty(self, tmp_path: Path) -> None:
        assert discover_skills(tmp_path, subpath=None) == []

    def test_subpath_preserved_in_rel_path(self, tmp_path: Path) -> None:
        write_skill(tmp_path, "welcome_note")
        skills = discover_skills(tmp_path, subpath="common")
        assert len(skills) == 1
        assert skills[0].rel_path == "welcome_note"

    def test_source_rel_includes_subpath(self, tmp_path: Path) -> None:
        write_skill(tmp_path, "welcome_note")
        skills = discover_skills(tmp_path, subpath="common")
        assert skills[0].source_rel == "common/welcome_note"

    def test_root_is_skill_dir(self, tmp_path: Path) -> None:
        """When the fetched root is itself a skill directory."""
        (tmp_path / "SKILL.md").write_text(
            "---\nname: root_skill\n---\n# root", encoding="utf-8"
        )
        skills = discover_skills(tmp_path, subpath="tools/root_skill")
        assert len(skills) == 1
        assert skills[0].name == "root_skill"
        assert skills[0].rel_path == "root_skill"

    def test_invalid_skill_skipped_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        write_skill(tmp_path, "valid")
        # Directory without SKILL.md — should be ignored
        bad = tmp_path / "bad_skill"
        bad.mkdir()
        (bad / "README.md").write_text("no skill marker")

        import logging

        with caplog.at_level(logging.WARNING, logger="shskills.core.planner"):
            skills = discover_skills(tmp_path, subpath=None)

        assert len(skills) == 1
        assert skills[0].name == "valid"

    def test_sha256_populated(self, tmp_path: Path) -> None:
        write_skill(tmp_path, "alpha")
        skills = discover_skills(tmp_path, subpath=None)
        assert len(skills[0].content_sha256) == 64

    def test_multiple_skills_sorted(self, tmp_path: Path) -> None:
        for name in ["z_skill", "a_skill", "m_skill"]:
            write_skill(tmp_path, name)
        skills = discover_skills(tmp_path, subpath=None)
        rel_paths = [s.rel_path for s in skills]
        assert rel_paths == sorted(rel_paths)
