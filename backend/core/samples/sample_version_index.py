"""Sample version ledger: per-snapshot index keyed by ``file_hash``.

Each registration copies the source file under ``snapshots/`` (mirroring the
``docx/`` layout) and writes a ``sample_version_index.json`` **inside** the
immutable snapshot directory. No global index file; the per-snapshot file is
the authoritative record for that version.

Layout::

    docx/zh/clinical_program_001_vt8802/VT8802.docx
        editable working copy

    snapshots/docx/zh/clinical_program_001_vt8802/sha256_<prefix>/
        VT8802.docx                 immutable snapshot
        sample_version_index.json   auto-generated, describes this snapshot

To look up an immutable snapshot by ``file_hash``: derive the dir name from the
hash prefix, then scan ``snapshots/`` for a matching ``sha256_<prefix>/``
directory.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from core.document.doc_identity import (
    FILE_HASH_PREFIX,
    compute_file_hash,
    utc_created_at,
)
from runtime.io import load_json, save_json
from runtime.run_provenance import find_git_root, get_git_provenance

SAMPLE_VERSION_INDEX_SCHEMA_VERSION = "0.1.0"
SAMPLE_VERSION_INDEX_KIND = "sample_version_index"
SAMPLE_VERSION_INDEX_FILENAME = "sample_version_index.json"
SNAPSHOTS_DIRNAME = "snapshots"
SNAPSHOT_HASH_HEX_PREFIX_LEN = 16

SourceFileGitStatus = Literal[
    "clean", "modified", "untracked", "ignored", "outside_repo"
]


@dataclass(frozen=True)
class RegisterSampleResult:
    file_hash: str
    snapshot_path: Path
    index_path: Path
    skipped: bool
    record: dict[str, Any]


def _resolve_under_root(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        return resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"{resolved} is not under {root_resolved}") from exc


def file_hash_to_snapshot_dir_name(file_hash: str) -> str:
    if not file_hash.startswith(FILE_HASH_PREFIX):
        raise ValueError(f"file_hash must start with {FILE_HASH_PREFIX!r}")
    hex_part = file_hash.removeprefix(FILE_HASH_PREFIX)
    if len(hex_part) < SNAPSHOT_HASH_HEX_PREFIX_LEN:
        raise ValueError("file_hash hex segment is too short for snapshot dir name")
    return f"sha256_{hex_part[:SNAPSHOT_HASH_HEX_PREFIX_LEN]}"


def snapshot_rel_path(
    *,
    file_hash: str,
    file_name: str,
    source_rel_path: str,
) -> str:
    """Relative path (from samples_root) of the snapshot docx file."""
    source = Path(source_rel_path)
    parent = source.parent.as_posix()
    dir_name = file_hash_to_snapshot_dir_name(file_hash)
    return f"{SNAPSHOTS_DIRNAME}/{parent}/{dir_name}/{file_name}"


def snapshot_dir_abs_path(
    *,
    file_hash: str,
    source_rel_path: str,
    samples_root: Path,
) -> Path:
    """Absolute path of the ``sha256_<prefix>/`` snapshot directory."""
    source = Path(source_rel_path)
    parent = source.parent.as_posix()
    dir_name = file_hash_to_snapshot_dir_name(file_hash)
    return (samples_root.resolve() / SNAPSHOTS_DIRNAME / parent / dir_name).resolve()


def snapshot_abs_path(
    *,
    file_hash: str,
    file_name: str,
    source_rel_path: str,
    samples_root: Path,
) -> Path:
    """Absolute path of the snapshot docx file."""
    return snapshot_dir_abs_path(
        file_hash=file_hash,
        source_rel_path=source_rel_path,
        samples_root=samples_root,
    ) / file_name


def snapshot_index_abs_path(
    *,
    file_hash: str,
    source_rel_path: str,
    samples_root: Path,
) -> Path:
    """Absolute path of ``sample_version_index.json`` inside the snapshot dir."""
    return snapshot_dir_abs_path(
        file_hash=file_hash,
        source_rel_path=source_rel_path,
        samples_root=samples_root,
    ) / SAMPLE_VERSION_INDEX_FILENAME


def load_snapshot_record(
    file_hash: str,
    *,
    samples_root: Path,
) -> dict[str, Any] | None:
    """Find and load the per-snapshot index for ``file_hash`` by scanning ``snapshots/``."""
    dir_name = file_hash_to_snapshot_dir_name(file_hash)
    snapshots_root = samples_root.resolve() / SNAPSHOTS_DIRNAME
    if not snapshots_root.is_dir():
        return None
    for candidate in snapshots_root.rglob(
        f"{dir_name}/{SAMPLE_VERSION_INDEX_FILENAME}"
    ):
        if candidate.is_file():
            data = load_json(candidate)
            if isinstance(data, dict) and data.get("file_hash") == file_hash:
                return data
    return None


def resolve_snapshot_path(
    file_hash: str,
    *,
    samples_root: Path,
) -> Path | None:
    """Return the absolute path to the snapshot docx for ``file_hash``, or None."""
    record = load_snapshot_record(file_hash, samples_root=samples_root)
    if record is None:
        return None
    rel = record.get("snapshot_path")
    if not isinstance(rel, str) or not rel.strip():
        return None
    candidate = (samples_root.resolve() / Path(rel)).resolve()
    return candidate if candidate.is_file() else None


def get_source_file_git_status(
    source_file: Path,
    *,
    git_root: Path | None,
) -> SourceFileGitStatus:
    if git_root is None:
        return "outside_repo"
    try:
        rel = source_file.resolve().relative_to(git_root.resolve())
    except ValueError:
        return "outside_repo"

    try:
        output = subprocess.run(
            ["git", "status", "--porcelain", "--", rel.as_posix()],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "outside_repo"

    if not output.strip():
        return "clean"

    line = output.strip().split("\n", 1)[0]
    if len(line) < 3:
        return "clean"
    status = line[:2]
    if status == "??":
        return "untracked"
    if status == "!!":
        return "ignored"
    if any(ch in status for ch in "MADRCU"):
        return "modified"
    return "modified"


def register_sample(
    source_file: Path,
    samples_root: Path,
    *,
    note: str | None = None,
    git_root: Path | None = None,
) -> RegisterSampleResult:
    """Register one sample version: copy snapshot + write per-snapshot index.

    If the hash already exists (``sha256_<prefix>/sample_version_index.json``
    is present with a matching ``file_hash``), the registration is skipped.
    """
    source_path = source_file.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    samples_root = samples_root.resolve()
    rel_source = _resolve_under_root(source_path, samples_root).as_posix()
    file_hash = compute_file_hash(source_path)
    file_name = source_path.name

    snap_path = snapshot_abs_path(
        file_hash=file_hash,
        file_name=file_name,
        source_rel_path=rel_source,
        samples_root=samples_root,
    )
    idx_path = snapshot_index_abs_path(
        file_hash=file_hash,
        source_rel_path=rel_source,
        samples_root=samples_root,
    )

    existing = load_snapshot_record(file_hash, samples_root=samples_root)
    if existing is not None:
        return RegisterSampleResult(
            file_hash=file_hash,
            snapshot_path=snap_path,
            index_path=idx_path,
            skipped=True,
            record=existing,
        )

    resolved_git_root = git_root if git_root is not None else find_git_root(source_path)
    git_prov = get_git_provenance(root=resolved_git_root) if resolved_git_root else {
        "git_commit": None,
        "git_dirty": None,
    }

    snap_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, snap_path)

    record: dict[str, Any] = {
        "schema_version": SAMPLE_VERSION_INDEX_SCHEMA_VERSION,
        "kind": SAMPLE_VERSION_INDEX_KIND,
        "file_hash": file_hash,
        "file_name": file_name,
        "source_path_at_registration": rel_source,
        "snapshot_path": _resolve_under_root(snap_path, samples_root).as_posix(),
        "registered_at": utc_created_at(),
        "git_commit": git_prov.get("git_commit"),
        "repo_git_dirty": git_prov.get("git_dirty"),
        "source_file_git_status": get_source_file_git_status(
            source_path,
            git_root=resolved_git_root,
        ),
    }
    if note:
        record["note"] = note

    save_json(idx_path, record)

    return RegisterSampleResult(
        file_hash=file_hash,
        snapshot_path=snap_path,
        index_path=idx_path,
        skipped=False,
        record=record,
    )
