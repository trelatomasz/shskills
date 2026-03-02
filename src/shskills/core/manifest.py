"""Read and write the .shskills-manifest.json file atomically."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from shskills.config import MANIFEST_FILENAME
from shskills.exceptions import ManifestError
from shskills.models import InstalledSkill, Manifest

# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_manifest(dest: Path) -> Manifest | None:
    """Read the manifest from *dest*, returning None when it does not exist.

    Raises ManifestError if the file exists but cannot be parsed.
    """
    manifest_path = dest / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None

    try:
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return Manifest.model_validate(data)
    except Exception as exc:
        raise ManifestError(
            f"Failed to parse manifest at '{manifest_path}': {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def write_manifest(dest: Path, manifest: Manifest) -> None:
    """Atomically write *manifest* to *dest*/.shskills-manifest.json.

    Uses write-to-temp + rename so a crash cannot leave a partial file.

    Raises ManifestError on I/O failure.
    """
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path = dest / MANIFEST_FILENAME

    payload = manifest.model_dump(mode="json")
    serialized = json.dumps(payload, indent=2, default=str)

    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(dest), prefix=".manifest-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(serialized)
            os.replace(tmp_path, str(manifest_path))
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
    except Exception as exc:
        raise ManifestError(
            f"Failed to write manifest to '{manifest_path}': {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Helpers used by installer / doctor
# ---------------------------------------------------------------------------


def update_manifest_skill(
    manifest: Manifest,
    dest_rel: str,
    skill_name: str,
    source_path: str,
    dest_path: str,
    sha256: str,
    files: list[str],
) -> None:
    """Upsert an InstalledSkill record into *manifest* in-place."""
    manifest.skills[dest_rel] = InstalledSkill(
        name=skill_name,
        source_path=source_path,
        dest_path=dest_path,
        content_sha256=sha256,
        installed_at=datetime.now(UTC),
        files=files,
    )
    manifest.updated_at = datetime.now(UTC)


def remove_manifest_skill(manifest: Manifest, dest_rel: str) -> None:
    """Remove an InstalledSkill record from *manifest* in-place."""
    manifest.skills.pop(dest_rel, None)
    manifest.updated_at = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Public API: installed_skills
# ---------------------------------------------------------------------------


def installed_skills(
    agent: str, dest: Path | None = None
) -> list[InstalledSkill]:
    """Return all skills recorded in the manifest at *dest*.

    Args:
        agent:  Agent name used to resolve the default destination.
        dest:   Override destination path.

    Returns:
        List of InstalledSkill records, or empty list if no manifest exists.
    """
    from shskills.config import resolve_dest  # local import avoids circular

    dest_path = resolve_dest(agent, dest)
    manifest = read_manifest(dest_path)
    if manifest is None:
        return []
    return list(manifest.skills.values())
