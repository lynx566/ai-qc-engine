"""Standalone dev runtime for Aggregate Comparison evidence materialization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    AGGREGATE_COMPARISON_EVIDENCE_FILENAME,
    AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_evidence import (
    materialize_aggregate_comparison_evidence,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_adapter import (
    build_aggregate_evidence_comparison_invocation,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceComparisonSourceAdapter,
)
from runtime.io import load_json, save_json
from runtime.run_ids import format_run_timestamp, utc_run_stamp
from runtime.run_layout import (
    resolve_unique_session_dir,
    sanitize_run_segment,
    utc_now_iso,
)
from runtime.run_provenance import snapshot_git_provenance_before_run

EVIDENCE_COMPARISON_STAGE = "evidence_comparison"
CLINICAL_SAFETY_EVIDENCE_SCOPE = "clinical_safety"
AGGREGATE_COMPARISON_SPECIALIZATION = "aggregate"
AGGREGATE_COMPARISON_MATERIALIZE_PHASE = "materialize"
AGGREGATE_COMPARISON_RUN_DIR_LAYOUT = "stage/evidence_scope/specialization/phase/run_id"
AGGREGATE_COMPARISON_MATERIALIZE_OPERATION = (
    "aggregate_evidence.materialize_aggregate_comparison_evidence"
)


@dataclass(frozen=True)
class AggregateComparisonMaterializationResult:
    run_id: str
    output_dir: Path
    aggregate_comparison_evidence: dict[str, Any]
    aggregate_comparison_evidence_path: Path
    run_summary_path: Path


@dataclass(frozen=True)
class AggregateComparisonMaterializationReport:
    result: AggregateComparisonMaterializationResult
    messages: tuple[str, ...]


def _ordered_sources(
    *,
    source: Path | str | None,
    source_a: Path | str | None,
    source_b: Path | str | None,
) -> tuple[tuple[str, Path], ...]:
    if source is not None and source_a is None and source_b is None:
        return (("source", Path(source)),)
    if source is None and source_a is not None and source_b is not None:
        return (("source_a", Path(source_a)), ("source_b", Path(source_b)))
    raise ValueError("provide either --source, or both --source-a and --source-b")


def _load_source(path: Path, *, role_id: str) -> Mapping[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"{role_id} must point to an existing file: {resolved}")
    payload = load_json(resolved)
    if not isinstance(payload, Mapping):
        raise TypeError(f"{role_id} source artifact must be a mapping")
    return payload


def _resolve_output(
    *,
    project_root: Path,
    output_dir: Path | str | None,
    run_id: str | None,
) -> tuple[Path, str]:
    requested_run_id = run_id.strip() if run_id is not None else ""
    if run_id is not None and not requested_run_id:
        raise ValueError("run_id must be a non-empty string when provided")

    if output_dir is not None:
        resolved_output = Path(output_dir).resolve()
        resolved_output.mkdir(parents=True, exist_ok=True)
        resolved_run_id = requested_run_id or format_run_timestamp(utc_run_stamp())
        return resolved_output, resolved_run_id

    phase_root = (
        project_root.resolve()
        / "runs"
        / EVIDENCE_COMPARISON_STAGE
        / CLINICAL_SAFETY_EVIDENCE_SCOPE
        / AGGREGATE_COMPARISON_SPECIALIZATION
        / AGGREGATE_COMPARISON_MATERIALIZE_PHASE
    )
    session_name = requested_run_id or format_run_timestamp(utc_run_stamp())
    session_dir = resolve_unique_session_dir(
        phase_root,
        sanitize_run_segment(session_name),
    )
    return session_dir.resolve(), session_dir.name


def _counts(artifact: Mapping[str, Any]) -> dict[str, int]:
    participants = artifact["participants"]
    scopes = [scope for participant in participants for scope in participant["scopes"]]
    units = [unit for scope in scopes for unit in scope["units"]]
    sentences = [sentence for unit in units for sentence in unit["sentences"]]
    return {
        "participant_count": len(participants),
        "scope_count": len(scopes),
        "unit_count": len(units),
        "sentence_count": len(sentences),
    }


def run_aggregate_comparison_materialization(
    *,
    project_root: Path,
    source_adapter: AggregateEvidenceComparisonSourceAdapter,
    source: Path | str | None = None,
    source_a: Path | str | None = None,
    source_b: Path | str | None = None,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
) -> AggregateComparisonMaterializationReport:
    """Materialize one or two ordered formal aggregate bundles for inspection."""

    ordered_paths = _ordered_sources(
        source=source,
        source_a=source_a,
        source_b=source_b,
    )
    git_provenance = snapshot_git_provenance_before_run(root=project_root)
    role_bound_evidence = tuple(
        (
            role_id,
            source_adapter(_load_source(path, role_id=role_id)),
        )
        for role_id, path in ordered_paths
    )
    invocation = build_aggregate_evidence_comparison_invocation(
        participants=role_bound_evidence,
    )
    artifact = materialize_aggregate_comparison_evidence(invocation=invocation)

    resolved_output, resolved_run_id = _resolve_output(
        project_root=project_root,
        output_dir=output_dir,
        run_id=run_id,
    )
    artifact_path = resolved_output / AGGREGATE_COMPARISON_EVIDENCE_FILENAME
    run_summary_path = resolved_output / "run_summary.json"
    save_json(artifact_path, artifact)
    save_json(
        run_summary_path,
        {
            "run_id": resolved_run_id,
            "stage": EVIDENCE_COMPARISON_STAGE,
            "evidence_scope": CLINICAL_SAFETY_EVIDENCE_SCOPE,
            "specialization": AGGREGATE_COMPARISON_SPECIALIZATION,
            "phase": AGGREGATE_COMPARISON_MATERIALIZE_PHASE,
            "created_at": utc_now_iso(),
            "git_commit": git_provenance["git_commit"],
            "git_dirty": git_provenance["git_dirty"],
            "git_dirty_checked_at": git_provenance["git_dirty_checked_at"],
            "status": "success",
            "run_status": "success",
            "run_dir_layout": AGGREGATE_COMPARISON_RUN_DIR_LAYOUT,
            "completed_operation": AGGREGATE_COMPARISON_MATERIALIZE_OPERATION,
            "inputs": {
                "participants": [
                    {
                        "role_id": role_id,
                        "source_bundle": path.resolve().as_posix(),
                        "aggregate_evidence_source_bundle_id": (
                            evidence.source_provenance.source_artifact_id
                        ),
                        "doc_id": evidence.source_provenance.doc_id,
                        "file_hash": evidence.source_provenance.file_hash,
                    }
                    for (role_id, path), (_, evidence) in zip(
                        ordered_paths,
                        role_bound_evidence,
                        strict=True,
                    )
                ]
            },
            "outputs": {
                "run_summary": "run_summary.json",
                "aggregate_comparison_evidence": (
                    AGGREGATE_COMPARISON_EVIDENCE_FILENAME
                ),
                "aggregate_comparison_evidence_schema_version": (
                    AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION
                ),
            },
            "stats": _counts(artifact),
        },
    )

    result = AggregateComparisonMaterializationResult(
        run_id=resolved_run_id,
        output_dir=resolved_output,
        aggregate_comparison_evidence=artifact,
        aggregate_comparison_evidence_path=artifact_path,
        run_summary_path=run_summary_path,
    )
    return AggregateComparisonMaterializationReport(
        result=result,
        messages=(
            f"run_id: {resolved_run_id}",
            f"aggregate_comparison_evidence: {artifact_path}",
            f"run_summary: {run_summary_path}",
        ),
    )


__all__ = [
    "AggregateComparisonMaterializationReport",
    "AggregateComparisonMaterializationResult",
    "run_aggregate_comparison_materialization",
]
