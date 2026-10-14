# ruff: noqa: TRY004
"""Aggregate Evidence eligibility phase dev/debug harness: load and persist outputs.

Phase dev/debug harness — not a canonical runtime stage.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    build_source_scope_assessments_ref,
)
from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    SCOPE_ASSESSMENTS_FILENAME,
    validate_scope_assessments_envelope,
)
from runtime.io import load_json
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
    persist_eligibility_execution,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.results import (
    EligibilityResult,
)
from runtime.run_layout import posix_relative, require_evidence_form_id_segment

__all__ = [
    "EligibilityResult",
    "run_eligibility",
]


def _extract_assess_run_id(rel_path: str) -> str | None:
    parts = rel_path.replace("\\", "/").split("/")
    for index in range(len(parts) - 3):
        if (
            parts[index] == "runs"
            and parts[index + 1] == EVIDENCE_SOURCE_PREPARATION_STAGE
            and parts[index + 2] == "assess"
        ):
            run_id = parts[index + 3].strip()
            return run_id or None
    return None


def _resolve_assess_run_id(
    scope_assessments_path: Path,
    *,
    artifact_reference_root: Path,
) -> str:
    rel_path = posix_relative(scope_assessments_path, artifact_reference_root)
    run_id = _extract_assess_run_id(rel_path)
    if run_id:
        return run_id

    summary_path = scope_assessments_path.parent / "run_summary.json"
    if summary_path.is_file():
        summary = load_json(summary_path)
        if isinstance(summary, dict):
            candidate = str(summary.get("run_id") or "").strip()
            stats = summary.get("stats")
            stats_phase = stats.get("phase") if isinstance(stats, dict) else None
            if (
                candidate
                and summary.get("stage") == EVIDENCE_SOURCE_PREPARATION_STAGE
                and stats_phase == "assess"
            ):
                return candidate

    raise ValueError(
        "cannot resolve source assess run_id; scope_assessments must live under "
        "runs/evidence_source_preparation/assess/<run_id>/... or include an assess "
        "run_summary.json"
    )


def run_eligibility(
    *,
    run_evaluate_eligibility_phase: Callable[..., Any],
    build_heading_scope_eligibility_entries: Callable[..., list[dict[str, Any]]],
    artifact_reference_root: Path,
    scope_assessments_path: Path | str,
    output_dir: Path | str,
    run_id: str,
    evidence_form_id: str,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> EligibilityResult:
    """Execute aggregate_evidence process.eligibility from persisted scope_assessments.json."""
    require_evidence_form_id_segment(evidence_form_id)
    resolved_assessments_path = Path(scope_assessments_path).resolve()
    if not resolved_assessments_path.is_file():
        raise ValueError(f"scope_assessments must be a file: {resolved_assessments_path}")
    if resolved_assessments_path.name != SCOPE_ASSESSMENTS_FILENAME:
        raise ValueError(
            f"scope_assessments input must be named {SCOPE_ASSESSMENTS_FILENAME!r}, "
            f"got {resolved_assessments_path.name!r}"
        )

    scope_assessments = load_json(resolved_assessments_path)
    if not isinstance(scope_assessments, dict):
        raise ValueError("scope_assessments must be a JSON object")
    validate_scope_assessments_envelope(scope_assessments)

    source_scope_assessments_ref = build_source_scope_assessments_ref(
        scope_assessments_payload=scope_assessments,
        scope_assessments_path=resolved_assessments_path,
        project_root=artifact_reference_root,
        run_id=_resolve_assess_run_id(
            resolved_assessments_path,
            artifact_reference_root=artifact_reference_root,
        ),
    )

    eligibility_execution = run_evaluate_eligibility_phase(
        scope_assessments=scope_assessments,
        source_scope_assessments_ref=source_scope_assessments_ref,
        build_heading_scope_eligibility_entries=build_heading_scope_eligibility_entries,
    )

    return persist_eligibility_execution(
        execution=eligibility_execution,
        output_dir=output_dir,
        run_id=run_id,
        scope_assessments_path=resolved_assessments_path,
        scope_assessments=scope_assessments,
        git_provenance=git_provenance,
    )
