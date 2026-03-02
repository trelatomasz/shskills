"""End-to-end integration tests for the shskills install workflow.

These tests create a real local git repository with a SKILLS/ tree,
run the installer against it, and verify the resulting directory layout
and manifest correctness.

Requires: git >= 2.28 (for ``git init -b <branch>``)
"""

from __future__ import annotations

from pathlib import Path

from shskills import install
from shskills.config import MANIFEST_FILENAME
from shskills.core.manifest import read_manifest

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _url(repo: Path) -> str:
    return f"file://{repo}"


# ---------------------------------------------------------------------------
# Basic install
# ---------------------------------------------------------------------------


class TestBasicInstall:
    def test_installs_all_skills(self, git_skills_repo: Path, tmp_path: Path) -> None:
        dest = tmp_path / ".claude" / "skills"

        result = install(url=_url(git_skills_repo), agent="claude", dest=dest)

        assert not result.errors
        assert not result.conflicts
        assert len(result.installed) == 2

    def test_skill_files_are_present(self, git_skills_repo: Path, tmp_path: Path) -> None:
        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        assert (dest / "common__welcome_note" / "SKILL.md").exists()
        assert (dest / "aws__scale_up" / "SKILL.md").exists()

    def test_manifest_is_written(self, git_skills_repo: Path, tmp_path: Path) -> None:
        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        manifest = read_manifest(dest)
        assert manifest is not None
        assert manifest.agent == "claude"
        assert len(manifest.skills) == 2
        assert "common__welcome_note" in manifest.skills
        assert "aws__scale_up" in manifest.skills

    def test_manifest_records_source_url(self, git_skills_repo: Path, tmp_path: Path) -> None:
        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        manifest = read_manifest(dest)
        assert manifest is not None
        assert manifest.source.url == _url(git_skills_repo)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_run_skips_everything(self, git_skills_repo: Path, tmp_path: Path) -> None:
        dest = tmp_path / ".claude" / "skills"

        r1 = install(url=_url(git_skills_repo), agent="claude", dest=dest)
        assert len(r1.installed) == 2

        r2 = install(url=_url(git_skills_repo), agent="claude", dest=dest)
        assert r2.installed == []
        assert r2.updated == []
        assert len(r2.skipped) == 2

    def test_manifest_sha_stable_across_runs(
        self, git_skills_repo: Path, tmp_path: Path
    ) -> None:
        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        sha1 = read_manifest(dest).skills["common__welcome_note"].content_sha256  # type: ignore[union-attr]

        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        sha2 = read_manifest(dest).skills["common__welcome_note"].content_sha256  # type: ignore[union-attr]
        assert sha1 == sha2


# ---------------------------------------------------------------------------
# Subpath install
# ---------------------------------------------------------------------------


class TestSubpathInstall:
    def test_installs_only_matching_skills(
        self, git_skills_repo: Path, tmp_path: Path
    ) -> None:
        dest = tmp_path / ".claude" / "skills"
        result = install(
            url=_url(git_skills_repo),
            agent="claude",
            dest=dest,
            subpath="common",
        )

        assert len(result.installed) == 1
        assert (dest / "welcome_note" / "SKILL.md").exists()
        assert not (dest / "aws").exists()

    def test_dest_rel_strips_subpath_prefix(
        self, git_skills_repo: Path, tmp_path: Path
    ) -> None:
        dest = tmp_path / ".claude" / "skills"
        install(
            url=_url(git_skills_repo),
            agent="claude",
            dest=dest,
            subpath="common",
        )

        manifest = read_manifest(dest)
        assert manifest is not None
        # Key should be "welcome_note", not "common/welcome_note"
        assert "welcome_note" in manifest.skills

    def test_single_skill_subpath(self, git_skills_repo: Path, tmp_path: Path) -> None:
        dest = tmp_path / ".claude" / "skills"
        result = install(
            url=_url(git_skills_repo),
            agent="claude",
            dest=dest,
            subpath="common/welcome_note",
        )

        assert len(result.installed) == 1
        assert (dest / "welcome_note" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# Conflict handling
# ---------------------------------------------------------------------------


class TestConflicts:
    def test_conflict_when_source_updated(
        self, git_skills_repo: Path, tmp_path: Path
    ) -> None:
        """Conflict is triggered when the *source* skill changes between installs."""
        from tests.conftest import _git

        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        # Update the skill in the source repo (new commit)
        skill_file = git_skills_repo / "SKILLS" / "common" / "welcome_note" / "SKILL.md"
        skill_file.write_text("---\nname: welcome_note\n---\n# updated source\n")
        _git(git_skills_repo, "add", ".")
        _git(git_skills_repo, "commit", "-m", "update welcome_note")

        result = install(url=_url(git_skills_repo), agent="claude", dest=dest)
        assert "common__welcome_note" in result.conflicts

    def test_force_resolves_conflict(
        self, git_skills_repo: Path, tmp_path: Path
    ) -> None:
        """--force overwrites when the source skill has changed."""
        from tests.conftest import _git

        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        # Update source
        skill_file = git_skills_repo / "SKILLS" / "common" / "welcome_note" / "SKILL.md"
        skill_file.write_text("---\nname: welcome_note\n---\n# updated source\n")
        _git(git_skills_repo, "add", ".")
        _git(git_skills_repo, "commit", "-m", "update welcome_note")

        result = install(
            url=_url(git_skills_repo), agent="claude", dest=dest, force=True
        )
        assert "common__welcome_note" in result.updated
        assert result.conflicts == []


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_no_files_written(self, git_skills_repo: Path, tmp_path: Path) -> None:
        dest = tmp_path / ".claude" / "skills"
        result = install(
            url=_url(git_skills_repo), agent="claude", dest=dest, dry_run=True
        )

        assert len(result.installed) == 2
        assert not dest.exists()

    def test_manifest_not_written(self, git_skills_repo: Path, tmp_path: Path) -> None:
        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest, dry_run=True)

        assert read_manifest(dest) is None


# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------


class TestClean:
    def test_orphaned_skills_removed(
        self, git_skills_repo: Path, tmp_path: Path
    ) -> None:
        dest = tmp_path / ".claude" / "skills"

        # Install all skills (common + aws)
        install(url=_url(git_skills_repo), agent="claude", dest=dest)
        assert (dest / "aws__scale_up").exists()

        # Re-install with --subpath common --clean (aws/scale_up becomes orphaned)
        result = install(
            url=_url(git_skills_repo),
            agent="claude",
            dest=dest,
            subpath="common",
            clean=True,
            force=True,
        )

        assert "aws__scale_up" in result.cleaned
        assert not (dest / "aws__scale_up").exists()

    def test_no_clean_without_flag(
        self, git_skills_repo: Path, tmp_path: Path
    ) -> None:
        """Without --clean a second install never removes anything."""
        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        result = install(url=_url(git_skills_repo), agent="claude", dest=dest)

        assert result.cleaned == []
        assert (dest / "aws__scale_up").exists()
        assert (dest / "common__welcome_note").exists()


# ---------------------------------------------------------------------------
# E2E layout structure test
# ---------------------------------------------------------------------------


class TestSubdirectoryFiles:
    def test_installs_nested_files(self, tmp_path: Path) -> None:
        """Skills with subdirectory files (e.g. hooks/) are fully copied."""
        import subprocess

        repo = tmp_path / "repo_with_hooks"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@shskills.io"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "shskills-test"],
            check=True, capture_output=True,
        )

        from tests.conftest import write_skill

        write_skill(
            repo / "SKILLS" / "common",
            "prompt_skill",
            extra_files={"hooks/run.py": "print('hello from hook')"},
        )

        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "add skill with hooks"],
            check=True, capture_output=True,
        )

        dest = tmp_path / ".claude" / "skills"
        result = install(url=f"file://{repo}", agent="claude", dest=dest)

        assert not result.errors
        assert len(result.installed) == 1
        assert (dest / "common__prompt_skill" / "SKILL.md").exists()
        assert (dest / "common__prompt_skill" / "hooks" / "run.py").exists()
        assert (
            (dest / "common__prompt_skill" / "hooks" / "run.py").read_text()
            == "print('hello from hook')"
        )

    def test_nested_files_in_manifest_sha(self, tmp_path: Path) -> None:
        """Manifest SHA-256 covers subdirectory files so changes are detected."""
        import subprocess

        repo = tmp_path / "repo_sha"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@shskills.io"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "shskills-test"],
            check=True, capture_output=True,
        )

        from tests.conftest import write_skill

        write_skill(
            repo / "SKILLS",
            "hook_skill",
            extra_files={"hooks/run.py": "v1"},
        )
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "v1"],
            check=True, capture_output=True,
        )

        dest = tmp_path / "dest"
        install(url=f"file://{repo}", agent="claude", dest=dest)
        sha1 = read_manifest(dest).skills["hook_skill"].content_sha256  # type: ignore[union-attr]

        # Modify the nested file in source
        hook_file = repo / "SKILLS" / "hook_skill" / "hooks" / "run.py"
        hook_file.write_text("v2")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "v2"],
            check=True, capture_output=True,
        )

        result = install(url=f"file://{repo}", agent="claude", dest=dest)
        assert "hook_skill" in result.conflicts

        result2 = install(url=f"file://{repo}", agent="claude", dest=dest, force=True)
        assert "hook_skill" in result2.updated
        sha2 = read_manifest(dest).skills["hook_skill"].content_sha256  # type: ignore[union-attr]
        assert sha1 != sha2


class TestLayoutStructure:
    def test_directory_layout(self, git_skills_repo: Path, tmp_path: Path) -> None:
        """Full structural verification of the installation layout."""
        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        # Manifest file
        assert (dest / MANIFEST_FILENAME).exists()

        # Skill directories with SKILL.md
        assert (dest / "common__welcome_note" / "SKILL.md").is_file()
        assert (dest / "aws__scale_up" / "SKILL.md").is_file()

        # No temp files left over
        assert not list(dest.glob(".manifest-*.tmp"))

    def test_manifest_skill_entries_valid(
        self, git_skills_repo: Path, tmp_path: Path
    ) -> None:
        dest = tmp_path / ".claude" / "skills"
        install(url=_url(git_skills_repo), agent="claude", dest=dest)

        manifest = read_manifest(dest)
        assert manifest is not None

        for dest_rel, skill in manifest.skills.items():
            # dest_path should be a string containing the dest_rel
            assert dest_rel in skill.dest_path
            # SHA-256 should be 64 hex chars
            assert len(skill.content_sha256) == 64
            # installed_at should be timezone-aware
            assert skill.installed_at.tzinfo is not None
