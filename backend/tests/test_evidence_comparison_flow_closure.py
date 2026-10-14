"""Flow closure tests for installed Evidence Comparison (Slice 3D)."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.flow as flow_module
from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.execution import (
    materialize_installed_evidence_comparison_execution_dependencies,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from application.clinical_trial_doc_consistency_qc.result_readiness import (
    probe_result_readiness,
)
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_FILENAME,
    validate_flow_run_summary,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    FINDINGS_FILENAME,
    validate_final_findings,
)
from capability import DSUR_UPDATED_IB_CONSISTENCY_QC, INTERNAL_DSUR_CONSISTENCY_QC
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantRunInput,
    DocumentConsistencyQcParticipantSlot,
)
from llm.providers.base import LLMRawResult
from operations.evidence_comparison.consumer_bindings import (
    EvidenceComparisonConsumerBinding,
    EvidenceComparisonConsumerBindings,
)
from operations.evidence_comparison.handoff import (
    EvidenceComparisonHandoffResolutionStatus,
)
from operations.evidence_comparison.participants import (
    EvidenceComparisonParticipantRequirement,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
    EvidenceComparisonStageInput,
    EvidenceComparisonStageResult,
)
from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBindings,
)
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationExecutionDependencies,
    EvidenceSourcePreparationStageResult,
)
from operations.prepare_analysis import PrepareAnalysisRequestOptions
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.profiles import (
    DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE,
    DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE,
)
from plugins.clinical_trial_doc.prepare_analysis.config import (
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    ClinicalPreparePrivacyConfig,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID,
    ClinicalTrialAggregateEvidenceComparisonExecutionDependencies,
)
from runtime.io import load_json
from tests.current_evidence_comparison_test_helpers import (
    write_current_ec_source_fixture,
)

FLOW_PATH = BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "flow.py"
CONSOLIDATION_PLUGIN_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
    / "comparison_finding_consolidation"
)


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
    finding_ids: list[str] = []
    for line in user_content[marker_index + len(marker) :].splitlines():
        stripped = line.strip()
        if stripped.startswith("L") and len(stripped) == 4 and stripped[1:].isdigit():
            finding_ids.append(stripped)
    return finding_ids


class _RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls.append(messages)
        user_content = messages[-1]["content"]
        if "## Conclusions" in user_content:
            return LLMRawResult(
                provider_name="flow-closure-mock",
                model="flow-closure-mock",
                raw_text=json.dumps({"consolidated_groups": []}),
            )
        if "## Findings" in user_content:
            finding_ids = _extract_verification_finding_ids(user_content)
            return LLMRawResult(
                provider_name="flow-closure-mock",
                model="flow-closure-mock",
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
            provider_name="flow-closure-mock",
            model="flow-closure-mock",
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


def _slot_result(
    tmp_path: Path,
    slot_id: str,
    *,
    bundle_path: Path,
    semantic_module_id: str = CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
):
    esp_output_dir = tmp_path / slot_id / "esp"
    esp_output_dir.mkdir(parents=True, exist_ok=True)
    declared_output_path = bundle_path
    run_summary_path = esp_output_dir / "run_summary.json"
    run_summary_path.write_text("{}", encoding="utf-8")
    esp_result = EvidenceSourcePreparationStageResult(
        output_dir=esp_output_dir,
        run_id=f"esp_{slot_id}",
        doc_id=f"doc_{slot_id}",
        semantic_module_id=semantic_module_id,
        stage_executor_id="recording.esp",
        declared_output_path=declared_output_path,
        run_summary_path=run_summary_path,
    )
    from runtime.document_source_binding import DocumentIntakeSourceBinding

    return flow_module.DocumentConsistencyQcSlotResult(
        slot_id=slot_id,
        admitted_source=DocumentIntakeSourceBinding(
            file_hash=f"sha256:{slot_id}",
            original_file_name=f"{slot_id}.docx",
            source_path=tmp_path / f"{slot_id}.docx",
        ),
        extract_report=SimpleNamespace(
            result=SimpleNamespace(run_id=f"extract_{slot_id}")
        ),
        prepare_analysis_report=SimpleNamespace(
            documents=(SimpleNamespace(run_id=f"prepare_{slot_id}"),)
        ),
        doc_meta_report={"output_dir": str(tmp_path / slot_id / "doc_meta")},
        route_semantic_module_results=(
            flow_module.RouteSemanticModuleFlowResult(
                semantic_module_id=semantic_module_id,
                selected_projected_source_count=1,
                route_invoked=True,
                evidence_source_preparation_invoked=True,
                evidence_source_preparation_stage_result=esp_result,
            ),
        ),
    )


def _admitted_source_fixture(*, project_root: Path, slot_id: str):
    from runtime.document_source_binding import DocumentIntakeSourceBinding

    source_path = project_root / f"{slot_id}.docx"
    source_path.write_bytes(b"fixture")
    return DocumentIntakeSourceBinding(
        file_hash="sha256:" + ("0" * 64),
        original_file_name=f"{slot_id}.docx",
        source_path=source_path,
    )


def _flow_kwargs(
    *,
    project_root: Path,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    composition,
    registry: PrepareAnalysisConfigRegistry,
    participant_input: DocumentConsistencyQcParticipantRunInput,
    materializer,
    consumer_bindings=None,
):
    binding_keys = {
        (capability_config.capability_id, slot.slot_id): next(
            iter(composition.prepare_analysis_bindings.values())
        )
        for slot in capability_config.slots
    }
    return {
        "capability_config": capability_config,
        "uploads": {
            slot.slot_id: _admitted_source_fixture(
                project_root=project_root,
                slot_id=slot.slot_id,
            )
            for slot in capability_config.slots
        },
        "participant_inputs": {
            slot.slot_id: participant_input for slot in capability_config.slots
        },
        "source_language": "zh",
        "extract_bindings": {key: "docx" for key in binding_keys},
        "prepare_analysis_bindings": binding_keys,
        "filter_job_bindings": {key: () for key in binding_keys},
        "prepare_analysis_config_registry": registry,
        "doc_meta_profile": composition.doc_meta_profile,
        "doc_meta_summary_builder": composition.doc_meta_summary_builder,
        "filter_job_variants": {},
        "filter_output_projection_jobs": {},
        "filter_output_projection_facade_builder": lambda **kwargs: None,
        "projected_source_route_executor": lambda **kwargs: None,
        "route_semantic_module_sequence": (),
        "evidence_source_preparation_consumer_bindings": (
            EvidenceSourcePreparationConsumerBindings(bindings={})
        ),
        "evidence_source_preparation_execution_dependencies": (
            EvidenceSourcePreparationExecutionDependencies()
        ),
        "evidence_comparison_consumer_bindings": (
            consumer_bindings
            if consumer_bindings is not None
            else composition.evidence_comparison_consumer_bindings
        ),
        "materialize_evidence_comparison_execution_dependencies": materializer,
    }


def _mark_slot_provenance_success(slot_provenance) -> None:
    slot_provenance.status = "success"
    slot_id = slot_provenance.slot_id
    slot_provenance.intake_run_id = f"intake_{slot_id}"
    slot_provenance.file_hash = "sha256:" + ("0" * 64)
    slot_provenance.original_file_name = f"{slot_id}.docx"
    slot_provenance.doc_id = f"doc_{slot_id}"
    slot_provenance.extract_run_id = f"extract_{slot_id}"
    slot_provenance.prepare_analysis_run_id = f"prepare_{slot_id}"
    slot_provenance.analysis_bundle_path = f"/tmp/{slot_id}/analysis_bundle.json"
    slot_provenance.block_manifest_path = f"/tmp/{slot_id}/block_manifest.json"
    slot_provenance.prepare_analysis_run_summary_path = (
        f"/tmp/{slot_id}/prepare_analysis/run_summary.json"
    )
    slot_provenance.doc_meta_run_id = f"doc_meta_{slot_id}"
    slot_provenance.doc_meta_output_dir = f"/tmp/{slot_id}/doc_meta"
    slot_provenance.doc_meta_bundle_path = (
        f"/tmp/{slot_id}/doc_meta/doc_meta_bundle.json"
    )
    slot_provenance.doc_meta_run_summary_path = (
        f"/tmp/{slot_id}/doc_meta/run_summary.json"
    )


def _run_flow_with_mock_slots(
    tmp_path: Path,
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    slot_bundle_paths: dict[str, Path],
    materializer,
    consumer_bindings=None,
):
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    participant_input = DocumentConsistencyQcParticipantRunInput(
        prepare_analysis_request_options=PrepareAnalysisRequestOptions(
            ClinicalPreparePrivacyConfig.identity()
        )
    )

    def fake_run_slot(*, slot, slot_provenance=None, **kwargs):
        if slot_provenance is not None:
            _mark_slot_provenance_success(slot_provenance)
        return _slot_result(
            tmp_path,
            slot.slot_id,
            bundle_path=slot_bundle_paths[slot.slot_id],
        )

    with patch.object(flow_module, "_run_slot", side_effect=fake_run_slot):
        return flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            **_flow_kwargs(
                project_root=tmp_path,
                capability_config=capability_config,
                composition=composition,
                registry=registry,
                participant_input=participant_input,
                materializer=materializer,
                consumer_bindings=consumer_bindings,
            ),
        )


def _load_flow_summary(report) -> dict:
    summary_path = report.flow_run_summary_path
    payload = load_json(summary_path)
    validate_flow_run_summary(payload)
    return payload


def _write_internal_dsur_source_bundle(tmp_path: Path, *, label: str) -> Path:
    return write_current_ec_source_fixture(
        tmp_path,
        label=label,
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )


def _write_cross_source_bundles(tmp_path: Path) -> tuple[Path, Path]:
    dsur_path = write_current_ec_source_fixture(
        tmp_path,
        label="cross_dsur",
        document_type="dsur",
        heading_paths=((DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE.include_terms[0],),),
    )
    ib_path = write_current_ec_source_fixture(
        tmp_path,
        label="cross_ib",
        document_type="ib",
        heading_paths=((DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE.include_terms[0],),),
    )
    return dsur_path, ib_path


def test_flow_module_has_no_concrete_evidence_comparison_imports() -> None:
    tree = ast.parse(FLOW_PATH.read_text(encoding="utf-8"), filename=str(FLOW_PATH))
    forbidden_prefixes = (
        "application.clinical_trial_doc_consistency_qc",
        "plugins.clinical_trial_doc.evidence_comparison",
        "runtime.evidence_comparison.clinical_trial_doc",
    )
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        else:
            continue
        for imported in modules:
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden_prefixes
            ):
                violations.append(imported)
    assert not violations, "\n".join(violations)


def test_consolidation_core_is_mode_neutral_and_layer_ownership_is_preserved() -> None:
    generic_core_files = (
        "input_materialization.py",
        "response_validation.py",
        "alias_qc.py",
        "execution.py",
    )
    for file_name in generic_core_files:
        source = (CONSOLIDATION_PLUGIN_ROOT / file_name).read_text(encoding="utf-8")
        assert "FocusComparison" not in source
        assert "focus_comparison" not in source
        assert "focus-specific" not in source

    artifacts_root = BACKEND_ROOT / "artifacts"
    assert not tuple(artifacts_root.rglob("*consolidation*"))
    plugin_dependencies = (
        CONSOLIDATION_PLUGIN_ROOT.parent / "dependencies.py"
    ).read_text(encoding="utf-8")
    application_execution = (
        BACKEND_ROOT
        / "application"
        / "clinical_trial_doc_consistency_qc"
        / "execution.py"
    ).read_text(encoding="utf-8")
    runtime_persistence = (
        BACKEND_ROOT
        / "runtime"
        / "evidence_comparison"
        / "clinical_trial_doc"
        / "clinical_safety"
        / "aggregate_evidence"
        / "persistence.py"
    ).read_text(encoding="utf-8")
    assert "materialize_llm_provider" not in plugin_dependencies
    assert "materialize_llm_provider" in application_execution
    assert "_persist_consolidation_execution" in runtime_persistence


def test_ready_single_participant_production_flow_success(
    tmp_path: Path,
) -> None:
    source_bundle = _write_internal_dsur_source_bundle(
        tmp_path,
        label="flow_internal_dsur",
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    provider = _RecordingProvider()
    materializer = lambda capability_id: (
        materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id=capability_id,
            assessment_provider=provider,
            assessment_second_pass_provider=provider,
            verification_provider=provider,
            consolidation_provider=provider,
        )
    )
    report = _run_flow_with_mock_slots(
        tmp_path,
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        slot_bundle_paths={"source": source_bundle},
        materializer=materializer,
    )

    stage_result = report.result.evidence_comparison_stage_result
    assert stage_result is not None
    assert stage_result.run_status == "success"
    assert stage_result.declared_output_path is not None
    validate_final_findings(load_json(stage_result.declared_output_path))
    assert stage_result.stage_executor_id == (
        CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID
    )

    summary = _load_flow_summary(report)
    assert summary["status"] == "success"
    ec = summary["evidence_comparison"]
    assert ec["handoff_status"] == "ready"
    assert ec["stage_executed"] is True
    assert ec["run_status"] == "success"
    assert ec["declared_output_path"] == stage_result.declared_output_path.as_posix()
    assert Path(ec["declared_output_path"]).name == "final_findings.json"
    assert ec["participants"][0]["role_id"] == "source"
    assert provider.calls


def test_ready_cross_file_production_flow_preserves_participant_ordering(
    tmp_path: Path,
) -> None:
    dsur_path, ib_path = _write_cross_source_bundles(tmp_path)
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    provider = _RecordingProvider()
    stage_calls: list[EvidenceComparisonStageInput] = []
    original_run_stage = flow_module.run_evidence_comparison_stage

    def recording_run_stage(*, stage_input, stage_executor):
        stage_calls.append(stage_input)
        return original_run_stage(
            stage_input=stage_input,
            stage_executor=stage_executor,
        )

    materializer = lambda capability_id: (
        materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id=capability_id,
            assessment_provider=provider,
            assessment_second_pass_provider=provider,
            verification_provider=provider,
            consolidation_provider=provider,
        )
    )
    with patch.object(
        flow_module,
        "run_evidence_comparison_stage",
        side_effect=recording_run_stage,
    ):
        report = _run_flow_with_mock_slots(
            tmp_path,
            capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
            slot_bundle_paths={"source_a": dsur_path, "source_b": ib_path},
            materializer=materializer,
        )

    assert len(stage_calls) == 1
    assert [participant.role_id for participant in stage_calls[0].participants] == [
        "source_a",
        "source_b",
    ]
    assert isinstance(
        stage_calls[0].execution_dependencies,
        ClinicalTrialAggregateEvidenceComparisonExecutionDependencies,
    )
    assert report.result.evidence_comparison_stage_result is not None
    assert report.result.evidence_comparison_stage_result.run_status == "success"


def test_ready_partial_failure_flow_status_and_provenance(tmp_path: Path) -> None:
    capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="partial_failure_test",
        slots=(DocumentConsistencyQcParticipantSlot(slot_id="source"),),
    )
    bundle = tmp_path / "bundle.json"
    bundle.write_text("{}", encoding="utf-8")

    def fake_stage_executor(*, stage_input: EvidenceComparisonStageInput):
        output_dir = stage_input.context.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        findings_path = output_dir / FINDINGS_FILENAME
        findings_path.write_text("{}", encoding="utf-8")
        run_summary_path = output_dir / "run_summary.json"
        run_summary_path.write_text("{}", encoding="utf-8")
        return EvidenceComparisonStageResult(
            output_dir=output_dir,
            run_id=stage_input.context.run_id or "evidence_comparison_partial",
            stage_executor_id="recording.comparison",
            run_status="partial_failure",
            run_summary_path=run_summary_path,
            declared_output_path=findings_path,
        )

    binding = EvidenceComparisonConsumerBinding(
        capability_id=capability.capability_id,
        participant_requirements=(
            EvidenceComparisonParticipantRequirement(
                role_id="source",
                slot_id="source",
                semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            ),
        ),
        stage_executor=fake_stage_executor,
    )
    materializer = lambda capability_id: EvidenceComparisonExecutionDependencies()

    report = _run_flow_with_mock_slots(
        tmp_path,
        capability_config=capability,
        slot_bundle_paths={"source": bundle},
        materializer=materializer,
        consumer_bindings=EvidenceComparisonConsumerBindings(
            bindings={capability.capability_id: binding}
        ),
    )

    stage_result = report.result.evidence_comparison_stage_result
    assert stage_result is not None
    assert stage_result.run_status == "partial_failure"
    assert stage_result.declared_output_path is not None

    summary = _load_flow_summary(report)
    assert summary["status"] == "partial"
    assert summary["evidence_comparison"]["run_status"] == "partial_failure"
    assert summary["evidence_comparison"]["declared_output_path"] == (
        stage_result.declared_output_path.as_posix()
    )


def test_ready_failed_flow_status_and_provenance(tmp_path: Path) -> None:
    capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="failed_test",
        slots=(DocumentConsistencyQcParticipantSlot(slot_id="source"),),
    )
    bundle = tmp_path / "bundle.json"
    bundle.write_text("{}", encoding="utf-8")

    def fake_stage_executor(*, stage_input: EvidenceComparisonStageInput):
        output_dir = stage_input.context.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        run_summary_path = output_dir / "run_summary.json"
        run_summary_path.write_text("{}", encoding="utf-8")
        return EvidenceComparisonStageResult(
            output_dir=output_dir,
            run_id=stage_input.context.run_id or "evidence_comparison_failed",
            stage_executor_id="recording.comparison",
            run_status="failed",
            run_summary_path=run_summary_path,
            declared_output_path=None,
        )

    binding = EvidenceComparisonConsumerBinding(
        capability_id=capability.capability_id,
        participant_requirements=(
            EvidenceComparisonParticipantRequirement(
                role_id="source",
                slot_id="source",
                semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            ),
        ),
        stage_executor=fake_stage_executor,
    )
    materializer = lambda capability_id: EvidenceComparisonExecutionDependencies()

    report = _run_flow_with_mock_slots(
        tmp_path,
        capability_config=capability,
        slot_bundle_paths={"source": bundle},
        materializer=materializer,
        consumer_bindings=EvidenceComparisonConsumerBindings(
            bindings={capability.capability_id: binding}
        ),
    )

    assert report.result.evidence_comparison_stage_result is not None
    assert report.result.evidence_comparison_stage_result.declared_output_path is None
    summary = _load_flow_summary(report)
    assert summary["status"] == "failed"
    assert summary["evidence_comparison"]["run_status"] == "failed"
    assert "declared_output_path" not in summary["evidence_comparison"]


def test_ready_comparison_execution_exception_records_failed_flow_status(
    tmp_path: Path,
) -> None:
    materializer = lambda capability_id: EvidenceComparisonExecutionDependencies()

    with (
        patch.object(
            flow_module,
            "run_evidence_comparison_stage",
            side_effect=RuntimeError("comparison setup failed"),
        ),
        pytest.raises(RuntimeError, match="comparison setup failed"),
    ):
        _run_flow_with_mock_slots(
            tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            slot_bundle_paths={"source": tmp_path / "unused.json"},
            materializer=materializer,
        )

    flow_root = next((tmp_path / "runs" / "document_consistency_qc").iterdir())
    summary = load_json(flow_root / FLOW_RUN_SUMMARY_FILENAME)
    validate_flow_run_summary(summary)
    assert summary["status"] == "failed"
    assert summary["slots"][0]["status"] == "success"

    evidence_comparison = summary["evidence_comparison"]
    assert evidence_comparison["handoff_status"] == "ready"
    assert evidence_comparison["stage_executed"] is True
    assert evidence_comparison["run_status"] == "failed"
    assert evidence_comparison["run_id"] == "evidence_comparison_internal_dsur"
    assert "declared_output_path" not in evidence_comparison

    failure_summary = load_json(Path(evidence_comparison["run_summary_path"]))
    assert failure_summary["failure_reason"] == "execution_exception"
    assert failure_summary["failure_message"] == "comparison setup failed"
    assert failure_summary["run_status"] == "failed"


def test_flow_preserves_rich_stage_owned_comparison_failure_summary(
    tmp_path: Path,
) -> None:
    materializer = lambda capability_id: EvidenceComparisonExecutionDependencies()

    def fail_after_rich_summary(*, stage_input, stage_executor):
        del stage_executor
        output_dir = stage_input.context.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / FINDINGS_FILENAME).write_text("{}", encoding="utf-8")
        (output_dir / "run_summary.json").write_text(
            json.dumps(
                {
                    "run_id": stage_input.context.run_id,
                    "stage": "evidence_comparison",
                    "status": "failed",
                    "run_status": "failed",
                    "failure_reason": "execution_exception",
                    "failure_message": "deterministic finalization failure",
                    "outputs": {
                        "job_final_findings": FINDINGS_FILENAME,
                        "final_findings": None,
                    },
                    "stats": {"job_final_finding_count": 2},
                    "consolidation": [
                        {
                            "comparison_mode_id": "focus_comparison",
                            "status": "success",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        raise RuntimeError("deterministic finalization failure")

    with (
        patch.object(
            flow_module,
            "run_evidence_comparison_stage",
            side_effect=fail_after_rich_summary,
        ),
        pytest.raises(RuntimeError, match="deterministic finalization failure"),
    ):
        _run_flow_with_mock_slots(
            tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            slot_bundle_paths={"source": tmp_path / "unused.json"},
            materializer=materializer,
        )

    flow_root = next((tmp_path / "runs" / "document_consistency_qc").iterdir())
    flow_summary = load_json(flow_root / FLOW_RUN_SUMMARY_FILENAME)
    comparison = flow_summary["evidence_comparison"]
    assert "declared_output_path" not in comparison
    failure_summary = load_json(Path(comparison["run_summary_path"]))
    assert failure_summary["stats"]["job_final_finding_count"] == 2
    assert failure_summary["outputs"]["job_final_findings"] == FINDINGS_FILENAME
    assert failure_summary["outputs"]["final_findings"] is None
    assert failure_summary["consolidation"][0]["status"] == "success"
    assert (
        probe_result_readiness(
            project_root=tmp_path,
            flow_run_id=flow_summary["flow_run_id"],
            summary=flow_summary,
        )
        is False
    )


def test_unbound_handoff_skips_stage_and_provider_materialization(
    tmp_path: Path,
) -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    materializer_calls: list[str] = []

    def recording_materializer(capability_id: str):
        materializer_calls.append(capability_id)
        return materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id=capability_id,
            assessment_provider=_RecordingProvider(),
            assessment_second_pass_provider=_RecordingProvider(),
            verification_provider=_RecordingProvider(),
            consolidation_provider=_RecordingProvider(),
        )

    with patch.object(
        flow_module,
        "run_evidence_comparison_stage",
    ) as run_stage:
        report = _run_flow_with_mock_slots(
            tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            slot_bundle_paths={"source": tmp_path / "unused.json"},
            materializer=recording_materializer,
            consumer_bindings=EvidenceComparisonConsumerBindings(bindings={}),
        )

    run_stage.assert_not_called()
    assert materializer_calls == []
    assert (
        report.result.evidence_comparison_handoff_resolution.status
        is EvidenceComparisonHandoffResolutionStatus.UNBOUND
    )
    assert report.result.evidence_comparison_stage_result is None
    summary = _load_flow_summary(report)
    assert summary["evidence_comparison"]["handoff_status"] == "unbound"
    assert summary["evidence_comparison"]["stage_executed"] is False
    assert "stage_executor_id" not in summary["evidence_comparison"]


def test_ready_without_materializer_raises_setup_error(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Evidence Comparison handoff is READY but no execution dependencies",
    ):
        _run_flow_with_mock_slots(
            tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            slot_bundle_paths={"source": tmp_path / "unused.json"},
            materializer=None,
        )


def test_dependency_materialization_failure_is_not_unbound(
    tmp_path: Path,
) -> None:
    def failing_materializer(capability_id: str):
        raise ValueError("missing installed LLM dependency binding")

    with pytest.raises(ValueError, match="missing installed LLM dependency binding"):
        _run_flow_with_mock_slots(
            tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            slot_bundle_paths={"source": tmp_path / "unused.json"},
            materializer=failing_materializer,
        )


def test_flow_invokes_comparison_stage_exactly_once(
    tmp_path: Path,
) -> None:
    source_bundle = _write_internal_dsur_source_bundle(
        tmp_path,
        label="flow_stage_once",
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    provider = _RecordingProvider()
    materializer = lambda capability_id: (
        materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id=capability_id,
            assessment_provider=provider,
            assessment_second_pass_provider=provider,
            verification_provider=provider,
            consolidation_provider=provider,
        )
    )

    with patch.object(
        flow_module,
        "run_evidence_comparison_stage",
        wraps=flow_module.run_evidence_comparison_stage,
    ) as run_stage:
        _run_flow_with_mock_slots(
            tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            slot_bundle_paths={"source": source_bundle},
            materializer=materializer,
        )

    run_stage.assert_called_once()


def test_flow_writes_canonical_single_participant_evidence_comparison_output_layout(
    tmp_path: Path,
) -> None:
    source_bundle = _write_internal_dsur_source_bundle(
        tmp_path,
        label="flow_single_layout",
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    provider = _RecordingProvider()
    materializer = lambda capability_id: (
        materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id=capability_id,
            assessment_provider=provider,
            assessment_second_pass_provider=provider,
            verification_provider=provider,
            consolidation_provider=provider,
        )
    )
    report = _run_flow_with_mock_slots(
        tmp_path,
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        slot_bundle_paths={"source": source_bundle},
        materializer=materializer,
    )
    stage_result = report.result.evidence_comparison_stage_result
    assert stage_result is not None
    assert stage_result.run_id == "evidence_comparison_internal_dsur"
    expected_output_dir = (
        report.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "evidence_comparison"
    )
    assert stage_result.output_dir == expected_output_dir
    assert stage_result.output_dir.name == "evidence_comparison"
    assert (stage_result.output_dir / FINDINGS_FILENAME).is_file()
    assert (stage_result.output_dir / "run_summary.json").is_file()
    assert (stage_result.output_dir / "aggregate_comparison_evidence.json").is_file()
    assert (
        stage_result.output_dir / "comparison_finding_assessment_jobs.json"
    ).is_file()
    legacy_output_dir = (
        report.flow_run_summary_path.parent
        / "evidence_comparison"
        / "evidence_comparison_internal_dsur"
    )
    assert not legacy_output_dir.exists()
    assert report.flow_run_summary_path.is_file()

    summary = _load_flow_summary(report)
    ec = summary["evidence_comparison"]
    assert ec["run_id"] == "evidence_comparison_internal_dsur"
    assert ec["output_dir"] == stage_result.output_dir.as_posix()
    assert ec["declared_output_path"] == stage_result.declared_output_path.as_posix()


def test_flow_writes_canonical_cross_participant_evidence_comparison_output_layout(
    tmp_path: Path,
) -> None:
    dsur_path, ib_path = _write_cross_source_bundles(tmp_path)
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    provider = _RecordingProvider()
    materializer = lambda capability_id: (
        materialize_installed_evidence_comparison_execution_dependencies(
            composition=composition,
            capability_id=capability_id,
            assessment_provider=provider,
            assessment_second_pass_provider=provider,
            verification_provider=provider,
            consolidation_provider=provider,
        )
    )
    report = _run_flow_with_mock_slots(
        tmp_path,
        capability_config=DSUR_UPDATED_IB_CONSISTENCY_QC,
        slot_bundle_paths={"source_a": dsur_path, "source_b": ib_path},
        materializer=materializer,
    )
    stage_result = report.result.evidence_comparison_stage_result
    assert stage_result is not None
    assert stage_result.run_status == "success"
    assert stage_result.run_id == "evidence_comparison_dsur_updated_ib"
    expected_output_dir = (
        report.flow_run_summary_path.parent / "evidence_comparison" / "dsur_updated_ib"
    )
    assert stage_result.output_dir == expected_output_dir
    assert stage_result.output_dir.name == "dsur_updated_ib"
    assert (stage_result.output_dir / FINDINGS_FILENAME).is_file()
    assert (stage_result.output_dir / "run_summary.json").is_file()
    legacy_output_dir = (
        report.flow_run_summary_path.parent
        / "evidence_comparison"
        / "evidence_comparison_dsur_updated_ib"
    )
    assert not legacy_output_dir.exists()

    summary = _load_flow_summary(report)
    ec = summary["evidence_comparison"]
    assert ec["run_id"] == "evidence_comparison_dsur_updated_ib"
    assert ec["output_dir"] == stage_result.output_dir.as_posix()
    assert ec["declared_output_path"] == stage_result.declared_output_path.as_posix()
