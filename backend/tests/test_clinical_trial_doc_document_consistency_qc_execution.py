"""Tests for installed Clinical Trial × Document Consistency QC execution."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc import (
    execute_installed_clinical_trial_document_consistency_qc,
)
from application.clinical_trial_doc_consistency_qc import (
    execution as execution_module,
)
from application.clinical_trial_doc_consistency_qc import (
    projection_runtime as projection_runtime_module,
)
from application.clinical_trial_doc_consistency_qc.expected_document_type_installation import (
    CLINICAL_TRIAL_DOCUMENT_TYPES,
)
from application.document_consistency_qc import DocumentConsistencyQcExecutionRequest
from application.document_consistency_qc.admitted_source import admit_participant_source_path
from capability import INTERNAL_DSUR_CONSISTENCY_QC
from execution_flow.document_consistency_qc import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcFlowReport,
    DocumentConsistencyQcFlowResult,
    DocumentConsistencyQcParticipantSlot,
    DocumentConsistencyQcParticipantRunInput,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from operations.prepare_analysis import (
    PrepareAnalysisPrivacyConfiguration,
    PrepareAnalysisRequestOptions,
)
from scripts import run_consistency_qc

EXECUTION_REQUEST_PATH = (
    BACKEND_ROOT
    / "application"
    / "document_consistency_qc"
    / "execution_request.py"
)
EXECUTION_PATH = (
    BACKEND_ROOT
    / "application"
    / "clinical_trial_doc_consistency_qc"
    / "execution.py"
)


@dataclass(frozen=True, slots=True)
class NeutralPrivacyConfiguration(PrepareAnalysisPrivacyConfiguration):
    label: str


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _flow_report() -> DocumentConsistencyQcFlowReport:
    return DocumentConsistencyQcFlowReport(
        result=DocumentConsistencyQcFlowResult(slots=()),
        messages=(),
        flow_run_id="executor_test",
        flow_run_summary_path=Path("/tmp/flow_run_summary.json"),
    )


def _application_result(
    flow_report: DocumentConsistencyQcFlowReport,
) -> SimpleNamespace:
    return SimpleNamespace(flow_report=flow_report, slots=())


def _installed_request(
    tmp_path: Path,
    *,
    capability_id: str = INTERNAL_DSUR_CONSISTENCY_QC.capability_id,
    slot_id: str = "source",
    source: Path | None = None,
    privacy_path: Path | None = None,
) -> DocumentConsistencyQcExecutionRequest:
    source_path = source if source is not None else tmp_path / "source.docx"
    if not source_path.is_file():
        source_path.write_bytes(b"executor-test")
    admitted = admit_participant_source_path(
        project_root=tmp_path,
        source_path=source_path,
    )
    return DocumentConsistencyQcExecutionRequest(
        capability_id=capability_id,
        project_root=tmp_path,
        participant_inputs={slot_id: admitted},
        participant_privacy_paths={slot_id: privacy_path},
        source_language="zh",
    )


def test_installed_prepare_and_execute_share_one_flow_handle(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    request = _installed_request(tmp_path)
    flow_handle = SimpleNamespace(
        execution=SimpleNamespace(
            flow_id="document_consistency_qc",
            flow_run_id="document_consistency_qc_test_run",
        )
    )
    flow_report = _flow_report()
    application_result = _application_result(flow_report)

    with (
        patch.object(
            execution_module,
            "_resolve_projection_runtime_dependencies",
            return_value=object(),
        ),
        patch.object(
            execution_module,
            "_resolve_evidence_source_preparation_execution_dependencies",
            return_value=object(),
        ),
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
            return_value=flow_handle,
        ) as allocate_flow,
        patch.object(
            execution_module,
            "execute_prepared_document_consistency_qc_flow",
            return_value=flow_report,
        ) as execute_flow,
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=application_result,
        ),
    ):
        prepared = execution_module.prepare_and_allocate_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
        )
        assert prepared.flow is flow_handle
        assert prepared.flow_run_id == "document_consistency_qc_test_run"
        result = execution_module.execute_prepared_installed_clinical_trial_document_consistency_qc(
            prepared
        )

    assert result is application_result
    assert allocate_flow.call_args.kwargs["capability_config"] is composition.capabilities[
        request.capability_id
    ]
    execute_flow.assert_called_once_with(flow_handle)


def test_execution_request_has_no_clinical_imports() -> None:
    tree = ast.parse(EXECUTION_REQUEST_PATH.read_text(encoding="utf-8"))
    imported = _imported_module_names(tree)
    forbidden = sorted(
        module
        for module in imported
        if module.startswith(
            (
                "application.clinical_trial_doc_consistency_qc.",
                "plugins.clinical_trial_doc.",
            )
        )
        or module
        in {
            "application.clinical_trial_doc_consistency_qc",
            "plugins.clinical_trial_doc",
        }
    )
    assert forbidden == []


def test_execution_module_does_not_import_runner() -> None:
    tree = ast.parse(EXECUTION_PATH.read_text(encoding="utf-8"))
    imported = _imported_module_names(tree)
    assert "scripts.run_consistency_qc" not in imported
    assert "scripts" not in imported


def test_executor_resolves_capability_from_composition(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    request = _installed_request(tmp_path)
    flow_report = _flow_report()
    application_result = _application_result(flow_report)

    with (
        patch.object(
            projection_runtime_module,
            "materialize_llm_provider",
            return_value=object(),
        ),
        patch.object(
            execution_module,
            "materialize_llm_provider",
            return_value=object(),
        ),
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
            return_value=flow_report,
        ) as flow,
        patch.object(
            execution_module,
            "execute_prepared_document_consistency_qc_flow",
            return_value=flow_report,
        ),
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=application_result,
        ),
    ):
        result = execute_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
        )

    assert result is application_result
    assert (
        flow.call_args.kwargs["capability_config"]
        is (composition.capabilities[request.capability_id])
    )
    assert (
        flow.call_args.kwargs["capability_config"].capability_id
        == INTERNAL_DSUR_CONSISTENCY_QC.capability_id
    )


def test_executor_passes_composition_ports_to_flow(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    request = _installed_request(tmp_path)
    flow_report = _flow_report()
    sentinel_projection_provider = object()
    sentinel_esp_provider = object()

    with (
        patch.object(
            projection_runtime_module,
            "materialize_llm_provider",
            return_value=sentinel_projection_provider,
        ) as projection_materialize,
        patch.object(
            execution_module,
            "materialize_llm_provider",
            return_value=sentinel_esp_provider,
        ) as esp_materialize,
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
            return_value=flow_report,
        ) as flow,
        patch.object(
            execution_module,
            "execute_prepared_document_consistency_qc_flow",
            return_value=flow_report,
        ),
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=_application_result(flow_report),
        ),
    ):
        execute_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
        )

    projection_materialize.assert_called_once()
    esp_materialize.assert_called_once()
    kwargs = flow.call_args.kwargs
    assert kwargs["project_root"] == request.project_root
    assert kwargs["uploads"] == request.participant_inputs
    assert kwargs["source_language"] == request.source_language
    assert kwargs["extract_bindings"] is composition.extract_bindings
    assert kwargs["prepare_analysis_bindings"] is composition.prepare_analysis_bindings
    assert kwargs["filter_job_bindings"] is composition.filter_job_bindings
    assert (
        kwargs["prepare_analysis_config_registry"]
        is composition.prepare_analysis_config_registry
    )
    assert kwargs["doc_meta_profile"] is composition.doc_meta_profile
    assert kwargs["doc_meta_summary_builder"] is composition.doc_meta_summary_builder
    assert kwargs["filter_job_variants"] is composition.filter_job_variants
    assert (
        kwargs["filter_output_projection_jobs"]
        is composition.filter_output_projection_jobs
    )
    assert (
        kwargs["filter_output_projection_facade_builder"]
        is composition.filter_output_projection_facade_builder
    )
    assert (
        kwargs["projected_source_route_executor"]
        is composition.projected_source_route_executor
    )
    assert (
        kwargs["route_semantic_module_sequence"]
        is composition.route_semantic_module_sequence
    )
    assert (
        kwargs["evidence_source_preparation_consumer_bindings"]
        is composition.evidence_source_preparation_consumer_bindings
    )
    esp_deps = kwargs["evidence_source_preparation_execution_dependencies"]
    assert esp_deps.llm_mode == "api"
    assert esp_deps.provider is sentinel_esp_provider
    deps = kwargs["projection_runtime_dependencies"]
    assert isinstance(deps, FilterOutputProjectionRuntimeDependencies)
    assert deps.llm_provider is sentinel_projection_provider


def test_executor_passes_runtime_dependencies_unchanged(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    request = _installed_request(tmp_path)
    flow_report = _flow_report()
    runtime_dependencies = FilterOutputProjectionRuntimeDependencies(
        llm_provider=object(),
    )

    with (
        patch.object(
            execution_module,
            "materialize_llm_provider",
            return_value=object(),
        ),
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
            return_value=flow_report,
        ) as flow,
        patch.object(
            execution_module,
            "execute_prepared_document_consistency_qc_flow",
            return_value=flow_report,
        ),
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=_application_result(flow_report),
        ),
    ):
        execute_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
            projection_runtime_dependencies=runtime_dependencies,
        )

    assert (
        flow.call_args.kwargs["projection_runtime_dependencies"] is runtime_dependencies
    )
    assert (
        flow.call_args.kwargs["evidence_comparison_consumer_bindings"]
        is composition.evidence_comparison_consumer_bindings
    )
    assert callable(
        flow.call_args.kwargs["materialize_evidence_comparison_execution_dependencies"]
    )


def test_executor_builds_participant_inputs_from_privacy_paths(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    privacy_path = tmp_path / "privacy.json"
    privacy_path.write_text("{}", encoding="utf-8")
    request = _installed_request(tmp_path, privacy_path=privacy_path)
    flow_report = _flow_report()
    loader_calls: list[Path | None] = []

    def recording_loader(path: Path | None) -> PrepareAnalysisRequestOptions:
        loader_calls.append(path)
        label = path.name if path is not None else "identity"
        return PrepareAnalysisRequestOptions(
            privacy_config=NeutralPrivacyConfiguration(label)
        )

    composition = replace(
        composition,
        load_prepare_request_options=recording_loader,
    )

    with (
        patch.object(
            projection_runtime_module,
            "materialize_llm_provider",
            return_value=object(),
        ),
        patch.object(
            execution_module,
            "materialize_llm_provider",
            return_value=object(),
        ),
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
            return_value=flow_report,
        ) as flow,
        patch.object(
            execution_module,
            "execute_prepared_document_consistency_qc_flow",
            return_value=flow_report,
        ),
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=_application_result(flow_report),
        ),
    ):
        execute_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
        )

    assert loader_calls == [privacy_path]
    participant = flow.call_args.kwargs["participant_inputs"]["source"]
    assert isinstance(participant, DocumentConsistencyQcParticipantRunInput)
    assert (
        participant.prepare_analysis_request_options.privacy_config.label
        == "privacy.json"
    )


def test_executor_participant_inputs_match_runner_semantics_for_resolved_paths(
    tmp_path: Path,
) -> None:
    capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="semantic_one",
        slots=(DocumentConsistencyQcParticipantSlot(slot_id="participant"),),
    )
    privacy_path = tmp_path / "privacy_a.json"
    privacy_path.write_text("{}", encoding="utf-8")
    loader_calls: list[Path | None] = []

    def recording_loader(path: Path | None) -> PrepareAnalysisRequestOptions:
        loader_calls.append(path)
        label = path.name if path is not None else "identity"
        return PrepareAnalysisRequestOptions(
            privacy_config=NeutralPrivacyConfiguration(label)
        )

    runner_inputs = run_consistency_qc._build_participant_inputs(
        SimpleNamespace(
            privacy_config=str(privacy_path),
            privacy_config_a=None,
            privacy_config_b=None,
        ),
        capability_config=capability,
        load_prepare_request_options=recording_loader,
    )
    loader_calls.clear()

    executor_inputs = execution_module._build_participant_inputs(
        capability_config=capability,
        participant_privacy_paths={"participant": privacy_path},
        load_prepare_request_options=recording_loader,
    )

    assert loader_calls == [privacy_path]
    assert executor_inputs == runner_inputs


def test_executor_derives_application_result(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    request = _installed_request(tmp_path)
    flow_report = _flow_report()
    application_result = _application_result(flow_report)

    with (
        patch.object(
            projection_runtime_module,
            "materialize_llm_provider",
            return_value=object(),
        ),
        patch.object(
            execution_module,
            "materialize_llm_provider",
            return_value=object(),
        ),
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
            return_value=flow_report,
        ),
        patch.object(
            execution_module,
            "execute_prepared_document_consistency_qc_flow",
            return_value=flow_report,
        ),
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=application_result,
        ) as enrich,
    ):
        result = execute_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
        )

    enrich.assert_called_once_with(
        capability_id=request.capability_id,
        flow_report=flow_report,
        expected_document_type_bindings=composition.expected_document_type_bindings,
        supported_document_types=CLINICAL_TRIAL_DOCUMENT_TYPES,
    )
    assert result is application_result


def test_two_slot_participant_inputs_follow_capability_slot_order(
    tmp_path: Path,
) -> None:
    capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="semantic_two",
        slots=(
            DocumentConsistencyQcParticipantSlot(slot_id="first_slot"),
            DocumentConsistencyQcParticipantSlot(slot_id="second_slot"),
        ),
    )
    privacy_a = tmp_path / "privacy_a.json"
    privacy_b = tmp_path / "privacy_b.json"
    loader_calls: list[Path | None] = []

    def recording_loader(path: Path | None) -> PrepareAnalysisRequestOptions:
        loader_calls.append(path)
        label = path.name if path is not None else "identity"
        return PrepareAnalysisRequestOptions(
            privacy_config=NeutralPrivacyConfiguration(label)
        )

    participant_inputs = execution_module._build_participant_inputs(
        capability_config=capability,
        participant_privacy_paths={
            "first_slot": privacy_a,
            "second_slot": privacy_b,
        },
        load_prepare_request_options=recording_loader,
    )

    assert loader_calls == [privacy_a, privacy_b]
    assert tuple(participant_inputs) == ("first_slot", "second_slot")
    assert (
        participant_inputs[
            "first_slot"
        ].prepare_analysis_request_options.privacy_config.label
        == "privacy_a.json"
    )
    assert (
        participant_inputs[
            "second_slot"
        ].prepare_analysis_request_options.privacy_config.label
        == "privacy_b.json"
    )
