"""Runtime and runner tests for Comparison Finding Assessment plan inspection."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan as discovery_runtime
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    serialize_comparison_finding_assessment_jobs,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan import (
    COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME,
    load_comparison_finding_assessment_jobs_from_plan,
    resolve_comparison_finding_assessment_plan_handoff,
    run_comparison_finding_assessment_plan_inspection,
)
from runtime.io import load_json, save_json
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    comparison_finding_assessment_plan_runner,
)


def _minimal_evidence(*, role_id: str = "source") -> dict:
    return build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": role_id,
                "aggregate_evidence_source_bundle_id": (
                    "aggregate_evidence_source_bundle_test"
                ),
                "doc_id": "doc_test",
                "file_hash": "sha256:test",
                "scopes": [
                    {
                        "scope_id": "HS0001",
                        "scope_alias": "H0001",
                        "heading_path": ["Heading one"],
                        "units": [
                            {
                                "unit_id": "TU0001",
                                "unit_alias": "U0001",
                                "sentences": [
                                    {
                                        "sentence_id": "C0001:S001",
                                        "sentence_alias": "T0001",
                                        "text": "one",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "scope_id": "HS0002",
                        "scope_alias": "H0002",
                        "heading_path": ["Heading two"],
                        "units": [
                            {
                                "unit_id": "TU0002",
                                "unit_alias": "U0002",
                                "sentences": [
                                    {
                                        "sentence_id": "C0002:S001",
                                        "sentence_alias": "T0002",
                                        "text": "two",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "scope_id": "HS0003",
                        "scope_alias": "H0003",
                        "heading_path": ["Heading three"],
                        "units": [
                            {
                                "unit_id": "TU0003",
                                "unit_alias": "U0003",
                                "sentences": [
                                    {
                                        "sentence_id": "C0003:S001",
                                        "sentence_alias": "T0003",
                                        "text": "three",
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ]
    )


def test_runner_delegates_to_runtime_only(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    save_json(evidence_path, _minimal_evidence())
    captured: dict[str, object] = {}

    def _fake_runtime(**kwargs):
        captured.update(kwargs)
        return type(
            "Report",
            (),
            {
                "messages": (
                    "run_id: test_run",
                    "comparison_finding_assessment_jobs: /tmp/jobs.json",
                    "run_summary: /tmp/run_summary.json",
                )
            },
        )()

    with patch.object(
        comparison_finding_assessment_plan_runner,
        "run_comparison_finding_assessment_plan_inspection",
        side_effect=_fake_runtime,
    ):
        comparison_finding_assessment_plan_runner.main(
            [
                "--evidence",
                str(evidence_path),
                "--capability",
                "internal_dsur",
                "--output-dir",
                str(tmp_path / "out"),
                "--run-id",
                "runner_test",
            ]
        )

    assert Path(str(captured["evidence"])) == evidence_path.resolve()
    assert captured["capability_id"] == "internal_dsur"
    assert Path(str(captured["output_dir"])) == (tmp_path / "out").resolve()
    assert captured["run_id"] == "runner_test"


def test_runtime_persists_inspection_json_and_summary(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    save_json(evidence_path, _minimal_evidence())
    output_dir = tmp_path / "output"

    report = run_comparison_finding_assessment_plan_inspection(
        project_root=tmp_path,
        evidence=evidence_path,
        capability_id="internal_dsur",
        output_dir=output_dir,
        run_id="inspection_test",
    )

    inspection = load_json(report.result.inspection_path)
    assert inspection["capability_id"] == "internal_dsur"
    assert len(inspection["jobs"]) == 6
    assert inspection["jobs"][0] == {
        "comparison_mode_id": "scope_local",
        "groups": [
            {
                "group_role": "scope",
                "scope_aliases": ["H0001"],
            }
        ],
    }
    assert "capability_id" not in inspection["jobs"][0]
    assert "schema_version" not in inspection
    assert "artifact_type" not in inspection

    summary = load_json(report.result.run_summary_path)
    assert summary["stage"] == "evidence_comparison"
    assert "document_type" not in summary
    assert summary["evidence_scope"] == "clinical_safety"
    assert summary["specialization"] == "aggregate"
    assert summary["phase"] == "comparison_finding_assessment_plan"
    assert summary["inputs"]["aggregate_comparison_evidence"]["path"] == (
        evidence_path.resolve().as_posix()
    )
    assert summary["inputs"]["capability_id"] == "internal_dsur"
    assert summary["inputs"]["participants"] == [
        {
            "role_id": "source",
            "aggregate_evidence_source_bundle_id": (
                "aggregate_evidence_source_bundle_test"
            ),
            "doc_id": "doc_test",
            "file_hash": "sha256:test",
        }
    ]
    assert summary["outputs"] == {
        "run_summary": "run_summary.json",
        "comparison_finding_assessment_jobs": COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME,
        "llm_inputs_dir": discovery_runtime.COMPARISON_FINDING_ASSESSMENT_LLM_INPUTS_DIRNAME,
    }
    assert summary["stats"]["participant_count"] == 1
    assert summary["stats"]["scope_count"] == 3
    assert summary["stats"]["job_count"] == 6
    assert summary["stats"]["llm_input_count"] == 6
    assert summary["stats"]["job_count_by_comparison_mode"] == {
        "scope_local": 3,
        "focus_comparison": 3,
    }
    assert {"doc_id", "file_hash"}.isdisjoint(summary)
    assert report.result.llm_inputs_dir == output_dir / "llm_inputs"
    assert report.result.llm_input_count == 6
    llm_inputs = sorted(report.result.llm_inputs_dir.glob("*.txt"))
    assert [path.name for path in llm_inputs] == [
        "001_scope_local.txt",
        "002_scope_local.txt",
        "003_scope_local.txt",
        "004_focus_comparison.txt",
        "005_focus_comparison.txt",
        "006_focus_comparison.txt",
    ]
    assert llm_inputs[0].read_text(encoding="utf-8") == (
        "Scope: Heading one\nUnit U0001\n- one [T0001]"
    )


def test_job_serialization_excludes_capability_id() -> None:
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
        ComparisonFindingAssessmentGroup,
        ComparisonFindingAssessmentJob,
    )

    payload = serialize_comparison_finding_assessment_jobs(
        capability_id="internal_ib",
        jobs=(
            ComparisonFindingAssessmentJob(
                comparison_mode_id="scope_local",
                groups=(
                    ComparisonFindingAssessmentGroup(
                        group_role="scope",
                        scope_aliases=("H0001",),
                    ),
                ),
            ),
        ),
    )
    assert payload["capability_id"] == "internal_ib"
    assert "capability_id" not in payload["jobs"][0]


def test_invalid_evidence_fails_before_persisting_outputs(tmp_path: Path) -> None:
    evidence_path = tmp_path / "invalid.json"
    invalid = _minimal_evidence()
    invalid["schema_version"] = "9.9.9"
    save_json(evidence_path, invalid)
    output_dir = tmp_path / "output"

    with pytest.raises(ValueError, match="schema_version"):
        run_comparison_finding_assessment_plan_inspection(
            project_root=tmp_path,
            evidence=evidence_path,
            capability_id="internal_dsur",
            output_dir=output_dir,
        )

    assert not (output_dir / COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME).exists()


def test_default_output_uses_comparison_finding_assessment_plan_run_layout(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "evidence.json"
    save_json(evidence_path, _minimal_evidence())

    report = run_comparison_finding_assessment_plan_inspection(
        project_root=tmp_path,
        evidence=evidence_path,
        capability_id="internal_csr",
    )

    relative = report.result.output_dir.relative_to(tmp_path)
    assert relative.parts[:5] == (
        "runs",
        "evidence_comparison",
        "clinical_safety",
        "aggregate",
        "comparison_finding_assessment_plan",
    )
    assert relative.parts[5] == report.result.run_id


_CROSS_ARTIFACT = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
    / "dsur_updated_ib"
    / "aggregate_comparison_evidence.json"
)


def test_cross_runtime_summary_preserves_participant_provenance(tmp_path: Path) -> None:
    report = run_comparison_finding_assessment_plan_inspection(
        project_root=tmp_path,
        evidence=_CROSS_ARTIFACT,
        capability_id="dsur_updated_ib",
        output_dir=tmp_path / "cross_output",
        run_id="cross_inspection",
    )
    summary = load_json(report.result.run_summary_path)
    assert len(summary["inputs"]["participants"]) == 2
    assert summary["inputs"]["participants"][0]["role_id"] == "source_a"
    assert summary["inputs"]["participants"][1]["role_id"] == "source_b"
    assert summary["stats"]["job_count"] == 6


def test_loader_round_trip_matches_serialized_jobs(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    save_json(evidence_path, _minimal_evidence())
    report = run_comparison_finding_assessment_plan_inspection(
        project_root=tmp_path,
        evidence=evidence_path,
        capability_id="internal_dsur",
        output_dir=tmp_path / "plan_output",
        run_id="loader_round_trip",
    )
    capability_id, loaded_jobs = load_comparison_finding_assessment_jobs_from_plan(
        report.result.output_dir
    )
    assert capability_id == "internal_dsur"
    assert len(loaded_jobs) == 6
    inspection = load_json(report.result.inspection_path)
    for index, loaded_job in enumerate(loaded_jobs):
        expected = inspection["jobs"][index]
        assert loaded_job.comparison_mode_id == expected["comparison_mode_id"]
        assert [
            {
                "group_role": group.group_role,
                "scope_aliases": list(group.scope_aliases),
            }
            for group in loaded_job.groups
        ] == expected["groups"]


def test_plan_handoff_resolver_reads_evidence_path(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    save_json(evidence_path, _minimal_evidence())
    report = run_comparison_finding_assessment_plan_inspection(
        project_root=tmp_path,
        evidence=evidence_path,
        capability_id="internal_csr",
        output_dir=tmp_path / "handoff_output",
        run_id="handoff_test",
    )
    handoff = resolve_comparison_finding_assessment_plan_handoff(report.result.output_dir)
    assert handoff.plan_run_id == "handoff_test"
    assert handoff.capability_id == "internal_csr"
    assert handoff.evidence_path == evidence_path.resolve()
    assert len(handoff.frozen_jobs) == 6
    assert len(handoff.participant_provenance) == 1
