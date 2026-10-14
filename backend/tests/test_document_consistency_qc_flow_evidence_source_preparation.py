"""Flow integration tests for Evidence Source Preparation wiring after Route."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.flow as flow_module
from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc import execution as execution_module
from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_consumer_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS,
)
from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from application.document_consistency_qc import DocumentConsistencyQcExecutionRequest
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    validate_flow_run_summary,
)
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantRunInput,
    DocumentConsistencyQcParticipantSlot,
)
from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBinding,
    EvidenceSourcePreparationConsumerBindings,
)
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationStageInput,
    EvidenceSourcePreparationStageResult,
    RouteStageReference,
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
    empty_evidence_source_preparation_flow_dependencies,
    flow_projection_runtime_dependencies,
    installed_doc_meta_flow_dependencies,
    installed_filter_flow_dependencies,
    installed_projection_route_flow_dependencies,
    single_filter_ib_safety_flow_capability,
    single_filter_ib_safety_flow_invocation,
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
FLOW_PATH = BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "flow.py"


def _fake_esp_stage_result(
    *,
    stage_input: EvidenceSourcePreparationStageInput,
    stage_executor_id: str = "mock.esp.stage_executor",
) -> EvidenceSourcePreparationStageResult:
    output_dir = stage_input.context.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    declared_output_path = output_dir / "declared_output.json"
    declared_output_path.write_text("{}", encoding="utf-8")
    run_summary_path = output_dir / "run_summary.json"
    run_summary_path.write_text("{}", encoding="utf-8")
    return EvidenceSourcePreparationStageResult(
        output_dir=output_dir,
        run_id=stage_input.context.run_id or "esp_mock",
        doc_id=stage_input.route_stage.doc_id,
        semantic_module_id=stage_input.route_stage.semantic_module_id,
        stage_executor_id=stage_executor_id,
        declared_output_path=declared_output_path,
        run_summary_path=run_summary_path,
    )


def _run_esp_flow(
    *,
    uploads: dict[str, Path | str],
    project_root: Path,
    invocation_overrides: dict[str, object] | None = None,
    stage_side_effect=None,
):
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    kwargs = single_filter_ib_safety_flow_invocation(
        prepare_analysis_config_id=next(
            iter(composition.prepare_analysis_bindings.values())
        ),
    )
    if invocation_overrides:
        kwargs.update(invocation_overrides)

    if stage_side_effect is None:

        def stage_side_effect(*, stage_input, stage_executor):
            _ = stage_executor
            return _fake_esp_stage_result(stage_input=stage_input)

    with patch.object(
        flow_module,
        "run_evidence_source_preparation_stage",
        side_effect=stage_side_effect,
    ) as mock_stage:
        report = flow_module.run_document_consistency_qc_flow(
            project_root=project_root,
            capability_config=single_filter_ib_safety_flow_capability(),
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
    return report, mock_stage


def test_neutral_composition_carries_evidence_source_preparation_consumer_bindings() -> (
    None
):
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    assert isinstance(
        composition.evidence_source_preparation_consumer_bindings,
        EvidenceSourcePreparationConsumerBindings,
    )


def test_installed_clinical_trial_binding_targets_clinical_safety_only() -> None:
    bindings = (
        INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS
    )
    assert set(bindings.bindings) == {CLINICAL_SAFETY_SEMANTIC_MODULE_ID}
    installed_binding = bindings.resolve_consumer_binding(
        CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    )
    assert installed_binding is not None
    assert installed_binding.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert installed_binding.required_route_output_kind == "aggregate"
    assert installed_binding.evidence_form_id == "aggregate_evidence"
    assert (
        installed_binding.stage_executor
        is INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
    )
    assert bindings.resolve_consumer_binding("efficacy") is None


def test_flow_does_not_hard_code_clinical_safety() -> None:
    slot_fn = FLOW_PATH.read_text(encoding="utf-8").split("def _run_slot", 1)[1]
    slot_fn = slot_fn.split("def run_document_consistency_qc_flow", 1)[0]
    assert '"clinical_safety"' not in slot_fn
    assert "'clinical_safety'" not in slot_fn
    assert '"aggregate"' not in slot_fn
    assert "'aggregate'" not in slot_fn
    assert '"aggregate_evidence"' not in slot_fn
    assert "'aggregate_evidence'" not in slot_fn
    assert "resolve_stage_executor" not in slot_fn
    assert not hasattr(
        EvidenceSourcePreparationConsumerBindings, "resolve_stage_executor"
    )


def test_esp_handoff_uses_route_stage_result_semantic_module_id(
    tmp_path: Path,
) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    captured: list[EvidenceSourcePreparationStageInput] = []
    resolve_calls: list[str] = []
    original_resolve = (
        EvidenceSourcePreparationConsumerBindings.resolve_consumer_binding
    )

    def tracking_resolve(self, semantic_module_id: str):
        resolve_calls.append(semantic_module_id)
        return original_resolve(self, semantic_module_id)

    def capture_stage(*, stage_input, stage_executor):
        _ = stage_executor
        captured.append(stage_input)
        return _fake_esp_stage_result(stage_input=stage_input)

    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    kwargs = single_filter_ib_safety_flow_invocation(
        prepare_analysis_config_id=next(
            iter(
                build_clinical_trial_doc_consistency_qc_application_composition().prepare_analysis_bindings.values()
            )
        ),
    )

    with (
        patch.object(
            EvidenceSourcePreparationConsumerBindings,
            "resolve_consumer_binding",
            tracking_resolve,
        ),
        patch.object(
            flow_module,
            "run_evidence_source_preparation_stage",
            side_effect=capture_stage,
        ),
    ):
        report = flow_module.run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=single_filter_ib_safety_flow_capability(),
            uploads=admitted_source_bindings({"source": SECOND_SAMPLE_DOCX}),
            participant_inputs={
                "source": DocumentConsistencyQcParticipantRunInput(
                    prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                        ClinicalPreparePrivacyConfig.identity()
                    ),
                )
            },
            prepare_analysis_config_registry=registry,
            **kwargs,
        )

    module_result = report.result.slots[0].route_semantic_module_results[0]
    assert module_result.route_invoked is True
    assert module_result.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert len(captured) == 1
    route_stage_id = captured[0].route_stage.semantic_module_id
    assert route_stage_id == module_result.semantic_module_id
    assert resolve_calls == [route_stage_id]


def test_routed_module_without_binding_skips_esp_without_error(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    empty_bindings = EvidenceSourcePreparationConsumerBindings(bindings={})
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    kwargs = single_filter_ib_safety_flow_invocation(
        prepare_analysis_config_id=next(
            iter(
                build_clinical_trial_doc_consistency_qc_application_composition().prepare_analysis_bindings.values()
            )
        ),
    )
    kwargs["evidence_source_preparation_consumer_bindings"] = empty_bindings
    report = flow_module.run_document_consistency_qc_flow(
        project_root=tmp_path,
        capability_config=single_filter_ib_safety_flow_capability(),
        uploads=admitted_source_bindings({"source": SECOND_SAMPLE_DOCX}),
        participant_inputs={
            "source": DocumentConsistencyQcParticipantRunInput(
                prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                    ClinicalPreparePrivacyConfig.identity()
                ),
            )
        },
        prepare_analysis_config_registry=registry,
        **kwargs,
    )
    module_result = report.result.slots[0].route_semantic_module_results[0]
    assert module_result.route_invoked is True
    assert module_result.evidence_source_preparation_invoked is False
    assert module_result.evidence_source_preparation_stage_result is None


def test_installed_binding_invokes_stage_runtime_exactly_once(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    report, mock_stage = _run_esp_flow(
        uploads=admitted_source_bindings({"source": SECOND_SAMPLE_DOCX}),
        project_root=tmp_path,
    )
    assert mock_stage.call_count == 1
    module_result = report.result.slots[0].route_semantic_module_results[0]
    assert module_result.evidence_source_preparation_invoked is True


def test_flow_passes_neutral_stage_input_not_aggregate_types(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    captured: list[EvidenceSourcePreparationStageInput] = []

    def capture_stage(*, stage_input, stage_executor):
        captured.append(stage_input)
        return _fake_esp_stage_result(stage_input=stage_input)

    _report, _mock_stage = _run_esp_flow(
        uploads=admitted_source_bindings({"source": SECOND_SAMPLE_DOCX}),
        project_root=tmp_path,
        stage_side_effect=capture_stage,
    )

    assert len(captured) == 1
    stage_input = captured[0]
    assert isinstance(stage_input, EvidenceSourcePreparationStageInput)
    assert isinstance(stage_input.route_stage, RouteStageReference)
    assert stage_input.evidence_form_id
    assert stage_input.selected_route_output.unit_count > 0
    assert stage_input.selected_route_output.routed_bundle_path.is_file()
    assert stage_input.projection_input_refs
    assert stage_input.filter_job_coverage_refs
    assert stage_input.upstream.analysis_bundle_path.is_file()


def test_flow_skips_esp_when_required_route_output_not_produced(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    mismatched_binding = EvidenceSourcePreparationConsumerBinding(
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        required_route_output_kind="table",
        evidence_form_id="form_test",
        stage_executor=INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
    )
    mismatched_bindings = EvidenceSourcePreparationConsumerBindings(
        bindings={CLINICAL_SAFETY_SEMANTIC_MODULE_ID: mismatched_binding},
    )
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    report, mock_stage = _run_esp_flow(
        uploads={"source": SECOND_SAMPLE_DOCX},
        project_root=tmp_path,
        invocation_overrides={
            "evidence_source_preparation_consumer_bindings": mismatched_bindings,
        },
    )
    module_result = report.result.slots[0].route_semantic_module_results[0]
    assert module_result.route_invoked is True
    assert module_result.evidence_source_preparation_invoked is False
    assert mock_stage.call_count == 0


def test_application_execution_materializes_esp_llm_not_flow(tmp_path: Path) -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    source = tmp_path / "source.docx"
    source.write_bytes(b"doc")
    request = DocumentConsistencyQcExecutionRequest(
        capability_id="internal_dsur",
        project_root=tmp_path,
        participant_inputs=admitted_source_bindings({"source": source}),
        participant_privacy_paths={"source": None},
        source_language="zh",
    )
    sentinel_provider = object()
    flow_source = FLOW_PATH.read_text(encoding="utf-8")

    with (
        patch.object(
            execution_module,
            "materialize_installed_projection_runtime_dependencies",
            return_value=flow_projection_runtime_dependencies(),
        ),
        patch.object(
            execution_module,
            "materialize_llm_provider",
            return_value=sentinel_provider,
        ),
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
        ) as mock_flow,
        patch.object(execution_module, "execute_prepared_document_consistency_qc_flow"),
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=object(),
        ),
    ):
        execution_module.execute_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
        )

    esp_deps = mock_flow.call_args.kwargs[
        "evidence_source_preparation_execution_dependencies"
    ]
    assert esp_deps.provider is sentinel_provider
    assert "materialize_llm_provider" not in flow_source
    assert "resolve_llm_execution_config" not in flow_source


def test_flow_imports_no_clinical_trial_doc_modules() -> None:
    tree = ast.parse(FLOW_PATH.read_text(encoding="utf-8"), filename=str(FLOW_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    for module in imported:
        assert module != "plugins.clinical_trial_doc"
        assert not module.startswith("plugins.clinical_trial_doc.")
        assert not module.startswith("application.clinical_trial_doc_consistency_qc.")


def test_flow_result_records_neutral_stage_result(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    report, _mock_stage = _run_esp_flow(
        uploads=admitted_source_bindings({"source": SECOND_SAMPLE_DOCX}),
        project_root=tmp_path,
    )
    module_result = report.result.slots[0].route_semantic_module_results[0]
    assert module_result.evidence_source_preparation_invoked is True
    stage_result = module_result.evidence_source_preparation_stage_result
    assert isinstance(stage_result, EvidenceSourcePreparationStageResult)
    assert stage_result.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert stage_result.declared_output_path.is_file()
    assert stage_result.run_summary_path.is_file()


def test_flow_run_summary_records_neutral_esp_provenance(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    report, _mock_stage = _run_esp_flow(
        uploads={"source": SECOND_SAMPLE_DOCX},
        project_root=tmp_path,
    )
    summary = load_json(report.flow_run_summary_path)
    validate_flow_run_summary(summary)
    assert summary["schema_version"] == FLOW_RUN_SUMMARY_SCHEMA_VERSION
    route_record = summary["slots"][0]["route_semantic_modules"][0]
    assert route_record["evidence_source_preparation_invoked"] is True
    assert route_record["evidence_source_preparation_run_id"]
    assert route_record["evidence_source_preparation_stage_executor_id"]
    assert route_record["evidence_source_preparation_declared_output_path"]
    assert route_record["evidence_source_preparation_run_summary_path"]
    forbidden_keys = (
        "prepare",
        "assess",
        "eligibility",
        "assemble",
        "scope_assessments",
        "heading_scope_eligibility",
    )
    for key in forbidden_keys:
        assert key not in route_record


def test_declared_output_path_points_to_persisted_stage_output(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    report, _mock_stage = _run_esp_flow(
        uploads={"source": SECOND_SAMPLE_DOCX},
        project_root=tmp_path,
    )
    module_result = report.result.slots[0].route_semantic_module_results[0]
    stage_result = module_result.evidence_source_preparation_stage_result
    assert stage_result is not None
    assert stage_result.declared_output_path.is_file()
    assert stage_result.output_dir.is_dir()
    assert stage_result.run_summary_path.is_file()


def test_route_and_projection_behavior_unchanged_with_esp(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    report, _mock_stage = _run_esp_flow(
        uploads={"source": SECOND_SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot = report.result.slots[0]
    assert slot.projection_results
    module_result = slot.route_semantic_module_results[0]
    assert module_result.route_invoked is True
    assert module_result.stage_result is not None
    assert module_result.stage_result.routing_manifest_path.is_file()


def test_canonical_flow_does_not_use_legacy_sequence_or_operations(
    tmp_path: Path,
) -> None:
    source = FLOW_PATH.read_text(encoding="utf-8")
    assert "sequence.py" not in source
    assert "operations.py" not in source
    assert "scripts.stage_runners.evidence_source_preparation" not in source


def test_flow_does_not_introduce_semantic_module_to_filter_job_mapping() -> None:
    source = FLOW_PATH.read_text(encoding="utf-8")
    assert "filter_job_id_by_semantic_module" not in source
    assert "semantic_module_id_to_filter_job" not in source


def test_zero_selected_route_records_esp_not_invoked(tmp_path: Path) -> None:
    assert SECOND_SAMPLE_DOCX.is_file()
    empty_route_capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="test_empty_route_esp",
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
        "projection_runtime_dependencies": flow_projection_runtime_dependencies(),
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
    assert module_result.route_invoked is False
    assert module_result.evidence_source_preparation_invoked is False
