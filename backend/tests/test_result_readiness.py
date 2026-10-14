"""Result prerequisite probe stays separate from the full Result model."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.result_readiness import (
    probe_result_readiness,
    resolve_result_prerequisites,
)
from runtime.io import save_json
from runtime.io import load_json
from tests.test_internal_result_read import (
    _default_extract_blocks,
    _write_minimal_internal_result_fixture,
)


def _fixture(tmp_path: Path) -> tuple[str, dict]:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [],
            }
        ],
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            }
        ],
        extract_blocks=_default_extract_blocks(),
    )
    summary = load_json(
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / "test_internal_result"
        / "flow_run_summary.json"
    )
    return flow_run_id, summary


def test_probe_accepts_complete_prerequisites_without_full_result(
    tmp_path: Path,
) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    with patch(
        "application.clinical_trial_doc_consistency_qc.result_read.load_document_consistency_qc_result",
        side_effect=AssertionError("full Result loaded"),
    ):
        assert (
            probe_result_readiness(
                project_root=tmp_path,
                flow_run_id=flow_run_id,
                summary=summary,
            )
            is True
        )


def test_probe_accepts_empty_findings_from_successful_second_pass(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [],
            }
        ],
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "assessment_second_pass": {"status": "success"},
                "verification": None,
            }
        ],
        extract_blocks=_default_extract_blocks(),
    )
    summary = load_json(
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / "test_internal_result"
        / "flow_run_summary.json"
    )

    assert (
        probe_result_readiness(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            summary=summary,
        )
        is True
    )


def test_probe_accepts_completed_with_fallback_final_findings(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [],
            }
        ],
        final_findings=[],
        finalization_status="completed_with_fallback",
        fallback_comparison_modes=["focus_comparison"],
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            }
        ],
        extract_blocks=_default_extract_blocks(),
    )
    summary = load_json(
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / "test_internal_result"
        / "flow_run_summary.json"
    )

    assert probe_result_readiness(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        summary=summary,
    )


def test_probe_validates_declared_final_findings_contract(tmp_path: Path) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    declared = Path(summary["evidence_comparison"]["declared_output_path"])
    declared.write_text('{"artifact_type":"findings"}', encoding="utf-8")

    with pytest.raises(ValueError, match="keys mismatch"):
        probe_result_readiness(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            summary=summary,
        )


def test_probe_returns_false_for_unsupported_internal_result_capability(
    tmp_path: Path,
) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    summary["capability_id"] = "dsur_updated_ib"
    summary_path = (
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / "test_internal_result"
        / "flow_run_summary.json"
    )
    save_json(summary_path, summary)

    assert (
        probe_result_readiness(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            summary=summary,
        )
        is False
    )


def test_resolve_still_rejects_unsupported_internal_result_capability(
    tmp_path: Path,
) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    summary["capability_id"] = "dsur_updated_ib"

    with pytest.raises(ValueError, match="unsupported by the internal Result"):
        resolve_result_prerequisites(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            summary=summary,
        )


def test_probe_returns_false_for_absent_prerequisite(tmp_path: Path) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    Path(summary["evidence_comparison"]["declared_output_path"]).unlink()
    assert (
        probe_result_readiness(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            summary=summary,
        )
        is False
    )


def test_probe_returns_false_when_failed_stage_has_no_declared_output(
    tmp_path: Path,
) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    declared = Path(summary["evidence_comparison"]["declared_output_path"])
    declared.unlink()
    assert (declared.parent / "findings.json").is_file()
    summary["evidence_comparison"].pop("declared_output_path")
    summary["evidence_comparison"]["run_status"] = "failed"

    assert (
        probe_result_readiness(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            summary=summary,
        )
        is False
    )


def test_probe_rejects_malformed_declared_path(tmp_path: Path) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    summary["evidence_comparison"]["declared_output_path"] = []
    with pytest.raises(ValueError, match="declared_output_path"):
        probe_result_readiness(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            summary=summary,
        )


def test_probe_rejects_prerequisite_from_another_flow(tmp_path: Path) -> None:
    flow_run_id, summary = _fixture(tmp_path)
    foreign = tmp_path / "runs" / "document_consistency_qc" / "other_flow"
    foreign.mkdir()
    foreign_findings = foreign / "findings.json"
    foreign_findings.write_text("{}", encoding="utf-8")
    summary["evidence_comparison"]["declared_output_path"] = foreign_findings.as_posix()
    with pytest.raises(ValueError, match="outside"):
        probe_result_readiness(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            summary=summary,
        )
