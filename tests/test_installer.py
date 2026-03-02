"""Unit tests for shskills.core.installer and shskills.config."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shskills.adapters.claude import ClaudeAdapter
from shskills.config import resolve_dest
from shskills.core.installer import build_plan, execute_plan
from shskills.exceptions import ConfigError
from shskills.models import (
    InstallActionKind,
    InstallResult,
    Manifest,
    SkillFrontmatter,
    SkillInfo,
    SkillSource,
)
from tests.conftest import write_skill

# ---------------------------------------------------------------------------
# config.resolve_dest
# ---------------------------------------------------------------------------


class TestResolveDest:
    def test_known_agent_returns_default(self) -> None:
        assert resolve_dest("claude", None) == Path(".claude/skills")
        assert resolve_dest("codex", None) == Path(".codex/skills")
        assert resolve_dest("gemini", None) == Path(".gemini/skills")
        assert resolve_dest("opencode", None) == Path(".opencode/skills")

    def test_dest_override_wins(self) -> None:
        assert resolve_dest("claude", Path("/tmp/custom")) == Path("/tmp/custom")
        assert resolve_dest("claude", "/tmp/str") == Path("/tmp/str")

    def test_custom_without_dest_raises(self) -> None:
        with pytest.raises(ConfigError, match="--dest"):
            resolve_dest("custom", None)

    def test_unknown_agent_raises(self) -> None:
        with pytest.raises(ConfigError, match="Unknown agent"):
            resolve_dest("grok", None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_skill(tmp_path: Path, name: str = "test_skill") -> SkillInfo:
    skill_dir = write_skill(tmp_path, name)
    return SkillInfo(
        name=name,
        rel_path=name,
        source_rel=f"group/{name}",
        local_path=skill_dir,
        frontmatter=SkillFrontmatter(name=name),
        files=["SKILL.md"],
        content_sha256="a" * 64,
    )


def _make_manifest(dest: Path, skills: dict[str, str] | None = None) -> Manifest:
    """Create a Manifest. skills maps dest_rel -> sha256."""
    from shskills.core.manifest import update_manifest_skill

    m = Manifest(
        agent="claude",
        dest=str(dest),
        source=SkillSource(url="https://example.com/r", ref="main"),
    )
    for dest_rel, sha in (skills or {}).items():
        update_manifest_skill(  # noqa: E501
            m, dest_rel, dest_rel, dest_rel, str(dest / dest_rel), sha, ["SKILL.md"]
        )
    return m


# ---------------------------------------------------------------------------
# build_plan
# ---------------------------------------------------------------------------


class TestBuildPlan:
    def test_new_skills_get_install_action(self, tmp_path: Path) -> None:
        skill = _make_skill(tmp_path / "src")
        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=tmp_path / "dest",
            manifest=None,
            force=False,
            clean=False,
            strict=False,
            dry_run=False,
        )
        assert len(plan.actions) == 1
        assert plan.actions[0].kind == InstallActionKind.INSTALL

    def test_same_sha_gets_skip_action(self, tmp_path: Path) -> None:
        skill = _make_skill(tmp_path / "src")
        dest = tmp_path / "dest"
        manifest = _make_manifest(dest, {skill.rel_path: skill.content_sha256})

        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=dest,
            manifest=manifest,
            force=False,
            clean=False,
            strict=False,
            dry_run=False,
        )
        assert plan.actions[0].kind == InstallActionKind.SKIP

    def test_changed_sha_without_force_gives_conflict(self, tmp_path: Path) -> None:
        skill = _make_skill(tmp_path / "src")
        dest = tmp_path / "dest"
        manifest = _make_manifest(dest, {skill.rel_path: "different_sha"})

        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=dest,
            manifest=manifest,
            force=False,
            clean=False,
            strict=False,
            dry_run=False,
        )
        assert plan.actions[0].kind == InstallActionKind.CONFLICT

    def test_changed_sha_with_force_gives_update(self, tmp_path: Path) -> None:
        skill = _make_skill(tmp_path / "src")
        dest = tmp_path / "dest"
        manifest = _make_manifest(dest, {skill.rel_path: "different_sha"})

        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=dest,
            manifest=manifest,
            force=True,
            clean=False,
            strict=False,
            dry_run=False,
        )
        assert plan.actions[0].kind == InstallActionKind.UPDATE


# ---------------------------------------------------------------------------
# execute_plan
# ---------------------------------------------------------------------------


class TestExecutePlan:
    def test_install_copies_files(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        skill = _make_skill(src)
        manifest = _make_manifest(dest)

        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=dest,
            manifest=manifest,
            force=False,
            clean=False,
            strict=False,
            dry_run=False,
        )
        adapter = ClaudeAdapter()
        result = execute_plan(plan, manifest, adapter)

        assert skill.rel_path in result.installed
        assert (dest / skill.rel_path / "SKILL.md").exists()

    def test_skip_does_not_copy(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        skill = _make_skill(src)
        manifest = _make_manifest(dest, {skill.rel_path: skill.content_sha256})

        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=dest,
            manifest=manifest,
            force=False,
            clean=False,
            strict=False,
            dry_run=False,
        )
        adapter = ClaudeAdapter()
        result = execute_plan(plan, manifest, adapter)

        assert skill.rel_path in result.skipped
        assert not (dest / skill.rel_path).exists()

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        skill = _make_skill(src)
        manifest = _make_manifest(dest)

        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=dest,
            manifest=manifest,
            force=False,
            clean=False,
            strict=False,
            dry_run=True,
        )
        adapter = ClaudeAdapter()
        result = execute_plan(plan, manifest, adapter)

        assert skill.rel_path in result.installed
        assert not (dest / skill.rel_path).exists()

    def test_conflict_recorded_no_overwrite(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        skill = _make_skill(src)
        manifest = _make_manifest(dest, {skill.rel_path: "old_sha"})

        # Pre-create the dest dir to show it's not overwritten
        (dest / skill.rel_path).mkdir(parents=True)
        (dest / skill.rel_path / "SKILL.md").write_text("original")

        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=dest,
            manifest=manifest,
            force=False,
            clean=False,
            strict=False,
            dry_run=False,
        )
        adapter = ClaudeAdapter()
        result = execute_plan(plan, manifest, adapter)

        assert skill.rel_path in result.conflicts
        # original content preserved
        assert (dest / skill.rel_path / "SKILL.md").read_text() == "original"

    def test_clean_removes_orphan(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        skill = _make_skill(src, "new_skill")

        orphan_dir = dest / "orphan_skill"
        orphan_dir.mkdir(parents=True)

        manifest = _make_manifest(
            dest,
            {"orphan_skill": "sha_orphan"},
        )
        # Add orphan_skill to manifest
        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=dest,
            manifest=manifest,
            force=False,
            clean=True,
            strict=False,
            dry_run=False,
        )
        adapter = ClaudeAdapter()
        result = execute_plan(plan, manifest, adapter)

        assert "orphan_skill" in result.cleaned
        assert not orphan_dir.exists()

    def test_update_overwrites_files(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        skill = _make_skill(src)

        # Pre-install with a different sha to trigger UPDATE
        manifest = _make_manifest(dest, {skill.rel_path: "old_different_sha"})
        (dest / skill.rel_path).mkdir(parents=True)
        (dest / skill.rel_path / "SKILL.md").write_text("old content")

        plan = build_plan(
            skills=[skill],
            source=SkillSource(url="https://x.com/r", ref="main"),
            agent="claude",
            dest=dest,
            manifest=manifest,
            force=True,
            clean=False,
            strict=False,
            dry_run=False,
        )
        adapter = ClaudeAdapter()
        result = execute_plan(plan, manifest, adapter)

        assert skill.rel_path in result.updated
        # Content now matches source
        src_content = (src / skill.name / "SKILL.md").read_text()
        dest_content = (dest / skill.rel_path / "SKILL.md").read_text()
        assert dest_content == src_content


# ---------------------------------------------------------------------------
# install() public API — mocked fetch
# ---------------------------------------------------------------------------


class TestInstallPublicApi:
    def test_returns_empty_result_when_no_skills_found(
        self, tmp_path: Path
    ) -> None:
        from shskills import install

        with patch("shskills.core.installer.fetch_skills_tree") as mock_fetch:
            mock_fetch.return_value.__enter__ = lambda s: tmp_path / "SKILLS"
            mock_fetch.return_value.__exit__ = lambda *a: False
            (tmp_path / "SKILLS").mkdir()

            result = install(
                url="https://example.com/repo",
                agent="claude",
                dest=tmp_path / "dest",
            )

        assert result == InstallResult()

    def test_strict_raises_on_conflict(self, tmp_path: Path) -> None:
        from shskills import install
        from shskills.exceptions import InstallError

        src = tmp_path / "src"
        dest = tmp_path / "dest"
        skill = _make_skill(src, "skill_a")

        # Pre-install with a different sha so a conflict is guaranteed
        from shskills.core.manifest import write_manifest
        manifest = _make_manifest(dest, {skill.rel_path: "old_sha"})
        write_manifest(dest, manifest)

        skills_root = tmp_path / "SKILLS"
        skills_root.mkdir()
        (skills_root / "skill_a").mkdir()
        (skills_root / "skill_a" / "SKILL.md").write_text(
            (src / "skill_a" / "SKILL.md").read_text()
        )

        with patch("shskills.core.installer.fetch_skills_tree") as mock_ctx:
            ctx = MagicMock()
            ctx.__enter__ = lambda s: skills_root
            ctx.__exit__ = lambda *a: False
            mock_ctx.return_value = ctx

            with pytest.raises(InstallError, match="conflict"):
                install(
                    url="https://example.com/repo",
                    agent="claude",
                    dest=dest,
                    strict=True,
                )


# ---------------------------------------------------------------------------
# doctor() public API
# ---------------------------------------------------------------------------


class TestDoctorPublicApi:
    def test_healthy_when_files_match(self, tmp_path: Path) -> None:
        from shskills import doctor
        from shskills.core.manifest import update_manifest_skill, write_manifest
        from shskills.core.validator import compute_skill_sha256, list_skill_files

        dest = tmp_path / "dest"
        skill_dir = dest / "group" / "my_skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: my_skill\n---\n")

        files = list_skill_files(skill_dir)
        sha = compute_skill_sha256(skill_dir, files)

        manifest = _make_manifest(dest)
        update_manifest_skill(
            manifest, "group/my_skill", "my_skill",
            "group/my_skill", str(dest / "group" / "my_skill"), sha, files
        )
        write_manifest(dest, manifest)

        report = doctor(agent="claude", dest=dest)
        assert report.healthy
        assert report.installed_count == 1

    def test_error_when_skill_dir_missing(self, tmp_path: Path) -> None:
        from shskills import doctor
        from shskills.core.manifest import update_manifest_skill, write_manifest
        from shskills.models import DoctorSeverity

        dest = tmp_path / "dest"
        manifest = _make_manifest(dest)
        update_manifest_skill(
            manifest, "missing/skill", "skill",
            "missing/skill", str(dest / "missing" / "skill"), "sha123", ["SKILL.md"]
        )
        write_manifest(dest, manifest)

        report = doctor(agent="claude", dest=dest)
        assert not report.healthy
        assert any(i.severity == DoctorSeverity.ERROR for i in report.issues)

    def test_warning_when_sha_mismatch(self, tmp_path: Path) -> None:
        from shskills import doctor
        from shskills.core.manifest import update_manifest_skill, write_manifest
        from shskills.models import DoctorSeverity

        dest = tmp_path / "dest"
        skill_dir = dest / "my_skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("original content")

        manifest = _make_manifest(dest)
        update_manifest_skill(
            manifest, "my_skill", "my_skill",
            "my_skill", str(dest / "my_skill"), "wrong_sha", ["SKILL.md"]
        )
        write_manifest(dest, manifest)

        # Modify the file after recording manifest
        (skill_dir / "SKILL.md").write_text("modified content")

        report = doctor(agent="claude", dest=dest)
        assert any(i.severity == DoctorSeverity.WARNING for i in report.issues)
