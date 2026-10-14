"""Shared run artifact naming and path helpers for backend/runs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.run_ids import build_run_id_from_session_dir, build_session_dir_segment

# Canonical layout: runs/<stage>/<run_id>/doc_<doc_id>/[<task_key>/[<route>/]]
CANONICAL_RUN_DIR_LAYOUT = "stage/run_id/doc_dir"
CANONICAL_RUN_DIR_LAYOUT_TASK = "stage/run_id/doc_dir/task_key"
CANONICAL_RUN_DIR_LAYOUT_ROUTE = "stage/run_id/doc_dir/task_key/route"

# Backward-compatible aliases used in run_summary.json metadata.
RUN_DIR_LAYOUT = CANONICAL_RUN_DIR_LAYOUT
ANALYSIS_RUN_DIR_LAYOUT = CANONICAL_RUN_DIR_LAYOUT
DOC_META_RUN_DIR_LAYOUT = CANONICAL_RUN_DIR_LAYOUT
EXTRACT_RUN_DIR_LAYOUT = CANONICAL_RUN_DIR_LAYOUT
FILTER_RUN_DIR_LAYOUT = CANONICAL_RUN_DIR_LAYOUT_TASK
FILTER_OUTPUT_PROJECTION_RUN_DIR_LAYOUT = CANONICAL_RUN_DIR_LAYOUT_TASK
ROUTE_RUN_DIR_LAYOUT = CANONICAL_RUN_DIR_LAYOUT_TASK
# Evidence Source Preparation:
# runs/evidence_source_preparation/<phase>/<run_id>/doc_<doc_id>/<zone_key>/<evidence_form_id>/
STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT = (
    "stage/phase/run_id/doc_dir/task_key/processor_type"
)
# Request File Intake: runs/request_file_intake/<run_id>/ (no doc_id leaf)
REQUEST_FILE_INTAKE_RUN_DIR_LAYOUT = "stage/run_id"


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def sanitize_run_segment(text: str) -> str:
    """Return a safe single path segment for Windows/macOS/Linux."""
    s = (text or "").strip()
    stripped = "".join(ch if ch not in '<>:"/\\|?*\n\r\t' else "_" for ch in s).strip(
        ". "
    )
    stripped = re.sub(r"\s+", "_", stripped)
    return stripped if stripped else "unnamed"


def require_evidence_form_id_segment(evidence_form_id: str) -> str:
    """Validate and normalize an evidence-form run-directory leaf."""
    resolved = sanitize_run_segment(evidence_form_id)
    if not resolved:
        raise ValueError("evidence_form_id must be a non-empty path segment")
    return resolved.lower()


def format_doc_run_dir_name(doc_id: str) -> str:
    """Return the per-document directory leaf under a stage run directory."""
    slug = sanitize_run_segment(doc_id)
    if slug.startswith("doc_"):
        return slug
    return f"doc_{slug}"


def build_stage_run_dir(
    runs_root: Path,
    stage: str,
    context: str,
    timestamp: str,
    doc_id: str,
) -> Path:
    """
    Legacy helper: ``runs/<stage>/<timestamp>/doc_<doc_id>/``.

    *context* is ignored (kept for call-site compatibility).
    """
    _ = context
    stage_seg = sanitize_run_segment(stage).lower()
    ts = sanitize_run_segment(timestamp)
    did = format_doc_run_dir_name(doc_id)
    return runs_root / stage_seg / ts / did


def run_dir_layout_metadata(
    *,
    context: str,
    run_dir_layout: str | None = None,
) -> dict[str, str]:
    _ = context  # path layout only; not persisted on run_summary.json
    return {
        "run_dir_layout": run_dir_layout or CANONICAL_RUN_DIR_LAYOUT,
    }


@dataclass(frozen=True)
class RunNaming:
    """
    Artifact directory names for pipeline runs.

    ``run_id`` follows ``<stage>_<session_dir_name>`` where *session_dir_name* is
    the final allocated session folder (may include a ``__n`` suffix).
    ``session_dir_name`` is a compact UTC timestamp such as ``20260705_102233_184512Z``.
    ``doc_id`` is the raw document id (directory leaf uses :func:`format_doc_run_dir_name`).
    """

    run_id: str
    doc_id: str
    session_dir_name: str | None = None
    artifact_stem: str | None = None
    stage: str | None = None
    context: str | None = None
    task_key: str | None = None
    route: str | None = None
    evidence_form_id: str | None = None
    comparison_type: str | None = None
    phase: str | None = None

    @property
    def export_dir_name(self) -> str:
        """Backward-compatible alias for formatted doc directory name."""
        return format_doc_run_dir_name(self.doc_id)


@dataclass(frozen=True)
class StageRunLayout:
    run_id: str
    stage: str
    context: str
    timestamp: str
    doc_id: str
    task_key: str | None = None
    route: str | None = None
    evidence_form_id: str | None = None
    comparison_type: str | None = None
    phase: str | None = None
    run_dir_layout: str = CANONICAL_RUN_DIR_LAYOUT

    @property
    def doc_dir_name(self) -> str:
        return format_doc_run_dir_name(self.doc_id)

    def session_dir(self, runs_root: Path) -> Path:
        stage = sanitize_run_segment(self.stage).lower()
        ts = sanitize_run_segment(self.timestamp)
        return runs_root / stage / ts

    def run_dir(self, runs_root: Path) -> Path:
        path = self.session_dir(runs_root) / self.doc_dir_name
        if self.task_key:
            path = path / sanitize_run_segment(self.task_key).lower()
        if self.evidence_form_id:
            path = path / sanitize_run_segment(self.evidence_form_id).lower()
        elif self.route:
            path = path / sanitize_run_segment(self.route).lower()
        if self.comparison_type:
            path = path / sanitize_run_segment(self.comparison_type).lower()
        if self.phase:
            path = path / sanitize_run_segment(self.phase).lower()
        return path

    def doc_parent(self, session_dir: Path) -> Path:
        """Directory that directly contains the artifact leaf (zone/route folder or doc dir)."""
        if self.task_key or self.route or self.evidence_form_id:
            return session_dir / self.doc_dir_name
        return session_dir

    def artifact_leaf(self, session_dir: Path) -> Path:
        """Resolved artifact directory under *session_dir*."""
        path = session_dir / self.doc_dir_name
        if self.task_key:
            path = path / sanitize_run_segment(self.task_key).lower()
        if self.evidence_form_id:
            path = path / sanitize_run_segment(self.evidence_form_id).lower()
        elif self.route:
            path = path / sanitize_run_segment(self.route).lower()
        if self.comparison_type:
            path = path / sanitize_run_segment(self.comparison_type).lower()
        if self.phase:
            path = path / sanitize_run_segment(self.phase).lower()
        return path

    def summary_layout_fields(self) -> dict[str, str]:
        return run_dir_layout_metadata(
            context=self.context,
            run_dir_layout=self.run_dir_layout,
        )


def build_stage_run_layout(
    *,
    stage: str,
    context: str,
    doc_id: str,
    stamp: datetime,
    session_dir_name: str | None = None,
    task_key: str | None = None,
    route: str | None = None,
    evidence_form_id: str | None = None,
    comparison_type: str | None = None,
    phase: str | None = None,
    run_dir_layout: str | None = None,
) -> StageRunLayout:
    ts = session_dir_name or build_session_dir_segment(stamp)
    stage_seg = sanitize_run_segment(stage).lower()
    ctx = sanitize_run_segment(context).lower()
    did = sanitize_run_segment(doc_id)
    resolved_task = sanitize_run_segment(task_key).lower() if task_key else None
    resolved_route = sanitize_run_segment(route).lower() if route else None
    resolved_evidence_form_id = (
        sanitize_run_segment(evidence_form_id).lower() if evidence_form_id else None
    )
    resolved_comparison = (
        sanitize_run_segment(comparison_type).lower() if comparison_type else None
    )
    resolved_phase = sanitize_run_segment(phase).lower() if phase else None
    if run_dir_layout is None:
        if resolved_evidence_form_id or resolved_comparison or resolved_phase:
            run_dir_layout = STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT
        elif resolved_route:
            run_dir_layout = CANONICAL_RUN_DIR_LAYOUT_ROUTE
        elif resolved_task:
            run_dir_layout = CANONICAL_RUN_DIR_LAYOUT_TASK
        else:
            run_dir_layout = CANONICAL_RUN_DIR_LAYOUT
    return StageRunLayout(
        run_id=build_run_id_from_session_dir(stage_seg, ts),
        stage=stage_seg,
        context=ctx,
        timestamp=ts,
        doc_id=did,
        task_key=resolved_task,
        route=resolved_route,
        evidence_form_id=resolved_evidence_form_id,
        comparison_type=resolved_comparison,
        phase=resolved_phase,
        run_dir_layout=run_dir_layout,
    )


def build_extract_run_naming(
    *,
    stamp: datetime,
    sample_slug: str,
    git_root: Path,
    source_type: str = "docx",
    session_dir_name: str | None = None,
) -> RunNaming:
    _ = git_root
    doc_id = sanitize_run_segment(sample_slug)
    session = session_dir_name or build_session_dir_segment(stamp)
    ctx = sanitize_run_segment(source_type).lower()
    return RunNaming(
        run_id=build_run_id_from_session_dir("extract", session),
        doc_id=doc_id,
        session_dir_name=session,
        artifact_stem=doc_id,
        stage="extract",
        context=ctx,
    )


def _stage_session_run_naming(
    *,
    stage: str,
    stamp: datetime,
    context: str,
    doc_id: str,
    git_root: Path,
    session_dir_name: str | None = None,
    task_key: str | None = None,
    route: str | None = None,
    evidence_form_id: str | None = None,
    comparison_type: str | None = None,
    phase: str | None = None,
) -> RunNaming:
    _ = git_root
    session = session_dir_name or build_session_dir_segment(stamp)
    ctx = sanitize_run_segment(context).lower()
    did = sanitize_run_segment(doc_id)
    return RunNaming(
        run_id=build_run_id_from_session_dir(stage, session),
        doc_id=did,
        session_dir_name=session,
        stage=sanitize_run_segment(stage).lower(),
        context=ctx,
        task_key=sanitize_run_segment(task_key).lower() if task_key else None,
        route=sanitize_run_segment(route).lower() if route else None,
        evidence_form_id=(
            sanitize_run_segment(evidence_form_id).lower() if evidence_form_id else None
        ),
        comparison_type=(
            sanitize_run_segment(comparison_type).lower() if comparison_type else None
        ),
        phase=sanitize_run_segment(phase).lower() if phase else None,
    )


def build_filter_session_run_naming(
    *,
    stamp: datetime,
    zone_key: str,
    doc_id: str,
    git_root: Path,
    session_dir_name: str | None = None,
) -> RunNaming:
    """Filter runs: ``runs/filter/<run_id>/doc_<doc_id>/<zone_key>/``."""
    return _stage_session_run_naming(
        stage="filter",
        stamp=stamp,
        context=zone_key,
        doc_id=doc_id,
        git_root=git_root,
        session_dir_name=session_dir_name,
        task_key=zone_key,
    )


def build_filter_output_projection_session_run_naming(
    *,
    stamp: datetime,
    filter_job_id: str,
    doc_id: str,
    git_root: Path,
    session_dir_name: str | None = None,
) -> RunNaming:
    """Projection runs: ``runs/filter_output_projection/<run_id>/doc_<doc_id>/<filter_job_id>/``."""
    task_key = sanitize_run_segment(filter_job_id).lower()
    return _stage_session_run_naming(
        stage="filter_output_projection",
        stamp=stamp,
        context=task_key,
        doc_id=doc_id,
        git_root=git_root,
        session_dir_name=session_dir_name,
        task_key=task_key,
    )


def build_prepare_analysis_session_run_naming(
    *,
    stamp: datetime,
    context: str,
    doc_id: str,
    git_root: Path,
    session_dir_name: str | None = None,
) -> RunNaming:
    """Analysis prep runs: ``runs/prepare_analysis/<run_id>/doc_<doc_id>/``."""
    return _stage_session_run_naming(
        stage="prepare_analysis",
        stamp=stamp,
        context=context,
        doc_id=doc_id,
        git_root=git_root,
        session_dir_name=session_dir_name,
    )


def build_doc_meta_session_run_naming(
    *,
    stamp: datetime,
    context: str,
    doc_id: str,
    git_root: Path,
    session_dir_name: str | None = None,
) -> RunNaming:
    """Doc_meta runs: ``runs/doc_meta/<run_id>/doc_<doc_id>/``."""
    return _stage_session_run_naming(
        stage="doc_meta",
        stamp=stamp,
        context=context,
        doc_id=doc_id,
        git_root=git_root,
        session_dir_name=session_dir_name,
    )


def _route_artifact_leaf(
    *,
    session_dir: Path,
    doc_id: str,
    zone_key: str,
    run_id: str,
    stamp: datetime,
) -> Path:
    layout = build_stage_run_layout(
        stage="route",
        context=zone_key,
        doc_id=doc_id,
        stamp=stamp,
        session_dir_name=run_id,
        task_key=zone_key,
        run_dir_layout=CANONICAL_RUN_DIR_LAYOUT_TASK,
    )
    return layout.artifact_leaf(session_dir)


def canonical_route_output_dir(
    *,
    runs_root: Path,
    run_id: str,
    doc_id: str,
    zone_key: str,
    stamp: datetime | None = None,
) -> Path:
    """Return canonical route artifact directory (no mkdir)."""
    resolved_stamp = stamp or datetime.now(timezone.utc)
    session_dir = runs_root / "route" / sanitize_run_segment(run_id)
    return _route_artifact_leaf(
        session_dir=session_dir,
        doc_id=doc_id,
        zone_key=zone_key,
        run_id=run_id,
        stamp=resolved_stamp,
    )


def resolve_route_artifact_dir(
    *,
    project_root: Path,
    zone_key: str,
    doc_id: str,
    run_id: str,
    stamp: datetime,
    output_root: Path | None = None,
) -> tuple[Path, Path]:
    """
    Return ``(artifact_dir, session_dir)`` for the route stage.

    Layout: ``runs/route/<run_id>/doc_<doc_id>/<zone_key>/``
    """
    if output_root is not None:
        session_dir = output_root / sanitize_run_segment(run_id)
        out_dir = _route_artifact_leaf(
            session_dir=session_dir,
            doc_id=doc_id,
            zone_key=zone_key,
            run_id=run_id,
            stamp=stamp,
        )
    else:
        runs_root = project_root / "runs"
        session_dir = runs_root / "route" / sanitize_run_segment(run_id)
        out_dir = canonical_route_output_dir(
            runs_root=runs_root,
            run_id=run_id,
            doc_id=doc_id,
            zone_key=zone_key,
            stamp=stamp,
        )
    session_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir, session_dir


def _stage_phase_artifact_leaf(
    *,
    session_dir: Path,
    stage: str,
    doc_id: str,
    zone_key: str,
    run_id: str,
    stamp: datetime,
    evidence_form_id: str,
) -> Path:
    layout = build_stage_run_layout(
        stage=stage,
        context=zone_key,
        doc_id=doc_id,
        stamp=stamp,
        session_dir_name=run_id,
        task_key=zone_key,
        evidence_form_id=evidence_form_id,
        phase=None,
        run_dir_layout=STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT,
    )
    return layout.artifact_leaf(session_dir)


def resolve_stage_phase_root(
    *,
    project_root: Path,
    stage: str,
    phase: str,
    output_root: Path | None = None,
) -> Path:
    """Return ``runs/<stage>/<phase>/`` (or *output_root*)."""
    if output_root is not None:
        return output_root
    stage_seg = sanitize_run_segment(stage).lower()
    phase_seg = sanitize_run_segment(phase).lower()
    return project_root / "runs" / stage_seg / phase_seg


def resolve_stage_phase_artifact_dir(
    *,
    project_root: Path,
    stage: str,
    zone_key: str,
    doc_id: str,
    run_id: str,
    stamp: datetime,
    phase: str,
    evidence_form_id: str,
    output_root: Path | None = None,
) -> tuple[Path, Path]:
    """
    Return ``(artifact_dir, session_dir)`` for a staged process operation.

    Layout: ``runs/<stage>/<phase>/<run_id>/doc_<doc_id>/<zone_key>/<evidence_form_id>/``
    """
    session_dir = resolve_stage_phase_root(
        project_root=project_root,
        stage=stage,
        phase=phase,
        output_root=output_root,
    ) / sanitize_run_segment(run_id)
    out_dir = _stage_phase_artifact_leaf(
        session_dir=session_dir,
        stage=stage,
        doc_id=doc_id,
        zone_key=zone_key,
        run_id=run_id,
        stamp=stamp,
        evidence_form_id=evidence_form_id,
    )
    session_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir, session_dir


def build_tag_session_run_naming(
    *,
    stamp: datetime,
    context: str,
    doc_id: str,
    git_root: Path,
    session_dir_name: str | None = None,
    route: str | None = None,
) -> RunNaming:
    """Tag runs: ``runs/tag/<run_id>/doc_<doc_id>/<zone_key>/<route>/``."""
    return _stage_session_run_naming(
        stage="tag",
        stamp=stamp,
        context=context,
        doc_id=doc_id,
        git_root=git_root,
        session_dir_name=session_dir_name,
        task_key=context,
        route=route,
    )


def posix_relative(path: Path, base: Path) -> str:
    """Best-effort relative path with forward slashes for JSON."""
    try:
        return Path(path.resolve()).relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def doc_id_from_bundle(bundle: dict[str, Any]) -> str:
    doc_id = bundle.get("doc_id")
    if doc_id is not None:
        sid = str(doc_id).strip()
        if sid:
            return sanitize_run_segment(sid)
    return "unnamed"


def output_leaf_name(bundle_path: Path, bundle: dict[str, Any]) -> str:
    """Resolve doc_id for run dir leaf (supports legacy ``*_export`` parents)."""
    parent_name = bundle_path.parent.name
    if parent_name.endswith("_export"):
        return sanitize_run_segment(parent_name[: -len("_export")])
    resolved = doc_id_from_bundle(bundle)
    if resolved != "unnamed":
        return resolved
    if parent_name:
        return sanitize_run_segment(parent_name)
    return sanitize_run_segment(bundle_path.stem)


def mkdir_unique_under(parent: Path, leaf: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    slug = sanitize_run_segment(leaf)
    cand = parent / slug
    if not cand.exists():
        cand.mkdir(parents=True, exist_ok=True)
        return cand
    n = 2
    while True:
        cand = parent / f"{slug}__{n}"
        if not cand.exists():
            cand.mkdir(parents=True, exist_ok=True)
            return cand
        n += 1


def resolve_unique_session_dir(session_root: Path, session_base_name: str) -> Path:
    """
    Allocate a unique session directory under *session_root*.

    Example::

        20260705_102233_184512Z/
        20260705_102233_184512Z__2/
    """
    return mkdir_unique_under(session_root, session_base_name)


def allocate_session_dir(
    runs_root: Path,
    *,
    stage: str,
    context: str,
    stamp: datetime,
    session_dir_name: str | None = None,
    bucket: str | None = None,
    run_dir_layout: str | None = None,
) -> Path:
    """
    Allocate one session directory per runner invocation.

    Canonical: ``runs/<stage>/<run_id>/`` where *run_id* is a UTC timestamp
    (microsecond precision). A defensive ``__n`` suffix is added only on collision.
    """
    _ = context, bucket, run_dir_layout
    session_base = session_dir_name or build_session_dir_segment(stamp)
    stage_root = runs_root / sanitize_run_segment(stage).lower()
    return resolve_unique_session_dir(stage_root, session_base)


def ensure_stage_doc_run_dir(
    runs_root: Path,
    layout: StageRunLayout,
    *,
    session_dir: Path,
    output_dir: str | Path | None = None,
    multi_input: bool = False,
) -> Path:
    """Create the artifact directory for one doc (and optional task/route)."""
    _ = runs_root
    if output_dir is not None:
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        return out

    artifact_dir = layout.artifact_leaf(session_dir)
    if multi_input and artifact_dir.exists():
        return mkdir_unique_under(artifact_dir.parent, artifact_dir.name)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir
