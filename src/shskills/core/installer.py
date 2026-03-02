"""Orchestrates the full install lifecycle."""

from __future__ import annotations

import logging
import shutil  # used by execute_plan --clean path
from datetime import datetime, timezone
from pathlib import Path

from shskills.adapters.base import AgentAdapter
from shskills.config import DEFAULT_REF, resolve_dest
from shskills.core.fetcher import fetch_skills_tree
from shskills.core.manifest import (
    read_manifest,
    remove_manifest_skill,
    update_manifest_skill,
    write_manifest,
)
from shskills.core.planner import discover_skills
from shskills.exceptions import InstallError
from shskills.models import (
    DoctorIssue,
    DoctorReport,
    DoctorSeverity,
    InstallAction,
    InstallActionKind,
    InstallPlan,
    InstallResult,
    Manifest,
    SkillInfo,
    SkillSource,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plan building
# ---------------------------------------------------------------------------


def _action_for_skill(
    skill: SkillInfo,
    dest_rel: str,
    manifest: Manifest | None,
    force: bool,
) -> InstallAction:
    """Determine the InstallAction for a single skill against the current manifest."""
    if manifest is None or dest_rel not in manifest.skills:
        return InstallAction(
            skill=skill,
            dest_rel=dest_rel,
            kind=InstallActionKind.INSTALL,
        )

    existing = manifest.skills[dest_rel]
    if existing.content_sha256 == skill.content_sha256:
        return InstallAction(
            skill=skill,
            dest_rel=dest_rel,
            kind=InstallActionKind.SKIP,
            reason="already up-to-date",
        )

    if force:
        return InstallAction(
            skill=skill,
            dest_rel=dest_rel,
            kind=InstallActionKind.UPDATE,
            reason="hash changed, --force specified",
        )

    return InstallAction(
        skill=skill,
        dest_rel=dest_rel,
        kind=InstallActionKind.CONFLICT,
        reason="hash changed; use --force to overwrite",
    )


def build_plan(
    skills: list[SkillInfo],
    source: SkillSource,
    agent: str,
    dest: Path,
    manifest: Manifest | None,
    force: bool,
    clean: bool,
    strict: bool,
    dry_run: bool,
) -> InstallPlan:
    """Combine discovered skills + existing manifest into an InstallPlan."""
    actions: list[InstallAction] = []
    for skill in skills:
        action = _action_for_skill(skill, skill.rel_path, manifest, force)
        actions.append(action)

    return InstallPlan(
        source=source,
        agent=agent,
        dest=dest,
        actions=actions,
        dry_run=dry_run,
        force=force,
        clean=clean,
        strict=strict,
    )


# ---------------------------------------------------------------------------
# Plan execution
# ---------------------------------------------------------------------------


def execute_plan(
    plan: InstallPlan,
    manifest: Manifest,
    adapter: AgentAdapter,
    verbose: bool = False,
) -> InstallResult:
    """Execute all actions in *plan*, update *manifest* in-place, return result."""
    result = InstallResult()

    for action in plan.actions:
        skill = action.skill
        dest_dir = plan.dest / action.dest_rel
        dest_path_str = str(plan.dest / action.dest_rel)

        if action.kind == InstallActionKind.SKIP:
            result.skipped.append(action.dest_rel)
            if verbose:
                logger.info("skip  %s (%s)", action.dest_rel, action.reason)
            continue

        if action.kind == InstallActionKind.CONFLICT:
            result.conflicts.append(action.dest_rel)
            logger.warning("conflict %s: %s", action.dest_rel, action.reason)
            continue

        # INSTALL or UPDATE
        if plan.dry_run:
            label = "install" if action.kind == InstallActionKind.INSTALL else "update"
            logger.info("[dry-run] %s  %s", label, action.dest_rel)
            if action.kind == InstallActionKind.INSTALL:
                result.installed.append(action.dest_rel)
            else:
                result.updated.append(action.dest_rel)
            continue

        try:
            adapter.preprocess(skill, dest_dir)
        except OSError as exc:
            result.errors.append(f"{action.dest_rel}: {exc}")
            logger.error("error installing '%s': %s", action.dest_rel, exc)
            continue

        update_manifest_skill(
            manifest,
            dest_rel=action.dest_rel,
            skill_name=skill.name,
            source_path=skill.source_rel,
            dest_path=dest_path_str,
            sha256=skill.content_sha256,
            files=skill.files,
        )

        if action.kind == InstallActionKind.INSTALL:
            result.installed.append(action.dest_rel)
            logger.info("installed %s", action.dest_rel)
        else:
            result.updated.append(action.dest_rel)
            logger.info("updated   %s", action.dest_rel)

    # --clean: remove orphaned skills (in manifest but not in current source)
    if plan.clean and not plan.dry_run:
        installed_keys = {a.dest_rel for a in plan.actions}
        for key in list(manifest.skills.keys()):
            if key not in installed_keys:
                orphan_dir = plan.dest / key
                if orphan_dir.exists():
                    shutil.rmtree(str(orphan_dir))
                remove_manifest_skill(manifest, key)
                result.cleaned.append(key)
                logger.info("cleaned   %s (orphaned)", key)

    return result


# ---------------------------------------------------------------------------
# Public API: install
# ---------------------------------------------------------------------------


def install(
    url: str,
    agent: str,
    subpath: str | None = None,
    ref: str = DEFAULT_REF,
    dest: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    clean: bool = False,
    strict: bool = False,
    verbose: bool = False,
) -> InstallResult:
    """Fetch and install skills from a remote repository.

    Args:
        url:      Git repository URL.
        agent:    Target agent (``claude``, ``codex``, ``gemini``, ``opencode``,
                  or ``custom``).
        subpath:  Optional path filter relative to ``SKILLS/``.
        ref:      Branch, tag, or commit SHA (default: ``main``).
        dest:     Override the default destination directory.
        dry_run:  Plan but do not write any files.
        force:    Overwrite skills whose content has changed.
        clean:    Remove orphaned skills that are no longer in the source.
        strict:   Abort on any conflict instead of warning.
        verbose:  Emit INFO-level log messages for skipped skills too.

    Returns:
        InstallResult summarising what happened.

    Raises:
        ConfigError:   Invalid agent or missing --dest for custom agent.
        FetchError:    Remote repository could not be fetched.
        InstallError:  strict=True and conflicts were detected.
        ManifestError: Manifest could not be read or written.
    """
    from shskills.adapters import get_adapter

    dest_path = resolve_dest(agent, dest)
    source = SkillSource(url=url, ref=ref, subpath=subpath)
    adapter = get_adapter(agent)

    existing_manifest = read_manifest(dest_path)

    with fetch_skills_tree(source) as skills_root:
        skills = discover_skills(skills_root, source.subpath)

        if not skills:
            logger.warning(
                "No skills found at '%s/%s' in '%s'",
                "SKILLS",
                subpath or "",
                url,
            )
            return InstallResult()

        plan = build_plan(
            skills=skills,
            source=source,
            agent=agent,
            dest=dest_path,
            manifest=existing_manifest,
            force=force,
            clean=clean,
            strict=strict,
            dry_run=dry_run,
        )

        conflict_keys = [a.dest_rel for a in plan.actions if a.kind == InstallActionKind.CONFLICT]
        if strict and conflict_keys:
            raise InstallError(
                f"Strict mode: {len(conflict_keys)} conflict(s) detected: "
                + ", ".join(conflict_keys)
            )

        # Prepare or create manifest
        working_manifest: Manifest = existing_manifest or Manifest(
            agent=agent,
            dest=str(dest_path),
            source=source,
        )
        # Always update the source reference in the manifest
        working_manifest.source = source

        result = execute_plan(plan, working_manifest, adapter, verbose=verbose)

        if not dry_run and (result.installed or result.updated or result.cleaned):
            write_manifest(dest_path, working_manifest)

    return result


# ---------------------------------------------------------------------------
# Public API: uninstall
# ---------------------------------------------------------------------------


def _parse_skill_key(dest_rel: str) -> tuple[str, str]:
    """Split 'prefix__skillname' → (prefix, skillname).

    If there is no ``__`` separator the whole string is treated as the skill
    name and the prefix is an empty string.
    """
    idx = dest_rel.find("__")
    if idx == -1:
        return "", dest_rel
    return dest_rel[:idx], dest_rel[idx + 2:]


def _key_matches(dest_rel: str, name: str | None, prefix: str | None) -> bool:
    prefix_part, skill_part = _parse_skill_key(dest_rel)
    if name is not None and skill_part != name:
        return False
    if prefix is not None and not prefix_part.startswith(prefix):
        return False
    return True


def uninstall(
    agent: str,
    name: str | None = None,
    prefix: str | None = None,
    dest: Path | None = None,
    dry_run: bool = False,
) -> InstallResult:
    """Remove installed skills matching *name* and/or *prefix*.

    Args:
        agent:    Target agent (determines default destination).
        name:     Skill name to match (the part after ``__``).
        prefix:   Prefix filter; matches any installed-skill key whose prefix
                  *starts with* this string.
        dest:     Override the default destination directory.
        dry_run:  Plan without removing any files.

    Returns:
        InstallResult with ``cleaned`` listing removed skills and ``errors``
        listing any I/O failures.

    Raises:
        ConfigError:   Invalid agent or missing --dest for custom agent.
        InstallError:  *name* matches skills under multiple prefixes and
                       *prefix* was not supplied to disambiguate.
        ManifestError: Manifest could not be read or written.
    """
    dest_path = resolve_dest(agent, dest)
    manifest = read_manifest(dest_path)
    if manifest is None:
        return InstallResult()

    matches: dict[str, object] = {
        k: v
        for k, v in manifest.skills.items()
        if _key_matches(k, name, prefix)
    }

    if not matches:
        return InstallResult()

    # Ambiguity guard: --name without --prefix must resolve to a single prefix.
    if name is not None and prefix is None:
        unique_prefixes = {_parse_skill_key(k)[0] for k in matches}
        if len(unique_prefixes) > 1:
            raise InstallError(
                f"Name '{name}' is ambiguous — found skills under multiple prefixes: "
                + ", ".join(sorted(unique_prefixes))
                + ". Re-run with --prefix to narrow the selection."
            )

    result = InstallResult()

    for dest_rel in list(matches):
        if dry_run:
            result.cleaned.append(dest_rel)
            continue
        try:
            skill_dir = dest_path / dest_rel
            if skill_dir.exists():
                shutil.rmtree(str(skill_dir))
            remove_manifest_skill(manifest, dest_rel)
            result.cleaned.append(dest_rel)
            logger.info("removed   %s", dest_rel)
        except OSError as exc:
            result.errors.append(f"{dest_rel}: {exc}")
            logger.error("error removing '%s': %s", dest_rel, exc)

    if not dry_run and result.cleaned:
        write_manifest(dest_path, manifest)

    return result


# ---------------------------------------------------------------------------
# Public API: doctor
# ---------------------------------------------------------------------------


def doctor(agent: str, dest: Path | None = None) -> DoctorReport:
    """Check the health of installed skills for *agent*.

    Verifies that:
    - The destination directory exists.
    - The manifest file is readable.
    - Each recorded skill directory is present on disk.
    - Each recorded skill's SHA-256 matches the installed files.

    Returns a DoctorReport with any issues found.
    """
    from shskills.core.validator import compute_skill_sha256, list_skill_files

    dest_path = resolve_dest(agent, dest)
    report = DoctorReport(agent=agent, dest=dest_path)

    if not dest_path.exists():
        report.issues.append(
            DoctorIssue(
                severity=DoctorSeverity.WARNING,
                message=f"Destination directory '{dest_path}' does not exist.",
            )
        )
        return report

    from shskills.core.manifest import read_manifest as _read
    from shskills.exceptions import ManifestError

    try:
        manifest = _read(dest_path)
    except ManifestError as exc:
        report.issues.append(
            DoctorIssue(severity=DoctorSeverity.ERROR, message=str(exc))
        )
        return report

    if manifest is None:
        report.issues.append(
            DoctorIssue(
                severity=DoctorSeverity.INFO,
                message="No manifest found. Run 'shskills install' first.",
            )
        )
        return report

    report.installed_count = len(manifest.skills)

    for dest_rel, skill in manifest.skills.items():
        skill_dir = dest_path / dest_rel
        if not skill_dir.exists():
            report.issues.append(
                DoctorIssue(
                    severity=DoctorSeverity.ERROR,
                    message=f"Skill '{dest_rel}' is recorded in manifest but directory is missing.",
                )
            )
            continue

        try:
            actual_files = list_skill_files(skill_dir)
            actual_sha = compute_skill_sha256(skill_dir, actual_files)
        except OSError as exc:
            report.issues.append(
                DoctorIssue(
                    severity=DoctorSeverity.ERROR,
                    message=f"Skill '{dest_rel}': could not read files: {exc}",
                )
            )
            continue

        if actual_sha != skill.content_sha256:
            report.issues.append(
                DoctorIssue(
                    severity=DoctorSeverity.WARNING,
                    message=(
                        f"Skill '{dest_rel}' has been modified locally "
                        f"(expected {skill.content_sha256[:8]}, got {actual_sha[:8]})."
                    ),
                )
            )

    return report
