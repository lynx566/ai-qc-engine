"""Flow integration tests for Filter → Projection → Route execution."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.flow as flow_module
from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from application.document_consistency_qc import (
    DocumentConsistencyQcApplicationComposition,
)
from artifacts.filter_output_projection_bundle import (
    validate_filter_output_projection_bundle,
)
from capability import INTERNAL_IB_CONSISTENCY_QC
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
    DocumentConsistencyQcParticipantRunInput,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from operations.prepare_analysis import PrepareAnalysisRequestOptions
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from plugins.clinical_trial_doc.prepare_analysis.config import (
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    ClinicalPreparePrivacyConfig,
)
from runtime.io import load_json
from tests.document_consistency_qc_flow_helpers import (
    admitted_source_bindings,
    clinical_flow_invocation_kwargs,
    empty_evidence_source_preparation_flow_dependencies,
    flow_projection_runtime_dependencies,
    installed_doc_meta_flow_dependencies,
    installed_filter_flow_dependencies,
    installed_projection_route_flow_dependencies,
    synthetic_operation_bindings_for_capability,
)

SECOND_SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)

FLOW_PATH = (
    BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "flow.py"
)


def _run_flow(
    *,
    capability_config: DocumentConsistencyQcCapabilityConfig,
    uploads: dict[str, Path | str],
    project_root: Path,
    composition_overrides: dict[str, object] | None = None,
    projection_runtime_dependencies: FilterOutputProjectionRuntimeDependencies | None = None,
):
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    kwargs = clinical_flow_invocation_kwargs()
    if projection_runtime_dependencies is not None:
        kwargs["projection_runtime_dependencies"] = projection_runtime_dependencies
    if composition_overrides:
        composition = DocumentConsistencyQcApplicationComposition(
            capabilities=composition.capabilities,
            extract_bindings=composition.extract_bindings,
            prepare_analysis_bindings=composition.prepare_analysis_bindings,
            filter_job_bindings=composition_overrides.get(
                "filter_job_bindings",
                composition.filter_job_bindings,
            ),
            candidate_scope_manual_default_filter_job_bindings=(
                composition.candidate_scope_manual_default_filter_job_bindings
            ),
            expected_document_type_bindings=composition.expected_document_type_bindings,
            prepare_analysis_config_registry=composition.prepare_analysis_config_registry,
            load_prepare_request_options=composition.load_prepare_request_options,
            doc_meta_profile=composition.doc_meta_profile,
            doc_meta_summary_builder=composition.doc_meta_summary_builder,
            filter_configs=composition.filter_configs,
            filter_job_variants=composition.filter_job_variants,
            filter_output_projection_jobs=composition.filter_output_projection_jobs,
            filter_output_projection_facade_builder=(
                composition.filter_output_projection_facade_builder
            ),
            projected_source_route_executor=composition.projected_source_route_executor,
            route_semantic_module_sequence=composition_overrides.get(
                "route_semantic_module_sequence",
                composition.route_semantic_module_sequence,
            ),
            evidence_source_preparation_consumer_bindings=composition_overrides.get(
                "evidence_source_preparation_consumer_bindings",
                composition.evidence_source_preparation_consumer_bindings,
            ),
            evidence_comparison_consumer_bindings=(
                composition.evidence_comparison_consumer_bindings
            ),
            llm_dependency_bindings=composition.llm_dependency_bindings,
        )
    return flow_module.run_document_consistency_qc_flow(
        project_root=project_root,
        capability_config=capability_config,
        uploads=admitted_source_bindings(uploads),
        participant_inputs={
            slot_id: DocumentConsistencyQcParticipantRunInput(
                prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                    ClinicalPreparePrivacyConfig.identity()
                ),
            )
            for slot_id in uploads
        },
        prepare_analysis_config_registry=registry,
        **kwargs,
    )


def test_flow_runs_projection_and_route_for_installed_filter_jobs(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=INTERNAL_IB_CONSISTENCY_QC,
        uploads=admitted_source_bindings({"source": SECOND_SAMPLE_DOCX}),
        project_root=tmp_path,
    )
    slot = report.result.slots[0]
    expected_jobs = INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS[
        (INTERNAL_IB_CONSISTENCY_QC.capability_id, "source")
    ]
    assert tuple(job.filter_job_id for job in slot.projection_results) == expected_jobs
    assert len(slot.route_semantic_module_results) == 1
    module_result = slot.route_semantic_module_results[0]
    assert module_result.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert module_result.route_invoked is True
    assert module_result.selected_projected_source_count >= 1

    route_manifest = load_json(
        module_result.stage_result.routing_manifest_path  # type: ignore[union-attr]
    )
    projection_refs = route_manifest["source_refs"]["projection_input_refs"]
    assert projection_refs
    upstream_bundle_ids = {
        load_json(job.stage_result.projection_bundle_path)[
            "filter_output_projection_bundle_id"
        ]
        for job in slot.projection_results
    }
    assert {
        ref["filter_output_projection_bundle_id"] for ref in projection_refs
    }.issubset(upstream_bundle_ids)

    summary = load_json(report.flow_run_summary_path)
    assert summary["slots"][0]["projection_jobs"]
    assert summary["slots"][0]["route_semantic_modules"][0]["route_invoked"] is True


def test_direct_only_capability_runs_without_live_llm(tmp_path: Path) -> None:
    direct_only_capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="test_direct_only",
        slots=(DocumentConsistencyQcParticipantSlot(slot_id="source"),),
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    bindings = synthetic_operation_bindings_for_capability(
        direct_only_capability,
        prepare_analysis_config_id=next(
            iter(composition.prepare_analysis_bindings.values())
        ),
        filter_job_ids=("ib_clinical_safety",),
    )
    invocation = {
        "source_language": "zh",
        **installed_doc_meta_flow_dependencies(),
        **installed_filter_flow_dependencies(),
        **installed_projection_route_flow_dependencies(),
        **empty_evidence_source_preparation_flow_dependencies(),
        "projection_runtime_dependencies": FilterOutputProjectionRuntimeDependencies(),
    }
    invocation.update(bindings)
    report = flow_module.run_document_consistency_qc_flow(
        project_root=tmp_path,
        capability_config=direct_only_capability,
        uploads=admitted_source_bindings({"source": SECOND_SAMPLE_DOCX}),
        participant_inputs={
            "source": DocumentConsistencyQcParticipantRunInput(
                prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                    ClinicalPreparePrivacyConfig.identity()
                ),
            )
        },
        prepare_analysis_config_registry=composition.prepare_analysis_config_registry,
        **invocation,
    )
    slot = report.result.slots[0]
    assert len(slot.projection_results) == 1
    assert slot.route_semantic_module_results[0].route_invoked is True


def test_flow_records_zero_selected_route_without_invocation(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    empty_route_capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="test_empty_route",
        slots=(DocumentConsistencyQcParticipantSlot(slot_id="source"),),
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    bindings = synthetic_operation_bindings_for_capability(
        empty_route_capability,
        prepare_analysis_config_id=next(
            iter(composition.prepare_analysis_bindings.values())
        ),
        filter_job_ids=("ib_clinical_safety",),
    )
    invocation = {
        "source_language": "zh",
        **installed_doc_meta_flow_dependencies(),
        **installed_filter_flow_dependencies(),
        **installed_projection_route_flow_dependencies(),
        **empty_evidence_source_preparation_flow_dependencies(),
        "projection_runtime_dependencies": FilterOutputProjectionRuntimeDependencies(),
        "route_semantic_module_sequence": ("efficacy",),
    }
    invocation.update(bindings)
    report = flow_module.run_document_consistency_qc_flow(
        project_root=tmp_path,
        capability_config=empty_route_capability,
        uploads=admitted_source_bindings({"source": SECOND_SAMPLE_DOCX}),
        participant_inputs={
            "source": DocumentConsistencyQcParticipantRunInput(
                prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                    ClinicalPreparePrivacyConfig.identity()
                ),
            )
        },
        prepare_analysis_config_registry=composition.prepare_analysis_config_registry,
        **invocation,
    )
    module_result = report.result.slots[0].route_semantic_module_results[0]
    assert module_result.selected_projected_source_count == 0
    assert module_result.route_invoked is False
    assert module_result.stage_result is None


def test_flow_execution_dispatch_has_no_domain_branching_tokens() -> None:
    source = FLOW_PATH.read_text(encoding="utf-8")
    slot_fn = source.split("def _run_slot", 1)[1].split("def run_document_consistency_qc_flow", 1)[0]
    forbidden = (
        "overview_semantic_decomposition",
        "assembled_semantic",
        "raw_source",
        "if \"overview\"",
        "\"clinical_safety\"",
        "'clinical_safety'",
    )
    for token in forbidden:
        assert token not in slot_fn, f"flow slot dispatch must not reference {token!r}"


def test_projection_artifact_preserves_semantic_outcomes(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    report = _run_flow(
        capability_config=INTERNAL_IB_CONSISTENCY_QC,
        uploads={"source": SECOND_SAMPLE_DOCX},
        project_root=tmp_path,
        projection_runtime_dependencies=flow_projection_runtime_dependencies(),
    )
    overview_job = next(
        job
        for job in report.result.slots[0].projection_results
        if job.filter_job_id.endswith("_overview")
    )
    bundle = load_json(overview_job.stage_result.projection_bundle_path)
    validate_filter_output_projection_bundle(bundle)
    assert bundle["semantic_outcomes"] is not None
