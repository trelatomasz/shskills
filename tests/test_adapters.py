"""Unit tests for shskills.adapters.*"""

from __future__ import annotations

from pathlib import Path

import pytest

from shskills.adapters import get_adapter
from shskills.adapters.claude import ClaudeAdapter
from shskills.adapters.codex import CodexAdapter
from shskills.adapters.custom import CustomAdapter
from shskills.adapters.gemini import GeminiAdapter
from shskills.adapters.opencode import OpenCodeAdapter
from shskills.models import SkillFrontmatter, SkillInfo


def _make_skill(tmp_path: Path, name: str = "test_skill") -> SkillInfo:
    """Build a SkillInfo backed by real files in tmp_path."""
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test\n---\n# {name}\n",
        encoding="utf-8",
    )
    (skill_dir / "helper.txt").write_text("helper content", encoding="utf-8")
    return SkillInfo(
        name=name,
        rel_path=name,
        source_rel=f"group/{name}",
        local_path=skill_dir,
        frontmatter=SkillFrontmatter(name=name, description="test"),
        files=["SKILL.md", "helper.txt"],
        content_sha256="0" * 64,
    )


def _make_skill_with_subdir(tmp_path: Path, name: str = "test_skill") -> SkillInfo:
    """Build a SkillInfo that contains files in a subdirectory."""
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test\n---\n# {name}\n",
        encoding="utf-8",
    )
    hooks = skill_dir / "hooks"
    hooks.mkdir()
    (hooks / "run.py").write_text("print('hello')", encoding="utf-8")
    return SkillInfo(
        name=name,
        rel_path=name,
        source_rel=f"group/{name}",
        local_path=skill_dir,
        frontmatter=SkillFrontmatter(name=name, description="test"),
        files=["SKILL.md", "hooks/run.py"],
        content_sha256="0" * 64,
    )


# ---------------------------------------------------------------------------
# get_adapter registry
# ---------------------------------------------------------------------------


class TestGetAdapter:
    def test_claude(self) -> None:
        assert isinstance(get_adapter("claude"), ClaudeAdapter)

    def test_codex(self) -> None:
        assert isinstance(get_adapter("codex"), CodexAdapter)

    def test_gemini(self) -> None:
        assert isinstance(get_adapter("gemini"), GeminiAdapter)

    def test_opencode(self) -> None:
        assert isinstance(get_adapter("opencode"), OpenCodeAdapter)

    def test_custom(self) -> None:
        assert isinstance(get_adapter("custom"), CustomAdapter)

    def test_unknown_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="No adapter"):
            get_adapter("unknown_agent")


# ---------------------------------------------------------------------------
# AgentAdapter.preprocess (via ClaudeAdapter)
# ---------------------------------------------------------------------------


class TestAdapterPreprocess:
    def test_copies_all_files(self, tmp_path: Path) -> None:
        skill = _make_skill(tmp_path / "src")
        dest_dir = tmp_path / "dest" / skill.name

        adapter = ClaudeAdapter()
        written = adapter.preprocess(skill, dest_dir)

        assert set(written) == {"SKILL.md", "helper.txt"}
        assert (dest_dir / "SKILL.md").exists()
        assert (dest_dir / "helper.txt").exists()

    def test_content_is_preserved(self, tmp_path: Path) -> None:
        skill = _make_skill(tmp_path / "src")
        dest_dir = tmp_path / "dest" / skill.name

        adapter = ClaudeAdapter()
        adapter.preprocess(skill, dest_dir)

        original = (skill.local_path / "SKILL.md").read_bytes()
        copied = (dest_dir / "SKILL.md").read_bytes()
        assert original == copied

    def test_creates_dest_directory(self, tmp_path: Path) -> None:
        skill = _make_skill(tmp_path / "src")
        dest_dir = tmp_path / "new" / "nested" / "dest"

        adapter = ClaudeAdapter()
        adapter.preprocess(skill, dest_dir)

        assert dest_dir.is_dir()

    def test_copies_nested_files(self, tmp_path: Path) -> None:
        skill = _make_skill_with_subdir(tmp_path / "src")
        dest_dir = tmp_path / "dest" / skill.name

        adapter = ClaudeAdapter()
        written = adapter.preprocess(skill, dest_dir)

        assert "hooks/run.py" in written
        assert (dest_dir / "hooks" / "run.py").exists()

    def test_nested_file_content_preserved(self, tmp_path: Path) -> None:
        skill = _make_skill_with_subdir(tmp_path / "src")
        dest_dir = tmp_path / "dest" / skill.name

        adapter = ClaudeAdapter()
        adapter.preprocess(skill, dest_dir)

        original = (skill.local_path / "hooks" / "run.py").read_bytes()
        copied = (dest_dir / "hooks" / "run.py").read_bytes()
        assert original == copied

    def test_creates_nested_subdirectories(self, tmp_path: Path) -> None:
        skill = _make_skill_with_subdir(tmp_path / "src")
        dest_dir = tmp_path / "new" / "nested" / "dest"

        adapter = ClaudeAdapter()
        adapter.preprocess(skill, dest_dir)

        assert (dest_dir / "hooks").is_dir()
        assert (dest_dir / "hooks" / "run.py").is_file()

    def test_overwrite_on_second_call(self, tmp_path: Path) -> None:
        skill = _make_skill(tmp_path / "src")
        dest_dir = tmp_path / "dest" / skill.name

        adapter = ClaudeAdapter()
        adapter.preprocess(skill, dest_dir)

        # Modify source and call again — should overwrite
        new_content = b"updated content"
        (skill.local_path / "SKILL.md").write_bytes(new_content)
        adapter.preprocess(skill, dest_dir)

        assert (dest_dir / "SKILL.md").read_bytes() == new_content


# ---------------------------------------------------------------------------
# agent_name properties
# ---------------------------------------------------------------------------


class TestAgentNames:
    def test_all_names(self) -> None:
        assert ClaudeAdapter().agent_name == "claude"
        assert CodexAdapter().agent_name == "codex"
        assert GeminiAdapter().agent_name == "gemini"
        assert OpenCodeAdapter().agent_name == "opencode"
        assert CustomAdapter().agent_name == "custom"
