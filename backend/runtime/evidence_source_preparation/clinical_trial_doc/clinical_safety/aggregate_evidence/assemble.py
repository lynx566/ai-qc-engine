# ruff: noqa: TRY004
"""Aggregate Evidence assemble phase dev/debug harness: join inputs and persist bundle.

Phase dev/debug harness — not a canonical runtime stage.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input import ASSESSMENT_INPUT_FILENAME
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    ASSESSMENT_RUNTIME_CONTEXT_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    HEADING_SCOPE_ELIGIBILITY_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import SCOPE_ASSESSMENTS_FILENAME
from runtime.io import load_json
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
    persist_assemble_execution,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.results import AssembleResult
from runtime.run_layout import require_evidence_form_id_segment

__all__ = [
    "AssembleResult",
    "run_assemble",
]


def run_assemble(
    *,
    run_assemble_phase: Callable[..., Any],
    assessment_input_path: Path | str,
    assessment_runtime_context_path: Path | str,
    scope_assessments_path: Path | str,
    heading_scope_eligibility_path: Path | str,
    output_dir: Path | str,
    run_id: str,
    evidence_form_id: str,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> AssembleResult:
    """Execute aggregate_evidence assemble from four persisted ESP internal artifacts."""
    require_evidence_form_id_segment(evidence_form_id)

    resolved_assessment_input_path = _require_input_file(
        assessment_input_path,
        expected_name=ASSESSMENT_INPUT_FILENAME,
        flag_name="assessment_input",
    )
    resolved_runtime_context_path = _require_input_file(
        assessment_runtime_context_path,
        expected_name=ASSESSMENT_RUNTIME_CONTEXT_FILENAME,
        flag_name="assessment_runtime_context",
    )
    resolved_scope_assessments_path = _require_input_file(
        scope_assessments_path,
        expected_name=SCOPE_ASSESSMENTS_FILENAME,
        flag_name="scope_assessments",
    )
    resolved_eligibility_path = _require_input_file(
        heading_scope_eligibility_path,
        expected_name=HEADING_SCOPE_ELIGIBILITY_FILENAME,
        flag_name="heading_scope_eligibility",
    )

    assessment_input = _load_object(resolved_assessment_input_path, label="assessment_input")
    assessment_runtime_context = _load_object(
        resolved_runtime_context_path,
        label="assessment_runtime_context",
    )
    scope_assessments = _load_object(resolved_scope_assessments_path, label="scope_assessments")
    heading_scope_eligibility = _load_object(
        resolved_eligibility_path,
        label="heading_scope_eligibility",
    )
    doc_id = _require_context_string(assessment_input, field="doc_id")
    zone_key = str(assessment_input.get("zone_key") or "")

    assemble_result = run_assemble_phase(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        scope_assessments=scope_assessments,
        heading_scope_eligibility=heading_scope_eligibility,
    )

    return persist_assemble_execution(
        execution=assemble_result,
        output_dir=output_dir,
        run_id=run_id,
        assessment_input_path=resolved_assessment_input_path,
        assessment_runtime_context_path=resolved_runtime_context_path,
        scope_assessments_path=resolved_scope_assessments_path,
        heading_scope_eligibility_path=resolved_eligibility_path,
        doc_id=doc_id,
        zone_key=zone_key,
        phase=EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE,
        git_provenance=git_provenance,
    )


def _require_input_file(
    path: Path | str,
    *,
    expected_name: str,
    flag_name: str,
) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise ValueError(f"{flag_name} must be a file: {resolved}")
    if resolved.name != expected_name:
        raise ValueError(
            f"{flag_name} input must be named {expected_name!r}, got {resolved.name!r}"
        )
    return resolved


def _load_object(path: Path, *, label: str) -> dict:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _require_context_string(payload: dict, *, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"assessment_input.{field} is required")
    return value.strip()
