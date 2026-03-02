"""Unit tests for shskills.core.manifest."""

from __future__ import annotations

from pathlib import Path

import pytest

from shskills.config import MANIFEST_FILENAME
from shskills.core.manifest import (
    installed_skills,
    read_manifest,
    remove_manifest_skill,
    update_manifest_skill,
    write_manifest,
)
from shskills.exceptions import ManifestError
from shskills.models import Manifest, SkillSource


def _make_manifest(dest: Path) -> Manifest:
    return Manifest(
        agent="claude",
        dest=str(dest),
        source=SkillSource(url="https://github.com/org/repo", ref="main"),
    )


# ---------------------------------------------------------------------------
# read_manifest
# ---------------------------------------------------------------------------


class TestReadManifest:
    def test_returns_none_when_absent(self, tmp_path: Path) -> None:
        assert read_manifest(tmp_path) is None

    def test_raises_on_corrupt_json(self, tmp_path: Path) -> None:
        (tmp_path / MANIFEST_FILENAME).write_text("{bad json", encoding="utf-8")
        with pytest.raises(ManifestError, match="Failed to parse"):
            read_manifest(tmp_path)

    def test_raises_on_invalid_schema(self, tmp_path: Path) -> None:
        (tmp_path / MANIFEST_FILENAME).write_text('{"version": 99}', encoding="utf-8")
        with pytest.raises(ManifestError):
            read_manifest(tmp_path)


# ---------------------------------------------------------------------------
# write_manifest / round-trip
# ---------------------------------------------------------------------------


class TestWriteManifest:
    def test_round_trip(self, tmp_path: Path) -> None:
        m = _make_manifest(tmp_path)
        write_manifest(tmp_path, m)

        loaded = read_manifest(tmp_path)
        assert loaded is not None
        assert loaded.agent == "claude"
        assert loaded.version == "1"
        assert loaded.source.url == "https://github.com/org/repo"

    def test_no_leftover_tmp_files(self, tmp_path: Path) -> None:
        write_manifest(tmp_path, _make_manifest(tmp_path))
        tmp_files = list(tmp_path.glob(".manifest-*.tmp"))
        assert tmp_files == [], "Temp file was not cleaned up"

    def test_creates_dest_directory(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c"
        write_manifest(deep, _make_manifest(deep))
        assert (deep / MANIFEST_FILENAME).exists()

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        m = _make_manifest(tmp_path)
        write_manifest(tmp_path, m)
        m.agent = "codex"
        write_manifest(tmp_path, m)

        loaded = read_manifest(tmp_path)
        assert loaded is not None
        assert loaded.agent == "codex"


# ---------------------------------------------------------------------------
# update_manifest_skill / remove_manifest_skill
# ---------------------------------------------------------------------------


class TestUpdateRemove:
    def test_update_adds_entry(self, tmp_path: Path) -> None:
        m = _make_manifest(tmp_path)
        update_manifest_skill(
            m,
            dest_rel="welcome_note",
            skill_name="welcome_note",
            source_path="common/welcome_note",
            dest_path=".claude/skills/welcome_note",
            sha256="abc123",
            files=["SKILL.md"],
        )
        assert "welcome_note" in m.skills
        assert m.skills["welcome_note"].content_sha256 == "abc123"

    def test_update_upserts(self, tmp_path: Path) -> None:
        m = _make_manifest(tmp_path)
        update_manifest_skill(m, "s", "s", "s", ".c/s", "sha1", ["SKILL.md"])
        update_manifest_skill(m, "s", "s", "s", ".c/s", "sha2", ["SKILL.md"])
        assert m.skills["s"].content_sha256 == "sha2"

    def test_remove_deletes_entry(self, tmp_path: Path) -> None:
        m = _make_manifest(tmp_path)
        update_manifest_skill(m, "x", "x", "x", ".c/x", "sha", ["SKILL.md"])
        remove_manifest_skill(m, "x")
        assert "x" not in m.skills

    def test_remove_nonexistent_is_noop(self, tmp_path: Path) -> None:
        m = _make_manifest(tmp_path)
        remove_manifest_skill(m, "nonexistent")  # must not raise

    def test_updated_at_is_bumped(self, tmp_path: Path) -> None:
        m = _make_manifest(tmp_path)
        before = m.updated_at
        update_manifest_skill(m, "s", "s", "s", ".c/s", "sha", ["SKILL.md"])
        assert m.updated_at >= before


# ---------------------------------------------------------------------------
# installed_skills public API
# ---------------------------------------------------------------------------


class TestInstalledSkills:
    def test_empty_when_no_manifest(self, tmp_path: Path) -> None:
        result = installed_skills(agent="claude", dest=tmp_path / "nowhere")
        assert result == []

    def test_returns_list_from_manifest(self, tmp_path: Path) -> None:
        m = _make_manifest(tmp_path)
        update_manifest_skill(
            m, "s1", "s1", "group/s1", ".claude/skills/s1", "sha1", ["SKILL.md"]
        )
        update_manifest_skill(
            m, "s2", "s2", "group/s2", ".claude/skills/s2", "sha2", ["SKILL.md"]
        )
        write_manifest(tmp_path, m)

        result = installed_skills(agent="claude", dest=tmp_path)
        assert len(result) == 2
        names = {s.name for s in result}
        assert "s1" in names and "s2" in names
