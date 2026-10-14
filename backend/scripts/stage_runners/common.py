from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from artifacts.prepare_analysis import ANALYSIS_BUNDLE_FILENAME
from runtime.run_layout import (
    format_doc_run_dir_name,
    mkdir_unique_under,
)


def ensure_project_on_path() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


def _resolve_runner_relative_path(path: Path) -> Path:
    """
    Resolve a non-absolute CLI path against the project conventions.

    Runner scripts live under the backend source root (``PROJECT_ROOT``), but users may
    pass repository-root style paths like ``backend/runs/...``. Treat those as rooted
    at ``PROJECT_ROOT.parent`` to avoid producing ``backend/backend/...``.
    """
    if path.is_absolute():
        return path.resolve()
    parts = path.parts
    if parts and parts[0] == PROJECT_ROOT.name:
        return (PROJECT_ROOT.parent / path).resolve()
    return (PROJECT_ROOT / path).resolve()


def resolve_user_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_file():
        return path.resolve()
    if not path.is_absolute():
        rooted = _resolve_runner_relative_path(path)
        if rooted.is_file():
            return rooted.resolve()
    return path.resolve()


def resolve_existing_file(path_str: str, *, flag_name: str = "path") -> Path:
    path = resolve_user_path(path_str)
    if not path.is_file():
        raise SystemExit(f"{flag_name} must be a file: {path_str!r}")
    return path


def resolve_existing_dir(path_str: str, *, flag_name: str = "path") -> Path:
    path = Path(path_str)
    if path.is_dir():
        return path.resolve()
    if not path.is_absolute():
        rooted = _resolve_runner_relative_path(path)
        if rooted.is_dir():
            return rooted.resolve()
    resolved = path.resolve()
    raise SystemExit(f"{flag_name} must be a directory: {path_str!r} ({resolved})")


def ensure_output_dir(path_str: str, *, flag_name: str = "--out") -> Path:
    """Resolve an output directory, creating it if needed."""
    _ = flag_name
    path = Path(path_str)
    if not path.is_absolute():
        path = _resolve_runner_relative_path(path)
    out_dir = path.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def discover_artifact_paths(directory: Path, *, filename: str) -> list[Path]:
    """All artifact inputs under a directory (canonical and legacy nested layouts)."""
    directory = directory.resolve()
    for pattern in (
        f"*/*/*/*/{filename}",
        f"*/*/*/{filename}",
        f"*/*/{filename}",
        f"*/{filename}",
    ):
        matches = sorted(directory.glob(pattern))
        if matches:
            return [p.resolve() for p in matches]
    direct = directory / filename
    if direct.is_file():
        return [direct.resolve()]
    hint = (
        " Run the prepare_analysis step first to produce analysis_bundle.json."
        if filename == ANALYSIS_BUNDLE_FILENAME
        else ""
    )
    raise SystemExit(
        f"no {filename} under {directory} "
        f"(expected */*/{filename}, */*/*/{filename}, or ./{filename}).{hint}"
    )


def resolve_artifact_file(
    path_str: str,
    *,
    filename: str,
    flag_name: str = "--bundle",
) -> Path:
    path = resolve_existing_file(path_str, flag_name=flag_name)
    if path.name != filename:
        if filename == ANALYSIS_BUNDLE_FILENAME and path.name == "bundle.json":
            raise SystemExit(
                "expected analysis_bundle.json (run prepare_analysis first), "
                f"got unmasked extract bundle: {path.name}"
            )
        raise SystemExit(f"expected {filename}, got: {path.name}")
    return path


def resolve_artifact_dir(
    path_str: str,
    *,
    filename: str,
    flag_name: str = "--bundle-dir",
) -> list[Path]:
    directory = resolve_existing_dir(path_str, flag_name=flag_name)
    return discover_artifact_paths(directory, filename=filename)


def resolve_output_dir(
    *,
    output_dir: str | None,
    session_parent: Path,
    export_dir_name: str,
    multi_input: bool,
) -> Path:
    """Deprecated: prefer :func:`ensure_stage_doc_run_dir`."""
    if output_dir:
        base = Path(output_dir).resolve()
        out_dir = mkdir_unique_under(base, export_dir_name) if multi_input else base
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir
    doc_name = format_doc_run_dir_name(export_dir_name)
    return mkdir_unique_under(session_parent, doc_name)
