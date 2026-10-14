"""Heading-scope eligibility artifact contract tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    HEADING_SCOPE_ELIGIBILITY_ARTIFACT_TYPE,
    HEADING_SCOPE_ELIGIBILITY_SCHEMA_VERSION,
    HEADING_SCOPE_ELIGIBILITY_STATUSES,
    build_heading_scope_eligibility_envelope,
    build_source_scope_assessments_ref,
    resolve_source_scope_assessments_path,
    validate_heading_scope_eligibility,
    validate_source_scope_assessments_ref,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import SCOPE_ASSESSMENTS_FILENAME
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import SCOPE_ASSESSMENTS_SCHEMA_VERSION
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.heading_scope_eligibility_policy import (
    build_heading_scope_eligibility_entries,
)
from runtime.io import save_json


def _scope_assessments_payload() -> dict:
    return {
        "artifact_type": "scope_assessments",
        "schema_version": SCOPE_ASSESSMENTS_SCHEMA_VERSION,
        "stage": "evidence_source_preparation",
        "phase": "assess",
        "doc_id": "doc_test",
        "file_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "zone_key": "ib_clinical_safety_zh",
        "scope_assessments": [
            {
                "scope_id": "HS0001",
                "heading_path": ["安全性"],
                "source_unit_ids": ["TU0001"],
                "product_context_role": "target_study_drug",
                "unit_form": "aggregate",
                "safety_role": "primary_safety_finding",
                "route_qc": {
                    "route_mismatch": False,
                    "suggested_route": None,
                    "reason": None,
                },
                "post_llm_validation_flags": [],
            }
        ],
        "scope_assessment_count": 1,
    }


def _canonical_scope_assessments_path(
    tmp_path: Path,
    *,
    assess_run_id: str = "assess_source_run",
) -> Path:
    artifact_dir = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "assess"
        / assess_run_id
        / "doc_test"
        / "ib_clinical_safety_zh"
        / "aggregate_evidence"
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir / SCOPE_ASSESSMENTS_FILENAME


def _source_ref(
    tmp_path: Path,
    payload: dict,
    *,
    assess_run_id: str = "assess_source_run",
) -> dict:
    path = _canonical_scope_assessments_path(tmp_path, assess_run_id=assess_run_id)
    save_json(path, payload)
    save_json(
        path.parent / "run_summary.json",
        {
            "run_id": assess_run_id,
            "stage": "evidence_source_preparation",
            "doc_id": payload["doc_id"],
            "zone_key": payload["zone_key"],
            "stats": {"phase": "assess"},
        },
    )
    return build_source_scope_assessments_ref(
        scope_assessments_payload=payload,
        scope_assessments_path=path,
        project_root=tmp_path,
        run_id=assess_run_id,
    )


def test_disk_source_ref_retains_zone_key_for_single_source(tmp_path: Path) -> None:
    payload = _scope_assessments_payload()
    source_ref = _source_ref(tmp_path, payload)
    assert source_ref["zone_key"] == "ib_clinical_safety_zh"
    validate_source_scope_assessments_ref(
        source_ref,
        scope_assessments_payload=payload,
    )


def test_disk_source_ref_omits_zone_key_for_fan_in(tmp_path: Path) -> None:
    payload = _scope_assessments_payload()
    del payload["zone_key"]
    artifact_dir = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "assess"
        / "assess_fan_in"
        / "doc_test"
        / "clinical_safety"
        / "aggregate_evidence"
    )
    artifact_dir.mkdir(parents=True)
    path = artifact_dir / SCOPE_ASSESSMENTS_FILENAME
    save_json(path, payload)
    source_ref = build_source_scope_assessments_ref(
        scope_assessments_payload=payload,
        scope_assessments_path=path,
        project_root=tmp_path,
        run_id="assess_fan_in",
    )
    assert "zone_key" not in source_ref
    validate_source_scope_assessments_ref(
        source_ref,
        scope_assessments_payload=payload,
    )
    resolved = resolve_source_scope_assessments_path(
        project_root=tmp_path,
        source_ref=source_ref,
    )
    assert resolved == path.resolve()


def test_validator_rejects_zone_key_when_payload_omits_it(tmp_path: Path) -> None:
    payload = _scope_assessments_payload()
    del payload["zone_key"]
    artifact_dir = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "assess"
        / "assess_source_run"
        / "doc_test"
        / "clinical_safety"
        / "aggregate_evidence"
    )
    artifact_dir.mkdir(parents=True)
    path = artifact_dir / SCOPE_ASSESSMENTS_FILENAME
    save_json(path, payload)
    source_ref = build_source_scope_assessments_ref(
        scope_assessments_payload=payload,
        scope_assessments_path=path,
        project_root=tmp_path,
        run_id="assess_source_run",
    )
    source_ref["zone_key"] = "ib_clinical_safety_zh"
    with pytest.raises(ValueError, match="must be omitted when scope_assessments has no zone_key"):
        validate_source_scope_assessments_ref(
            source_ref,
            scope_assessments_payload=payload,
        )


def test_build_and_validate_envelope(tmp_path: Path) -> None:
    payload = _scope_assessments_payload()
    entries = build_heading_scope_eligibility_entries(
        scope_assessments=payload["scope_assessments"],
    )
    source_ref = _source_ref(tmp_path, payload)
    envelope = build_heading_scope_eligibility_envelope(
        scope_assessments_payload=payload,
        scope_eligibility_entries=entries,
        source_scope_assessments_ref=source_ref,
    )
    validate_heading_scope_eligibility(envelope, source_scope_assessments_payload=payload)
    assert envelope["artifact_type"] == HEADING_SCOPE_ELIGIBILITY_ARTIFACT_TYPE
    assert envelope["schema_version"] == HEADING_SCOPE_ELIGIBILITY_SCHEMA_VERSION
    assert envelope["phase"] == "eligibility"
    assert len(envelope["scope_eligibility_entries"]) == 1
    assert "processing_disposition" not in envelope["scope_eligibility_entries"][0]
    assert envelope["source_scope_assessments_ref"]["run_id"] == "assess_source_run"
    assert envelope["source_scope_assessments_ref"]["path"].startswith(
        "runs/evidence_source_preparation/assess/"
    )
    assert envelope["eligibility_status_counts"]["auto_included"] == 1
    assert envelope["eligibility_status_counts"]["excluded_non_aggregate_form"] == 0
    assert "excluded_*" not in envelope["eligibility_status_counts"]


def test_source_ref_resolves_to_input_artifact(tmp_path: Path) -> None:
    payload = _scope_assessments_payload()
    source_ref = _source_ref(tmp_path, payload)
    resolved = resolve_source_scope_assessments_path(
        project_root=tmp_path,
        source_ref=source_ref,
    )
    assert resolved.is_file()
    assert resolved.name == SCOPE_ASSESSMENTS_FILENAME


def test_source_ref_rejects_bare_filename(tmp_path: Path) -> None:
    payload = _scope_assessments_payload()
    entries = build_heading_scope_eligibility_entries(
        scope_assessments=payload["scope_assessments"],
    )
    bad_ref = {
        "artifact_type": "scope_assessments",
        "schema_version": SCOPE_ASSESSMENTS_SCHEMA_VERSION,
        "stage": "evidence_source_preparation",
        "phase": "assess",
        "run_id": "assess_source_run",
        "doc_id": payload["doc_id"],
        "zone_key": payload["zone_key"],
        "file_hash": payload["file_hash"],
        "path": SCOPE_ASSESSMENTS_FILENAME,
    }
    with pytest.raises(ValueError, match="project-relative artifact path"):
        build_heading_scope_eligibility_envelope(
            scope_assessments_payload=payload,
            scope_eligibility_entries=entries,
            source_scope_assessments_ref=bad_ref,
        )


def test_rejects_unknown_eligibility_status_count(tmp_path: Path) -> None:
    payload = _scope_assessments_payload()
    entries = build_heading_scope_eligibility_entries(
        scope_assessments=payload["scope_assessments"],
    )
    envelope = build_heading_scope_eligibility_envelope(
        scope_assessments_payload=payload,
        scope_eligibility_entries=entries,
        source_scope_assessments_ref=_source_ref(tmp_path, payload),
    )
    envelope["eligibility_status_counts"]["excluded_*"] = 0
    with pytest.raises(ValueError, match="unknown status keys"):
        validate_heading_scope_eligibility(envelope)


def test_eligibility_status_counts_cover_allowed_enum() -> None:
    assert HEADING_SCOPE_ELIGIBILITY_STATUSES == frozenset(
        {
            "auto_included",
            "excluded_non_aggregate_form",
            "excluded_route_mismatch",
            "excluded_non_primary_safety",
            "excluded_non_target_product",
            "review_ambiguous",
        }
    )


def test_rejects_forbidden_processing_plan_field(tmp_path: Path) -> None:
    payload = _scope_assessments_payload()
    entries = build_heading_scope_eligibility_entries(
        scope_assessments=payload["scope_assessments"],
    )
    envelope = build_heading_scope_eligibility_envelope(
        scope_assessments_payload=payload,
        scope_eligibility_entries=entries,
        source_scope_assessments_ref=_source_ref(tmp_path, payload),
    )
    envelope["scope_processing_plan"] = {}
    with pytest.raises(ValueError, match="scope_processing_plan"):
        validate_heading_scope_eligibility(envelope)
