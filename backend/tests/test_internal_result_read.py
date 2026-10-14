"""Targeted tests for internal Document Consistency QC Result read model."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.result_read import (
    ResultReadUnsupportedComparisonModeError,
    ResultReadValidationError,
    _resolve_job_execution,
    load_document_consistency_qc_result,
    resolve_owner_scope_alias,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
    build_final_findings,
    build_findings,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    build_aggregate_evidence_source_bundle,
)
from runtime.io import save_json

_TEST_FILE_HASH = (
    "sha256:10910f206d37eb8e78e2cd5becd0e23747dc216bb446014dcc08d1fc61579cb4"
)


def _write_minimal_internal_result_fixture(
    tmp_path: Path,
    *,
    findings_jobs: list[dict],
    plan_jobs: list[dict],
    run_summary_jobs: list[dict],
    extract_blocks: list[dict],
    final_findings: list[dict] | None = None,
    finalization_status: str = "completed",
    fallback_comparison_modes: list[str] | None = None,
) -> str:
    flow_run_id = "document_consistency_qc_test_internal_result"
    flow_root = tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    slot_root = flow_root / "participants" / "source"
    comparison_root = slot_root / "evidence_comparison"
    esp_root = slot_root / "evidence_source_preparation" / "clinical_safety"
    extract_root = slot_root / "extract"

    for directory in (comparison_root, esp_root, extract_root):
        directory.mkdir(parents=True, exist_ok=True)

    esp_bundle = build_aggregate_evidence_source_bundle(
        doc_id="doc_test",
        file_hash=_TEST_FILE_HASH,
        document_type="dsur",
        heading_scopes=[
            {
                "scope_id": "HS0001",
                "scope_order": 0,
                "heading_path": ["Scope A"],
                "units": [
                    {
                        "unit_id": "TU0001",
                        "unit_order": 0,
                        "text": "Sentence A Sentence B",
                        "source": {"block_ids": ["C0002"]},
                        "sentences": [
                            {
                                "sentence_id": "C0002:S001",
                                "sentence_order": 0,
                                "text": "Sentence A",
                                "source_block_ids": ["C0002"],
                            },
                            {
                                "sentence_id": "C0003:S001",
                                "sentence_order": 1,
                                "text": "Sentence B",
                                "source_block_ids": ["C0003"],
                            },
                        ],
                    }
                ],
            },
            {
                "scope_id": "HS0002",
                "scope_order": 1,
                "heading_path": ["Scope B"],
                "units": [
                    {
                        "unit_id": "TU0002",
                        "unit_order": 0,
                        "text": "Sentence C",
                        "source": {"block_ids": ["C0004"]},
                        "sentences": [
                            {
                                "sentence_id": "C0004:S001",
                                "sentence_order": 0,
                                "text": "Sentence C",
                                "source_block_ids": ["C0004"],
                            }
                        ],
                    }
                ],
            },
        ],
    )
    ace = build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": "source",
                "aggregate_evidence_source_bundle_id": esp_bundle[
                    "aggregate_evidence_source_bundle_id"
                ],
                "doc_id": "doc_test",
                "file_hash": _TEST_FILE_HASH,
                "scopes": [
                    {
                        "scope_id": "HS0001",
                        "scope_alias": "H0001",
                        "heading_path": ["Scope A"],
                        "units": [
                            {
                                "unit_id": "TU0001",
                                "unit_alias": "U0001",
                                "sentences": [
                                    {
                                        "sentence_id": "C0002:S001",
                                        "sentence_alias": "T0001",
                                        "text": "Sentence A",
                                    },
                                    {
                                        "sentence_id": "C0003:S001",
                                        "sentence_alias": "T0002",
                                        "text": "Sentence B",
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "scope_id": "HS0002",
                        "scope_alias": "H0002",
                        "heading_path": ["Scope B"],
                        "units": [
                            {
                                "unit_id": "TU0002",
                                "unit_alias": "U0002",
                                "sentences": [
                                    {
                                        "sentence_id": "C0004:S001",
                                        "sentence_alias": "T0003",
                                        "text": "Sentence C",
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ]
    )
    findings = build_findings(jobs=findings_jobs)
    if final_findings is None:
        final_findings = [
            {
                **finding,
                "comparison_mode_id": job["comparison_mode_id"],
                "source_finding_ids": [finding["finding_id"]],
            }
            for job in findings_jobs
            for finding in job["findings"]
        ]
    final_findings_payload = build_final_findings(
        finalization_status=finalization_status,
        fallback_comparison_modes=fallback_comparison_modes or [],
        findings=final_findings,
    )
    extract_bundle = {
        "doc_id": "doc_test",
        "file_name": "test.docx",
        "display_name": "test",
        "content_blocks": extract_blocks,
    }
    flow_summary = {
        "artifact_type": "document_consistency_qc_flow_run_summary",
        "schema_version": "0.11.0",
        "flow_id": "document_consistency_qc",
        "flow_run_id": flow_run_id,
        "capability_id": "internal_dsur",
        "source_language": "zh",
        "status": "success",
        "created_at": "2026-09-12T00:00:00Z",
        "completed_at": "2026-09-12T00:10:00Z",
        "slots": [
            {
                "slot_id": "source",
                "status": "success",
                "extract_config_id": "docx",
                "prepare_analysis_config_id": "pacfg_7f3a1c9e",
                "intake_run_id": "intake_source",
                "file_hash": _TEST_FILE_HASH,
                "doc_id": "doc_test",
                "extract_run_id": "extract_source",
                "prepare_analysis_run_id": "prepare_analysis_source",
                "analysis_bundle_path": (
                    slot_root / "prepare_analysis" / "analysis_bundle.json"
                ).as_posix(),
                "block_manifest_path": (
                    slot_root / "prepare_analysis" / "block_manifest.json"
                ).as_posix(),
                "prepare_analysis_run_summary_path": (
                    slot_root / "prepare_analysis" / "run_summary.json"
                ).as_posix(),
                "doc_meta_run_id": "doc_meta_source",
                "doc_meta_output_dir": (slot_root / "doc_meta").as_posix(),
                "doc_meta_bundle_path": (
                    slot_root / "doc_meta" / "doc_meta_bundle.json"
                ).as_posix(),
                "doc_meta_run_summary_path": (
                    slot_root / "doc_meta" / "run_summary.json"
                ).as_posix(),
            }
        ],
        "evidence_comparison": {
            "capability_id": "internal_dsur",
            "handoff_status": "ready",
            "stage_executed": True,
            "stage_executor_id": "clinical_trial_doc.clinical_safety.aggregate_evidence",
            "run_id": "evidence_comparison_internal_dsur",
            "output_dir": comparison_root.as_posix(),
            "run_status": "success",
            "run_summary_path": (comparison_root / "run_summary.json").as_posix(),
            "declared_output_path": (
                comparison_root / "final_findings.json"
            ).as_posix(),
            "participants": [
                {
                    "role_id": "source",
                    "slot_id": "source",
                    "semantic_module_id": "clinical_safety",
                    "declared_output_path": (
                        esp_root / "aggregate_evidence_source_bundle.json"
                    ).as_posix(),
                }
            ],
        },
    }

    save_json(comparison_root / "aggregate_comparison_evidence.json", ace)
    save_json(comparison_root / "findings.json", findings)
    save_json(comparison_root / "final_findings.json", final_findings_payload)
    save_json(
        comparison_root / "comparison_finding_assessment_jobs.json",
        {"capability_id": "internal_dsur", "jobs": plan_jobs},
    )
    save_json(
        comparison_root / "run_summary.json",
        {
            "run_id": "evidence_comparison_internal_dsur",
            "status": "success",
            "run_status": "success",
            "jobs": run_summary_jobs,
        },
    )
    save_json(esp_root / "aggregate_evidence_source_bundle.json", esp_bundle)
    save_json(extract_root / "bundle.json", extract_bundle)
    save_json(flow_root / "flow_run_summary.json", flow_summary)
    return flow_run_id


def _default_extract_blocks() -> list[dict]:
    return [
        {
            "block_id": "C0001",
            "kind": "heading",
            "heading_path": ["Scope A"],
            "doc_order_index": 1,
            "raw_text": "Scope A",
            "meta": {"heading_level": 1},
        },
        {
            "block_id": "C0002",
            "kind": "paragraph",
            "heading_path": ["Scope A"],
            "doc_order_index": 2,
            "raw_text": "Sentence A",
            "sentences": [
                {
                    "sentence_id": "C0002:S001",
                    "raw_text": "Sentence A",
                    "normalized_text": "Sentence A",
                }
            ],
        },
        {
            "block_id": "C0003",
            "kind": "paragraph",
            "heading_path": ["Scope A"],
            "doc_order_index": 3,
            "raw_text": "Sentence B",
            "sentences": [
                {
                    "sentence_id": "C0003:S001",
                    "raw_text": "Sentence B",
                    "normalized_text": "Sentence B",
                }
            ],
        },
        {
            "block_id": "C0005",
            "kind": "heading",
            "heading_path": ["Scope B"],
            "doc_order_index": 4,
            "raw_text": "Scope B",
            "meta": {"heading_level": 1},
        },
        {
            "block_id": "C0004",
            "kind": "paragraph",
            "heading_path": ["Scope B"],
            "doc_order_index": 5,
            "raw_text": "Sentence C",
            "sentences": [
                {
                    "sentence_id": "C0004:S001",
                    "raw_text": "Sentence C",
                    "normalized_text": "Sentence C",
                }
            ],
        },
    ]


def test_flat_final_findings_preserve_order_and_cross_section_evidence(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            },
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0002"]}],
            },
        ],
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [],
            },
            {
                "frozen_job_index": 2,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0002"]}
                ],
                "findings": [],
            },
        ],
        final_findings=[
            {
                "finding_id": "L031",
                "label": "need_review",
                "conclusion": "cross-section finding",
                "source_sentence_aliases": ["T0001", "T0003"],
                "comparison_mode_id": "focus_comparison",
                "source_finding_ids": ["L009", "L003"],
            },
            {
                "finding_id": "L002",
                "label": "fail",
                "conclusion": "second in product order",
                "source_sentence_aliases": ["T0002"],
                "comparison_mode_id": "scope_local",
                "source_finding_ids": ["L002"],
            },
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            },
            {
                "frozen_job_index": 2,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            },
        ],
        extract_blocks=_default_extract_blocks(),
    )

    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )

    assert [finding.finding_id for finding in result.findings] == ["L031", "L002"]
    assert [ref.sentence_alias for ref in result.findings[0].evidence_refs] == [
        "T0001",
        "T0003",
    ]
    assert [ref.block_id for ref in result.findings[0].evidence_refs] == [
        "C0002",
        "C0004",
    ]
    assert result.findings[0].source_finding_ids == ("L009", "L003")
    assert not hasattr(result.scope_results[0], "findings")
    comparison_root = (
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / "test_internal_result"
        / "participants"
        / "source"
        / "evidence_comparison"
    )
    assert (comparison_root / "findings.json").is_file()


def test_result_read_accepts_completed_with_fallback_empty_product(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
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

    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )

    assert result.finalization_status == "completed_with_fallback"
    assert result.fallback_comparison_modes == ("focus_comparison",)
    assert result.findings == ()


def test_resolve_owner_scope_alias_scope_local() -> None:
    owner = resolve_owner_scope_alias(
        comparison_mode_id="scope_local",
        comparison_groups=[
            {"group_role": "scope", "scope_aliases": ["H0001"]},
        ],
    )
    assert owner == "H0001"


def test_resolve_owner_scope_alias_focus_comparison() -> None:
    owner = resolve_owner_scope_alias(
        comparison_mode_id="focus_comparison",
        comparison_groups=[
            {"group_role": "focus_scope", "scope_aliases": ["H0002"]},
            {"group_role": "comparison_scopes", "scope_aliases": ["H0001"]},
        ],
    )
    assert owner == "H0002"


def test_resolve_owner_scope_alias_rejects_cross_mode() -> None:
    with pytest.raises(ResultReadUnsupportedComparisonModeError):
        resolve_owner_scope_alias(
            comparison_mode_id="ib_to_dsur",
            comparison_groups=[
                {"group_role": "ib_scope", "scope_aliases": ["H0001"]},
                {"group_role": "dsur_scopes", "scope_aliases": ["H0002"]},
            ],
        )


@pytest.mark.parametrize(
    ("run_job", "expected"),
    [
        (
            {
                "assessment": {"status": "success"},
                "assessment_second_pass": None,
                "verification": {"status": "success"},
            },
            ("success", None, "success", "success"),
        ),
        (
            {
                "assessment": {"status": "success"},
                "assessment_second_pass": {"status": "success"},
                "verification": None,
            },
            ("success", "success", None, "success"),
        ),
        (
            {
                "assessment": {"status": "failed"},
                "assessment_second_pass": None,
                "verification": None,
            },
            ("failed", None, None, "failed"),
        ),
        (
            {
                "assessment": {"status": "success"},
                "assessment_second_pass": None,
                "verification": {"status": "failed"},
            },
            ("success", None, "failed", "failed"),
        ),
        (
            {
                "assessment": {"status": "success"},
                "assessment_second_pass": {"status": "failed"},
                "verification": None,
            },
            ("success", "failed", None, "failed"),
        ),
        (
            {
                "assessment": {"status": "success"},
                "assessment_second_pass": None,
                "verification": None,
            },
            ("success", None, None, "failed"),
        ),
        (
            {
                "assessment": {"status": "success"},
                "assessment_second_pass": {"status": "success"},
                "verification": {"status": "success"},
            },
            ("success", "success", "success", "failed"),
        ),
    ],
)
def test_job_status_uses_executed_terminal_branch(
    run_job: dict,
    expected: tuple[str, str | None, str | None, str],
) -> None:
    assert _resolve_job_execution(run_job=run_job, frozen_job_index=1) == expected


def test_flat_findings_are_independent_from_scope_check_ownership(tmp_path: Path) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            },
            {
                "comparison_mode_id": "focus_comparison",
                "groups": [
                    {"group_role": "focus_scope", "scope_aliases": ["H0001"]},
                    {"group_role": "comparison_scopes", "scope_aliases": ["H0002"]},
                ],
            },
        ],
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [
                    {
                        "finding_id": "L001",
                        "label": "fail",
                        "conclusion": "fail one",
                        "source_sentence_aliases": ["T0001"],
                    },
                    {
                        "finding_id": "L002",
                        "label": "need_review",
                        "conclusion": "review one",
                        "source_sentence_aliases": ["T0002"],
                    },
                    {
                        "finding_id": "L003",
                        "label": "need_review",
                        "conclusion": "review two",
                        "source_sentence_aliases": ["T0001"],
                    },
                ],
            },
            {
                "frozen_job_index": 2,
                "comparison_mode_id": "focus_comparison",
                "comparison_groups": [
                    {"group_role": "focus_scope", "scope_aliases": ["H0001"]},
                    {
                        "group_role": "comparison_scopes",
                        "scope_aliases": ["H0002"],
                    },
                ],
                "findings": [
                    {
                        "finding_id": "L004",
                        "label": "fail",
                        "conclusion": "cross fail",
                        "source_sentence_aliases": ["T0001", "T0003"],
                    }
                ],
            },
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            },
            {
                "frozen_job_index": 2,
                "comparison_mode_id": "focus_comparison",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            },
        ],
        extract_blocks=_default_extract_blocks(),
    )

    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    scope_a = next(item for item in result.scope_results if item.scope_id == "HS0001")

    assert scope_a.outline_heading_block_id == "C0001"
    assert scope_a.execution_status == "complete"
    assert scope_a.has_successful_check is True
    assert [finding.finding_id for finding in result.findings] == [
        "L001",
        "L002",
        "L003",
        "L004",
    ]
    assert [finding.label for finding in result.findings] == [
        "fail",
        "need_review",
        "need_review",
        "fail",
    ]
    assert all(scope.scope_id != "HS0002" for scope in result.scope_results)


def test_heading_path_mapping_requires_exact_heading_block(tmp_path: Path) -> None:
    blocks = _default_extract_blocks()
    blocks = [block for block in blocks if block["block_id"] != "C0001"]
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
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
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            }
        ],
        extract_blocks=blocks,
    )

    with pytest.raises(
        ResultReadValidationError, match="unable to resolve extract heading"
    ):
        load_document_consistency_qc_result(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
        )


def test_duplicate_heading_path_fails(tmp_path: Path) -> None:
    blocks = _default_extract_blocks() + [
        {
            "block_id": "C0099",
            "kind": "heading",
            "heading_path": ["Scope A"],
            "doc_order_index": 99,
            "raw_text": "Scope A duplicate",
            "meta": {"heading_level": 1},
        }
    ]
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
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
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            }
        ],
        extract_blocks=blocks,
    )

    with pytest.raises(
        ResultReadValidationError, match="duplicate extract heading_path"
    ):
        load_document_consistency_qc_result(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
        )


def test_evidence_refs_use_canonical_sentence_and_block_ids(tmp_path: Path) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [
                    {
                        "finding_id": "L001",
                        "label": "fail",
                        "conclusion": "fail one",
                        "source_sentence_aliases": ["T0001"],
                    }
                ],
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

    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    evidence = result.findings[0].evidence_refs[0]
    assert evidence.sentence_id == "C0002:S001"
    assert evidence.block_id == "C0002"
    assert evidence.slot_id == "source"
    assert evidence.doc_id == "doc_test"
    assert evidence.sentence_alias == "T0001"


def test_scope_execution_status_partial_and_failed(tmp_path: Path) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            },
            {
                "comparison_mode_id": "focus_comparison",
                "groups": [
                    {"group_role": "focus_scope", "scope_aliases": ["H0001"]},
                    {"group_role": "comparison_scopes", "scope_aliases": ["H0002"]},
                ],
            },
        ],
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
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            },
            {
                "frozen_job_index": 2,
                "comparison_mode_id": "focus_comparison",
                "assessment": {"status": "failed"},
                "verification": None,
            },
        ],
        extract_blocks=_default_extract_blocks(),
    )

    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    scope_a = result.scope_results[0]
    assert scope_a.execution_status == "partial"
    assert scope_a.has_successful_check is True
    assert result.findings == ()


def test_successful_zero_findings_scope_still_present(tmp_path: Path) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
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

    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    assert len(result.scope_results) == 1
    assert result.findings == ()
    assert result.scope_results[0].execution_status == "complete"
    assert result.scope_results[0].has_successful_check is True


@pytest.mark.parametrize(
    "findings",
    [
        [],
        [
            {
                "finding_id": "L001",
                "label": "need_review",
                "conclusion": "second-pass issue",
                "source_sentence_aliases": ["T0001"],
            }
        ],
    ],
)
def test_successful_second_pass_job_is_complete_for_empty_or_non_empty_findings(
    tmp_path: Path,
    findings: list[dict],
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": findings,
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

    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    scope = result.scope_results[0]
    assert scope.execution_status == "complete"
    assert scope.has_successful_check is True
    assert len(result.findings) == len(findings)


def test_failed_job_preserved_from_plan_without_findings_entry(tmp_path: Path) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            },
            {
                "comparison_mode_id": "focus_comparison",
                "groups": [
                    {"group_role": "focus_scope", "scope_aliases": ["H0001"]},
                    {"group_role": "comparison_scopes", "scope_aliases": ["H0002"]},
                ],
            },
        ],
        findings_jobs=[
            {
                "frozen_job_index": 2,
                "comparison_mode_id": "focus_comparison",
                "comparison_groups": [
                    {"group_role": "focus_scope", "scope_aliases": ["H0001"]},
                    {
                        "group_role": "comparison_scopes",
                        "scope_aliases": ["H0002"],
                    },
                ],
                "findings": [],
            }
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "failed"},
                "verification": None,
            },
            {
                "frozen_job_index": 2,
                "comparison_mode_id": "focus_comparison",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            },
        ],
        extract_blocks=_default_extract_blocks(),
    )

    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    scope_a = result.scope_results[0]
    assert scope_a.execution_status == "partial"
    assert scope_a.has_successful_check is True
    assert result.findings == ()


def test_similar_findings_are_not_deduped(tmp_path: Path) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [
                    {
                        "finding_id": "L001",
                        "label": "fail",
                        "conclusion": "same text",
                        "source_sentence_aliases": ["T0001"],
                    },
                    {
                        "finding_id": "L002",
                        "label": "fail",
                        "conclusion": "same text",
                        "source_sentence_aliases": ["T0001"],
                    },
                ],
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

    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    assert len(result.findings) == 2
