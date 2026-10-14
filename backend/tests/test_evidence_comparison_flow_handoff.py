"""Flow and Application wiring tests for capability-level Comparison fan-in."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.flow as flow_module
from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
    DocumentConsistencyQcParticipantRunInput,
)
from operations.evidence_comparison.consumer_bindings import (
    EvidenceComparisonConsumerBinding,
    EvidenceComparisonConsumerBindings,
)
from operations.evidence_comparison.handoff import (
    EvidenceComparisonHandoffResolutionStatus,
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
from plugins.clinical_trial_doc.prepare_analysis.config import (
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    ClinicalPreparePrivacyConfig,
)
from runtime.document_source_binding import DocumentIntakeSourceBinding


def _slot_result(tmp_path: Path, slot_id: str):
    esp_output_dir = tmp_path / slot_id / "esp"
    esp_output_dir.mkdir(parents=True)
    declared_output_path = esp_output_dir / "declared.json"
    declared_output_path.write_text("not loaded by Flow", encoding="utf-8")
    run_summary_path = esp_output_dir / "run_summary.json"
    run_summary_path.write_text("{}", encoding="utf-8")
    esp_result = EvidenceSourcePreparationStageResult(
        output_dir=esp_output_dir,
        run_id=f"esp_{slot_id}",
        doc_id=f"doc_{slot_id}",
        semantic_module_id="module_alpha",
        stage_executor_id="recording.esp",
        declared_output_path=declared_output_path,
        run_summary_path=run_summary_path,
    )
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
                semantic_module_id="module_alpha",
                selected_projected_source_count=1,
                route_invoked=True,
                evidence_source_preparation_invoked=True,
                evidence_source_preparation_stage_result=esp_result,
            ),
        ),
    )


def test_production_application_installs_evidence_comparison_bindings() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()

    assert isinstance(
        composition.evidence_comparison_consumer_bindings,
        EvidenceComparisonConsumerBindings,
    )
    assert composition.evidence_comparison_consumer_bindings.bindings
    assert (
        composition.evidence_comparison_consumer_bindings.resolve_consumer_binding(
            "dsur_updated_ib"
        )
        is not None
    )
    assert (
        composition.evidence_comparison_consumer_bindings.resolve_consumer_binding(
            "unknown_capability"
        )
        is None
    )


def test_flow_collects_semantic_module_identity_from_esp_stage_result(
    tmp_path: Path,
) -> None:
    slot_result = _slot_result(tmp_path, "source")
    mirrored_route_result = slot_result.route_semantic_module_results[0]
    mismatched_slot_result = flow_module.DocumentConsistencyQcSlotResult(
        slot_id=slot_result.slot_id,
        admitted_source=slot_result.admitted_source,
        extract_report=slot_result.extract_report,
        prepare_analysis_report=slot_result.prepare_analysis_report,
        doc_meta_report=slot_result.doc_meta_report,
        route_semantic_module_results=(
            flow_module.RouteSemanticModuleFlowResult(
                semantic_module_id="outer_mirror_must_not_win",
                selected_projected_source_count=(
                    mirrored_route_result.selected_projected_source_count
                ),
                route_invoked=True,
                evidence_source_preparation_invoked=True,
                evidence_source_preparation_stage_result=(
                    mirrored_route_result.evidence_source_preparation_stage_result
                ),
            ),
        ),
    )

    produced = flow_module._collect_produced_evidence_source_preparation_outputs(
        (mismatched_slot_result,)
    )

    assert produced[0].semantic_module_id == "module_alpha"


def test_flow_fan_in_runs_comparison_once_after_all_slots_complete(
    tmp_path: Path,
) -> None:
    capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="comparison_fan_in_test",
        slots=(
            DocumentConsistencyQcParticipantSlot(slot_id="source_a"),
            DocumentConsistencyQcParticipantSlot(slot_id="source_b"),
        ),
    )
    completed_slots: list[str] = []
    stage_calls: list[EvidenceComparisonStageInput] = []

    def fake_run_slot(*, slot, slot_provenance=None, **kwargs):
        if slot_provenance is not None:
            slot_provenance.status = "success"
            slot_id = slot.slot_id
            slot_provenance.intake_run_id = f"intake_{slot_id}"
            slot_provenance.file_hash = "sha256:" + ("0" * 64)
            slot_provenance.doc_id = f"doc_{slot_id}"
            slot_provenance.extract_run_id = f"extract_{slot_id}"
            slot_provenance.prepare_analysis_run_id = f"prepare_{slot_id}"
            slot_provenance.analysis_bundle_path = (
                f"/tmp/{slot_id}/analysis_bundle.json"
            )
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
        completed_slots.append(slot.slot_id)
        return _slot_result(tmp_path, slot.slot_id)

    def recording_comparison_stage_executor(
        *,
        stage_input: EvidenceComparisonStageInput,
    ) -> EvidenceComparisonStageResult:
        assert completed_slots == ["source_a", "source_b"]
        stage_calls.append(stage_input)
        output_dir = stage_input.context.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        run_summary_path = output_dir / "run_summary.json"
        run_summary_path.write_text("{}", encoding="utf-8")
        return EvidenceComparisonStageResult(
            output_dir=output_dir,
            run_id=stage_input.context.run_id or "evidence_comparison",
            stage_executor_id="recording.comparison",
            run_status="success",
            run_summary_path=run_summary_path,
        )

    binding = EvidenceComparisonConsumerBinding(
        capability_id=capability.capability_id,
        participant_requirements=(
            EvidenceComparisonParticipantRequirement(
                role_id="second",
                slot_id="source_b",
                semantic_module_id="module_alpha",
            ),
            EvidenceComparisonParticipantRequirement(
                role_id="first",
                slot_id="source_a",
                semantic_module_id="module_alpha",
            ),
        ),
        stage_executor=recording_comparison_stage_executor,
    )
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    prepare_config_id = next(iter(composition.prepare_analysis_bindings.values()))
    participant_input = DocumentConsistencyQcParticipantRunInput(
        prepare_analysis_request_options=PrepareAnalysisRequestOptions(
            ClinicalPreparePrivacyConfig.identity()
        )
    )
    binding_keys = {
        (capability.capability_id, slot.slot_id): prepare_config_id
        for slot in capability.slots
    }

    materializer_calls: list[str] = []

    def recording_materializer(capability_id: str):
        materializer_calls.append(capability_id)
        return EvidenceComparisonExecutionDependencies()

    with (
        patch.object(flow_module, "_run_slot", side_effect=fake_run_slot),
        patch.object(
            flow_module,
            "persist_flow_run_summary",
            return_value=tmp_path / "flow_run_summary.json",
        ),
    ):
        source_a = tmp_path / "a.docx"
        source_b = tmp_path / "b.docx"
        source_a.write_bytes(b"a")
        source_b.write_bytes(b"b")
        report = flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=capability,
            uploads={
                "source_a": DocumentIntakeSourceBinding(
                    file_hash="sha256:" + ("0" * 64),
                    original_file_name="a.docx",
                    source_path=source_a,
                ),
                "source_b": DocumentIntakeSourceBinding(
                    file_hash="sha256:" + ("1" * 64),
                    original_file_name="b.docx",
                    source_path=source_b,
                ),
            },
            participant_inputs={
                "source_a": participant_input,
                "source_b": participant_input,
            },
            source_language="zh",
            extract_bindings={key: "docx" for key in binding_keys},
            prepare_analysis_bindings=binding_keys,
            filter_job_bindings={key: () for key in binding_keys},
            prepare_analysis_config_registry=registry,
            doc_meta_profile=composition.doc_meta_profile,
            doc_meta_summary_builder=composition.doc_meta_summary_builder,
            filter_job_variants={},
            filter_output_projection_jobs={},
            filter_output_projection_facade_builder=lambda **kwargs: None,
            projected_source_route_executor=lambda **kwargs: None,
            route_semantic_module_sequence=(),
            evidence_source_preparation_consumer_bindings=(
                EvidenceSourcePreparationConsumerBindings(bindings={})
            ),
            evidence_source_preparation_execution_dependencies=(
                EvidenceSourcePreparationExecutionDependencies()
            ),
            evidence_comparison_consumer_bindings=(
                EvidenceComparisonConsumerBindings(
                    bindings={capability.capability_id: binding}
                )
            ),
            materialize_evidence_comparison_execution_dependencies=recording_materializer,
        )

    assert len(stage_calls) == 1
    assert materializer_calls == [capability.capability_id]
    assert isinstance(
        stage_calls[0].execution_dependencies,
        EvidenceComparisonExecutionDependencies,
    )
    assert [participant.role_id for participant in stage_calls[0].participants] == [
        "second",
        "first",
    ]
    assert (
        report.result.evidence_comparison_handoff_resolution.status
        is EvidenceComparisonHandoffResolutionStatus.READY
    )
    assert report.result.evidence_comparison_stage_result is not None
