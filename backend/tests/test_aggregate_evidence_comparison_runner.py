"""Standalone Aggregate Evidence Comparison runner tests."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_FILENAME,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    AGGREGATE_COMPARISON_EVIDENCE_FILENAME,
    FINDINGS_FILENAME,
    validate_final_findings,
)
from execution_flow.document_consistency_qc.evidence_comparison_produced_outputs import (
    collect_produced_evidence_source_preparation_outputs_from_flow_execution,
)
from llm.providers.base import LLMRawResult
from operations.evidence_comparison.handoff import (
    EvidenceComparisonHandoffResolutionStatus,
    resolve_evidence_comparison_handoff,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
    EvidenceComparisonStageResult,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
    RUN_SUMMARY_FILENAME,
)
from runtime.io import load_json, save_json
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    aggregate_evidence_comparison_runner,
)
from tests.current_evidence_comparison_test_helpers import (
    write_current_ec_source_fixture,
)


def _flow_run_id_from_session(session: str) -> str:
    return f"document_consistency_qc_{session}"


def _write_minimal_flow_run_summary(
    *,
    project_root: Path,
    flow_run_id: str,
    capability_id: str,
    slot_esp_outputs: dict[str, Path],
) -> Path:
    session = flow_run_id.removeprefix("document_consistency_qc_")
    flow_root = project_root / "runs" / "document_consistency_qc" / session
    flow_root.mkdir(parents=True, exist_ok=True)

    slots = []
    for slot_id, bundle_path in slot_esp_outputs.items():
        route_dir = flow_root / "participants" / slot_id / "route"
        route_dir.mkdir(parents=True, exist_ok=True)
        esp_run_summary = bundle_path.parent / "run_summary.json"
        esp_run_summary.write_text("{}", encoding="utf-8")
        routing_manifest = route_dir / "routing_manifest.json"
        routing_manifest.write_text("{}", encoding="utf-8")
        route_run_summary = route_dir / "run_summary.json"
        route_run_summary.write_text("{}", encoding="utf-8")
        slots.append(
            {
                "slot_id": slot_id,
                "status": "partial",
                "extract_config_id": "docx",
                "prepare_analysis_config_id": "pacfg_test",
                "filter_job_ids": ["dsur_clinical_safety"],
                "route_semantic_modules": [
                    {
                        "semantic_module_id": CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
                        "selected_projected_source_count": 1,
                        "route_invoked": True,
                        "route_run_id": f"route_{slot_id}",
                        "output_dir": route_dir.as_posix(),
                        "routing_manifest_path": routing_manifest.as_posix(),
                        "run_summary_path": route_run_summary.as_posix(),
                        "evidence_source_preparation_invoked": True,
                        "evidence_source_preparation_run_id": f"esp_{slot_id}",
                        "evidence_source_preparation_stage_executor_id": (
                            "clinical_trial_doc.aggregate_evidence"
                        ),
                        "evidence_source_preparation_declared_output_path": (
                            bundle_path.resolve().as_posix()
                        ),
                        "evidence_source_preparation_run_summary_path": (
                            esp_run_summary.as_posix()
                        ),
                    }
                ],
            }
        )

    summary = {
        "artifact_type": "document_consistency_qc_flow_run_summary",
        "schema_version": "0.13.0",
        "flow_id": "document_consistency_qc",
        "flow_run_id": flow_run_id,
        "capability_id": capability_id,
        "source_language": "zh",
        "status": "partial",
        "created_at": "2026-09-23T00:00:00Z",
        "completed_at": "2026-09-23T00:00:01Z",
        "slots": slots,
        "candidate_scope_decision_mode": "automatic_continue",
    }
    summary_path = flow_root / FLOW_RUN_SUMMARY_FILENAME
    save_json(summary_path, summary)
    return flow_root


def _first_alias(messages: list[dict[str, str]]) -> str:
    match = re.search(r"\[(T\d{4})\]", messages[-1]["content"])
    if match is None:
        raise AssertionError("expected sentence alias in prompt")
    return match.group(1)


def _extract_verification_finding_ids(user_content: str) -> list[str]:
    marker = "## Findings\n"
    marker_index = user_content.find(marker)
    if marker_index == -1:
        return []
    findings_section = user_content[marker_index + len(marker) :]
    finding_ids: list[str] = []
    for line in findings_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("L") and len(stripped) == 4 and stripped[1:].isdigit():
            finding_ids.append(stripped)
    return finding_ids


class _FullPipelineProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        if "## Conclusions" in user_content:
            return LLMRawResult(
                provider_name="runner-mock",
                model="runner-mock",
                raw_text=json.dumps({"consolidated_groups": []}),
            )
        if "## Findings" in user_content:
            finding_ids = _extract_verification_finding_ids(user_content)
            return LLMRawResult(
                provider_name="runner-mock",
                model="runner-mock",
                raw_text=json.dumps(
                    {
                        "finding_verifications": [
                            {
                                "finding_id": finding_id,
                                "verification_result": "confirmed",
                            }
                            for finding_id in finding_ids
                        ],
                        "additional_findings": [],
                    }
                ),
            )
        alias = _first_alias(messages)
        return LLMRawResult(
            provider_name="runner-mock",
            model="runner-mock",
            raw_text=json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": f"candidate for {alias}",
                            "label": "fail",
                            "trigger_sentence_aliases": [alias],
                        }
                    ]
                }
            ),
        )


class _EmptyAssessmentProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="runner-empty-mock",
            model="runner-empty-mock",
            raw_text=json.dumps({"candidates": []}),
        )


class _FailingProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        raise RuntimeError("provider unavailable")


def test_single_document_flow_provenance_rebuilds_ready_handoff(
    tmp_path: Path,
) -> None:
    bundle = write_current_ec_source_fixture(
        tmp_path / "bundles",
        label="source",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    flow_run_id = _flow_run_id_from_session("20260930_single_doc")
    _write_minimal_flow_run_summary(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        capability_id="internal_dsur",
        slot_esp_outputs={"source": bundle},
    )

    from execution_flow.document_consistency_qc.flow_loader import (
        load_flow_run_execution,
    )

    execution = load_flow_run_execution(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    produced = collect_produced_evidence_source_preparation_outputs_from_flow_execution(
        execution
    )
    assert len(produced) == 1
    assert produced[0].slot_id == "source"
    assert produced[0].semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert produced[0].declared_output_path == bundle.resolve()

    composition = build_installed_document_consistency_qc_application_composition()
    binding = composition.evidence_comparison_consumer_bindings.resolve_consumer_binding(
        "internal_dsur"
    )
    resolution = resolve_evidence_comparison_handoff(
        consumer_binding=binding,
        produced_outputs=produced,
    )
    assert resolution.status is EvidenceComparisonHandoffResolutionStatus.READY
    assert resolution.handoff is not None
    assert [participant.role_id for participant in resolution.handoff.participants] == [
        "source"
    ]


def test_cross_document_flow_provenance_rebuilds_ready_handoff(
    tmp_path: Path,
) -> None:
    bundle_a = write_current_ec_source_fixture(
        tmp_path / "bundles",
        label="source_a",
        document_type="dsur",
        heading_paths=(("Safety findings",),),
    )
    bundle_b = write_current_ec_source_fixture(
        tmp_path / "bundles",
        label="source_b",
        document_type="ib",
        heading_paths=(("Safety findings",),),
    )
    flow_run_id = _flow_run_id_from_session("20260930_cross_doc")
    _write_minimal_flow_run_summary(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        capability_id="dsur_updated_ib",
        slot_esp_outputs={"source_a": bundle_a, "source_b": bundle_b},
    )

    from execution_flow.document_consistency_qc.flow_loader import (
        load_flow_run_execution,
    )

    execution = load_flow_run_execution(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
    )
    produced = collect_produced_evidence_source_preparation_outputs_from_flow_execution(
        execution
    )
    composition = build_installed_document_consistency_qc_application_composition()
    binding = composition.evidence_comparison_consumer_bindings.resolve_consumer_binding(
        "dsur_updated_ib"
    )
    resolution = resolve_evidence_comparison_handoff(
        consumer_binding=binding,
        produced_outputs=produced,
    )
    assert resolution.status is EvidenceComparisonHandoffResolutionStatus.READY
    assert [participant.role_id for participant in resolution.handoff.participants] == [
        "source_a",
        "source_b",
    ]


def test_runner_calls_run_evidence_comparison_stage_with_installed_stage_executor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bundle = write_current_ec_source_fixture(
        tmp_path / "bundles",
        label="source",
        document_type="dsur",
        heading_paths=(("Safety findings",),),
    )
    flow_run_id = _flow_run_id_from_session("20260930_stage_boundary")
    _write_minimal_flow_run_summary(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        capability_id="internal_dsur",
        slot_esp_outputs={"source": bundle},
    )

    composition = build_installed_document_consistency_qc_application_composition()
    expected_executor = (
        composition.evidence_comparison_consumer_bindings.resolve_consumer_binding(
            "internal_dsur"
        ).stage_executor
    )
    stage_calls: list[tuple[object, object]] = []

    def recording_stage(*, stage_input, stage_executor):
        stage_calls.append((stage_input, stage_executor))
        return EvidenceComparisonStageResult(
            output_dir=stage_input.context.output_dir,
            run_id=stage_input.context.run_id or "recorded_run",
            stage_executor_id="recording.stage",
            run_status="success",
            run_summary_path=stage_input.context.output_dir / RUN_SUMMARY_FILENAME,
            declared_output_path=None,
        )

    monkeypatch.setattr(
        aggregate_evidence_comparison_runner,
        "materialize_installed_evidence_comparison_execution_dependencies",
        lambda **kwargs: EvidenceComparisonExecutionDependencies(),
    )
    monkeypatch.setattr(
        aggregate_evidence_comparison_runner,
        "run_evidence_comparison_stage",
        recording_stage,
    )

    out_dir = tmp_path / "standalone_out"
    result = aggregate_evidence_comparison_runner.run_standalone_aggregate_evidence_comparison_from_flow_run(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        output_dir=out_dir,
        run_id="runner_stage_boundary",
    )

    assert result.run_status == "success"
    assert len(stage_calls) == 1
    stage_input, stage_executor = stage_calls[0]
    assert stage_executor is expected_executor
    assert stage_input.context.output_dir == out_dir.resolve()
    assert stage_input.context.run_id == "runner_stage_boundary"


def test_runner_normal_branch_uses_canonical_stage_persistence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bundle = write_current_ec_source_fixture(
        tmp_path / "bundles",
        label="source",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    flow_run_id = _flow_run_id_from_session("20260930_normal_branch")
    _write_minimal_flow_run_summary(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        capability_id="internal_dsur",
        slot_esp_outputs={"source": bundle},
    )

    provider = _FullPipelineProvider()

    def materialize_with_mock(**kwargs):
        from application.clinical_trial_doc_consistency_qc.execution import (
            materialize_installed_evidence_comparison_execution_dependencies as real_materialize,
        )

        return real_materialize(
            **kwargs,
            assessment_provider=provider,
            assessment_second_pass_provider=provider,
            verification_provider=provider,
            consolidation_provider=provider,
        )

    monkeypatch.setattr(
        aggregate_evidence_comparison_runner,
        "materialize_installed_evidence_comparison_execution_dependencies",
        materialize_with_mock,
    )

    out_dir = tmp_path / "normal_branch_out"
    result = aggregate_evidence_comparison_runner.run_standalone_aggregate_evidence_comparison_from_flow_run(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        output_dir=out_dir,
        run_id="runner_normal_branch",
    )

    assert result.run_status == "success"
    assert result.declared_output_path is not None
    validate_final_findings(load_json(result.declared_output_path))
    assert (out_dir / AGGREGATE_COMPARISON_EVIDENCE_FILENAME).is_file()
    assert (out_dir / RUN_SUMMARY_FILENAME).is_file()
    assert (out_dir / FINDINGS_FILENAME).is_file()
    run_summary = load_json(out_dir / RUN_SUMMARY_FILENAME)
    assert run_summary["phase"] == "evidence_comparison"
    assert run_summary["stats"]["verification_success_count"] >= 1


def test_runner_second_pass_branch_uses_canonical_stage_persistence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bundle = write_current_ec_source_fixture(
        tmp_path / "bundles",
        label="source",
        document_type="dsur",
        heading_paths=(("Safety findings",),),
    )
    flow_run_id = _flow_run_id_from_session("20260930_second_pass")
    _write_minimal_flow_run_summary(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        capability_id="internal_dsur",
        slot_esp_outputs={"source": bundle},
    )

    primary = _EmptyAssessmentProvider()
    second_pass = _FullPipelineProvider()

    def materialize_with_mock(**kwargs):
        from application.clinical_trial_doc_consistency_qc.execution import (
            materialize_installed_evidence_comparison_execution_dependencies as real_materialize,
        )

        return real_materialize(
            **kwargs,
            assessment_provider=primary,
            assessment_second_pass_provider=second_pass,
            verification_provider=_FailingProvider(),
            consolidation_provider=_FullPipelineProvider(),
        )

    monkeypatch.setattr(
        aggregate_evidence_comparison_runner,
        "materialize_installed_evidence_comparison_execution_dependencies",
        materialize_with_mock,
    )

    out_dir = tmp_path / "second_pass_out"
    result = aggregate_evidence_comparison_runner.run_standalone_aggregate_evidence_comparison_from_flow_run(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        output_dir=out_dir,
        run_id="runner_second_pass",
    )

    assert result.run_status == "success"
    run_summary = load_json(out_dir / RUN_SUMMARY_FILENAME)
    assert run_summary["stats"]["assessment_second_pass_success_count"] >= 1
    assert run_summary["stats"]["verification_success_count"] == 0
    job_root = Path(run_summary["jobs"][0]["assessment"]["job_dir"])
    assert (job_root / "assessment" / "second_pass" / "result.txt").is_file()


def test_runner_does_not_modify_source_flow_run_summary(tmp_path: Path, monkeypatch) -> None:
    bundle = write_current_ec_source_fixture(
        tmp_path / "bundles",
        label="source",
        document_type="dsur",
        heading_paths=(("Safety findings",),),
    )
    flow_run_id = _flow_run_id_from_session("20260930_immutable_flow")
    flow_root = _write_minimal_flow_run_summary(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        capability_id="internal_dsur",
        slot_esp_outputs={"source": bundle},
    )
    summary_path = flow_root / FLOW_RUN_SUMMARY_FILENAME
    before = summary_path.read_text(encoding="utf-8")

    monkeypatch.setattr(
        aggregate_evidence_comparison_runner,
        "materialize_installed_evidence_comparison_execution_dependencies",
        lambda **kwargs: EvidenceComparisonExecutionDependencies(),
    )
    monkeypatch.setattr(
        aggregate_evidence_comparison_runner,
        "run_evidence_comparison_stage",
        lambda **kwargs: EvidenceComparisonStageResult(
            output_dir=kwargs["stage_input"].context.output_dir,
            run_id="mock_run",
            stage_executor_id="mock",
            run_status="success",
            run_summary_path=kwargs["stage_input"].context.output_dir / "run_summary.json",
            declared_output_path=None,
        ),
    )

    aggregate_evidence_comparison_runner.run_standalone_aggregate_evidence_comparison_from_flow_run(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        output_dir=tmp_path / "immutable_out",
        run_id="immutable_ec_run",
    )

    assert summary_path.read_text(encoding="utf-8") == before


def test_runner_missing_flow_run_id_exits_with_message(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="canonical flow output directory not found"):
        aggregate_evidence_comparison_runner.main(
            [
                "--flow-run-id",
                "document_consistency_qc_missing",
                "--project-root",
                str(tmp_path),
            ]
        )


def test_runner_handoff_not_ready_exits_with_message(tmp_path: Path) -> None:
    flow_run_id = _flow_run_id_from_session("20260930_no_esp")
    session = flow_run_id.removeprefix("document_consistency_qc_")
    flow_root = tmp_path / "runs" / "document_consistency_qc" / session
    flow_root.mkdir(parents=True)
    save_json(
        flow_root / FLOW_RUN_SUMMARY_FILENAME,
        {
            "artifact_type": "document_consistency_qc_flow_run_summary",
            "schema_version": "0.13.0",
            "flow_id": "document_consistency_qc",
            "flow_run_id": flow_run_id,
            "capability_id": "internal_dsur",
            "source_language": "zh",
            "status": "partial",
            "created_at": "2026-09-23T00:00:00Z",
            "completed_at": "2026-09-23T00:00:01Z",
            "slots": [
                {
                    "slot_id": "source",
                    "status": "partial",
                    "extract_config_id": "docx",
                    "prepare_analysis_config_id": "pacfg_test",
                    "filter_job_ids": ["dsur_clinical_safety"],
                    "route_semantic_modules": [
                        {
                            "semantic_module_id": CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
                            "selected_projected_source_count": 0,
                            "route_invoked": False,
                            "evidence_source_preparation_invoked": False,
                        }
                    ],
                }
            ],
            "candidate_scope_decision_mode": "automatic_continue",
        },
    )

    with pytest.raises(SystemExit, match="no usable ESP outputs"):
        aggregate_evidence_comparison_runner.main(
            [
                "--flow-run-id",
                flow_run_id,
                "--project-root",
                str(tmp_path),
            ]
        )


def test_runner_is_thin_wrapper_boundary() -> None:
    source = Path(aggregate_evidence_comparison_runner.__file__).read_text(encoding="utf-8")
    assert "run_aggregate_evidence_comparison_execution" not in source
    assert "execute_clinical_trial_aggregate_evidence_comparison_stage" not in source
    assert "run_evidence_comparison_stage" in source
