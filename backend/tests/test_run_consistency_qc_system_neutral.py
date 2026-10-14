"""Concrete Flow CLI helper guards for the consistency-QC production entry."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import execution_flow.document_consistency_qc.flow as document_consistency_qc_flow_module
from application.document_consistency_qc import (
    DocumentConsistencyQcExecutionRequest,
)
from execution_flow.document_consistency_qc import (
    CandidateScopeDecisionMode,
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
)
from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBindings,
)
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationExecutionDependencies,
)
from operations.prepare_analysis import (
    PrepareAnalysisConfigId,
    PrepareAnalysisPrivacyConfiguration,
    PrepareAnalysisRequestOptions,
)
from operations.prepare_analysis.registry import (
    PrepareAnalysisConfigRegistry,
)
from scripts import run_consistency_qc

RUN_CONSISTENCY_QC_PATH = BACKEND_ROOT / "scripts" / "run_consistency_qc.py"


@dataclass(frozen=True, slots=True)
class NeutralPrivacyConfiguration(PrepareAnalysisPrivacyConfiguration):
    label: str


def _capability(
    capability_id: str,
    *slot_ids: str,
) -> DocumentConsistencyQcCapabilityConfig:
    return DocumentConsistencyQcCapabilityConfig(
        capability_id=capability_id,
        slots=tuple(
            DocumentConsistencyQcParticipantSlot(
                slot_id=slot_id,
            )
            for slot_id in slot_ids
        ),
    )


def _bindings_for_capability(
    capability: DocumentConsistencyQcCapabilityConfig,
) -> tuple[
    dict[tuple[str, str], str],
    dict[tuple[str, str], PrepareAnalysisConfigId],
    dict[tuple[str, str], tuple[str, ...]],
]:
    config_id = PrepareAnalysisConfigId("pacfg_neutral_test")
    extract_bindings: dict[tuple[str, str], str] = {}
    prepare_bindings: dict[tuple[str, str], PrepareAnalysisConfigId] = {}
    filter_bindings: dict[tuple[str, str], tuple[str, ...]] = {}
    for slot in capability.slots:
        key = (capability.capability_id, slot.slot_id)
        extract_bindings[key] = "neutral_extract"
        prepare_bindings[key] = config_id
        filter_bindings[key] = ()
    return extract_bindings, prepare_bindings, filter_bindings


def _neutral_loaders():
    request_calls: list[Path | None] = []

    def load_request(path: Path | None) -> PrepareAnalysisRequestOptions:
        request_calls.append(path)
        label = path.name if path is not None else "identity"
        return PrepareAnalysisRequestOptions(
            privacy_config=NeutralPrivacyConfiguration(label)
        )

    return load_request, request_calls


class _NeutralFilterOutputProjectionFacadeBuilder:
    """Minimal structural stub; flow is patched in these harness tests."""

    def build(self, *, job: object, runtime_dependencies: object) -> object:
        raise AssertionError("neutral harness tests should not reach projection")


def _neutral_projected_source_route_executor():
    from artifacts.routing.types import ROUTES, RoutedUnitSet

    def executor(**kwargs: object) -> RoutedUnitSet:
        _ = kwargs
        units_by_route = {route: [] for route in ROUTES}
        route_counts = {f"{route}_unit_count": 0 for route in ROUTES}
        route_counts["total_routed_unit_count"] = 0
        return RoutedUnitSet(
            units_by_route=units_by_route,
            route_counts=route_counts,
            all_units=(),
        )

    return executor


class _NeutralEvidenceSourcePreparationExecutionDependencies(
    EvidenceSourcePreparationExecutionDependencies,
):
    """Minimal marker for the concrete Flow harness tests."""


def _neutral_evidence_source_preparation_dependencies() -> dict[str, object]:
    return {
        "evidence_source_preparation_consumer_bindings": (
            EvidenceSourcePreparationConsumerBindings(bindings={})
        ),
        "evidence_source_preparation_execution_dependencies": (
            _NeutralEvidenceSourcePreparationExecutionDependencies()
        ),
    }


def _neutral_projection_route_dependencies() -> dict[str, object]:
    return {
        "filter_output_projection_jobs": {},
        "filter_output_projection_facade_builder": (
            _NeutralFilterOutputProjectionFacadeBuilder()
        ),
        "route_semantic_module_sequence": (),
        "projected_source_route_executor": _neutral_projected_source_route_executor(),
        **_neutral_evidence_source_preparation_dependencies(),
    }


def _invoke_flow(
    *,
    capability: DocumentConsistencyQcCapabilityConfig,
    argv: list[str],
):
    load_request, request_calls = _neutral_loaders()
    registry = PrepareAnalysisConfigRegistry()
    extract_bindings, prepare_bindings, filter_bindings = _bindings_for_capability(
        capability
    )
    report = object()
    doc_meta_profile = object()
    def doc_meta_summary_builder(metadata_base):
        return metadata_base
    filter_job_variants = {}
    args = run_consistency_qc._parse_args({capability.capability_id: capability}, argv)
    run_consistency_qc._validate_args(args, capability_config=capability)
    project_root = run_consistency_qc._resolve_project_root(args.project_root)
    uploads = run_consistency_qc._build_uploads(args, capability_config=capability)
    participant_inputs = run_consistency_qc._build_participant_inputs(
        args,
        capability_config=capability,
        load_prepare_request_options=load_request,
    )
    with patch.object(
        document_consistency_qc_flow_module,
        "run_document_consistency_qc_flow",
        return_value=report,
    ) as flow:
        document_consistency_qc_flow_module.run_document_consistency_qc_flow(
            project_root=project_root,
            capability_config=capability,
            uploads=uploads,
            participant_inputs=participant_inputs,
            source_language=args.source_language,
            extract_bindings=extract_bindings,
            prepare_analysis_bindings=prepare_bindings,
            filter_job_bindings=filter_bindings,
            prepare_analysis_config_registry=registry,
            doc_meta_profile=doc_meta_profile,
            doc_meta_summary_builder=doc_meta_summary_builder,
            filter_job_variants=filter_job_variants,
            **_neutral_projection_route_dependencies(),
        )
    return (
        flow.call_args.kwargs,
        request_calls,
        registry,
        doc_meta_profile,
        doc_meta_summary_builder,
    )


def test_one_slot_uses_unsuffixed_inputs_and_injected_loaders(tmp_path: Path) -> None:
    capability = _capability("neutral_one", "participant")
    source = tmp_path / "one.docx"
    privacy = tmp_path / "privacy.json"

    kwargs, request_calls, registry, doc_meta_profile, doc_meta_summary_builder = (
        _invoke_flow(
            capability=capability,
            argv=[
                "--capability",
                capability.capability_id,
                "--source",
                str(source),
                "--privacy-config",
                str(privacy),
                "--project-root",
                str(tmp_path),
            ],
        )
    )

    assert kwargs["capability_config"] is capability
    assert kwargs["uploads"] == {"participant": source}
    assert set(kwargs["participant_inputs"]) == {"participant"}
    assert kwargs["prepare_analysis_config_registry"] is registry
    assert kwargs["doc_meta_profile"] is doc_meta_profile
    assert kwargs["doc_meta_summary_builder"] is doc_meta_summary_builder
    assert kwargs["source_language"] == "zh"
    assert request_calls == [privacy]


def test_two_slots_use_ordered_suffixed_inputs_and_injected_loaders(
    tmp_path: Path,
) -> None:
    capability = _capability("neutral_two", "first_slot", "second_slot")
    source_a = tmp_path / "a.docx"
    source_b = tmp_path / "b.docx"
    privacy_a = tmp_path / "privacy_a.json"
    privacy_b = tmp_path / "privacy_b.json"

    kwargs, request_calls, _, _, _ = _invoke_flow(
        capability=capability,
        argv=[
            "--capability",
            capability.capability_id,
            "--source-a",
            str(source_a),
            "--source-b",
            str(source_b),
            "--privacy-config-a",
            str(privacy_a),
            "--privacy-config-b",
            str(privacy_b),
        ],
    )

    assert kwargs["uploads"] == {
        "first_slot": source_a,
        "second_slot": source_b,
    }
    assert tuple(kwargs["participant_inputs"]) == ("first_slot", "second_slot")
    assert request_calls == [privacy_a, privacy_b]


def test_neutral_flow_forwards_projected_source_route_executor(
    tmp_path: Path,
) -> None:
    route_executor = _neutral_projected_source_route_executor()
    capability = _capability("neutral_forward", "participant")
    source = tmp_path / "one.docx"
    deps = _neutral_projection_route_dependencies()
    deps["projected_source_route_executor"] = route_executor
    report = object()
    load_request, _ = _neutral_loaders()
    extract_bindings, prepare_bindings, filter_bindings = _bindings_for_capability(
        capability
    )
    args = run_consistency_qc._parse_args(
        {capability.capability_id: capability},
        [
            "--capability",
            capability.capability_id,
            "--source",
            str(source),
            "--project-root",
            str(tmp_path),
        ],
    )
    with (
        patch.object(
            document_consistency_qc_flow_module,
            "run_document_consistency_qc_flow",
            return_value=report,
        ) as flow,
        patch.object(run_consistency_qc, "_print_summary"),
    ):
        document_consistency_qc_flow_module.run_document_consistency_qc_flow(
            project_root=run_consistency_qc._resolve_project_root(args.project_root),
            capability_config=capability,
            uploads=run_consistency_qc._build_uploads(
                args, capability_config=capability
            ),
            participant_inputs=run_consistency_qc._build_participant_inputs(
                args,
                capability_config=capability,
                load_prepare_request_options=load_request,
            ),
            source_language=args.source_language,
            extract_bindings=extract_bindings,
            prepare_analysis_bindings=prepare_bindings,
            filter_job_bindings=filter_bindings,
            prepare_analysis_config_registry=PrepareAnalysisConfigRegistry(),
            doc_meta_profile=object(),
            doc_meta_summary_builder=lambda metadata_base: metadata_base,
            filter_job_variants={},
            **deps,
        )

    assert flow.call_args.kwargs["projected_source_route_executor"] is route_executor


@pytest.mark.parametrize("slot_ids", [(), ("a", "b", "c")])
def test_unsupported_slot_count_fails_neutrally(slot_ids: tuple[str, ...]) -> None:
    capability = _capability("neutral_unsupported", *slot_ids)
    with pytest.raises(
        SystemExit,
        match=f"unsupported participant-slot count: {len(slot_ids)}",
    ):
        run_consistency_qc._validate_args(
            argparse_namespace_for_capability(capability),
            capability_config=capability,
        )


def argparse_namespace_for_capability(
    capability: DocumentConsistencyQcCapabilityConfig,
) -> SimpleNamespace:
    if len(capability.slots) == 0:
        return SimpleNamespace(
            source=None,
            source_a=None,
            source_b=None,
            privacy_config=None,
            privacy_config_a=None,
            privacy_config_b=None,
        )
    if len(capability.slots) == 1:
        return SimpleNamespace(
            source="doc.docx",
            source_a=None,
            source_b=None,
            privacy_config=None,
            privacy_config_a=None,
            privacy_config_b=None,
        )
    return SimpleNamespace(
        source=None,
        source_a="a.docx",
        source_b="b.docx",
        privacy_config=None,
        privacy_config_a=None,
        privacy_config_b=None,
    )


def test_script_does_not_export_legacy_run_consistency_qc_helper() -> None:
    source = RUN_CONSISTENCY_QC_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUN_CONSISTENCY_QC_PATH))
    defined_functions = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert "run_consistency_qc" not in defined_functions
    assert not hasattr(run_consistency_qc, "run_consistency_qc")


def test_execution_entry_is_directly_executable_and_slot_driven() -> None:
    source = RUN_CONSISTENCY_QC_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUN_CONSISTENCY_QC_PATH))
    assert "capability_config.slots" in source
    assert 'if __name__ == "__main__"' in source
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "main"
        for node in ast.walk(tree)
    )


def test_main_delegates_to_installed_executor() -> None:
    from runtime.document_source_binding import DocumentIntakeSourceBinding

    capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="opaque",
        slots=(DocumentConsistencyQcParticipantSlot(slot_id="participant"),),
    )
    composition = SimpleNamespace(capabilities={"opaque": capability})
    args = SimpleNamespace(
        capability="opaque",
        source_language="zh",
        project_root=None,
        candidate_scope_mode=CandidateScopeDecisionMode.AUTOMATIC_CONTINUE.value,
    )
    uploads = {capability.slots[0].slot_id: Path("/tmp/source.docx")}
    participant_privacy_paths = {capability.slots[0].slot_id: None}
    project_root = Path("/tmp/project")
    application_result = SimpleNamespace(flow_report=object())
    admitted_source = DocumentIntakeSourceBinding(
        file_hash="sha256:" + "a" * 64,
        original_file_name="source.docx",
        source_path=uploads["participant"],
    )
    intake_report = SimpleNamespace(
        result=SimpleNamespace(source_binding=admitted_source)
    )
    prepared = object()
    events: list[str] = []

    def _intake(**kwargs: object) -> object:
        events.append("intake")
        return intake_report

    def _allocate(**kwargs: object) -> object:
        events.append("allocate")
        return prepared

    def _execute(actual: object) -> object:
        events.append("execute")
        assert actual is prepared
        return application_result

    with (
        patch.object(
            run_consistency_qc,
            "build_installed_document_consistency_qc_application_composition",
            return_value=composition,
        ) as build,
        patch.object(run_consistency_qc, "_parse_args", return_value=args),
        patch.object(run_consistency_qc, "_validate_args") as validate,
        patch.object(
            run_consistency_qc,
            "_build_uploads",
            return_value=uploads,
        ) as build_uploads,
        patch.object(
            run_consistency_qc,
            "_build_participant_privacy_paths",
            return_value=participant_privacy_paths,
        ) as build_privacy,
        patch.object(
            run_consistency_qc,
            "_resolve_project_root",
            return_value=project_root,
        ),
        patch.object(
            run_consistency_qc,
            "run_request_file_intake_operation",
            side_effect=_intake,
        ) as intake,
        patch.object(
            run_consistency_qc,
            "prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=_allocate,
        ) as allocate,
        patch.object(
            run_consistency_qc,
            "execute_prepared_installed_clinical_trial_document_consistency_qc",
            side_effect=_execute,
        ) as execute,
        patch.object(run_consistency_qc, "_print_summary") as print_summary,
    ):
        run_consistency_qc.main(["--capability", "opaque"])

    build.assert_called_once_with()
    validate.assert_called_once_with(args, capability_config=capability)
    build_uploads.assert_called_once_with(args, capability_config=capability)
    build_privacy.assert_called_once_with(args, capability_config=capability)
    allocate.assert_called_once_with(
        composition=composition,
        request=DocumentConsistencyQcExecutionRequest(
            capability_id="opaque",
            project_root=project_root,
            participant_inputs={"participant": admitted_source},
            participant_privacy_paths=participant_privacy_paths,
            source_language="zh",
            candidate_scope_decision_mode=(
                CandidateScopeDecisionMode.AUTOMATIC_CONTINUE
            ),
        ),
    )
    execute.assert_called_once_with(prepared)
    assert events == ["intake", "allocate", "execute"]
    print_summary.assert_called_once_with(
        capability_config=capability,
        report=application_result.flow_report,
        standalone_intake_reports={"participant": intake_report},
    )
    intake.assert_called_once_with(
        project_root=project_root,
        source_file=uploads["participant"],
    )


def test_standalone_execute_failure_propagates_without_task_run(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    source.write_bytes(b"doc")
    prepared = object()
    with (
        patch.object(
            run_consistency_qc,
            "prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            return_value=prepared,
        ) as allocate,
        patch.object(
            run_consistency_qc,
            "execute_prepared_installed_clinical_trial_document_consistency_qc",
            side_effect=RuntimeError("standalone execution failed"),
        ) as execute,
        pytest.raises(RuntimeError, match="standalone execution failed"),
    ):
        run_consistency_qc.main(
            [
                "--capability",
                "internal_dsur",
                "--source",
                str(source),
                "--project-root",
                str(tmp_path),
            ]
        )

    assert not hasattr(allocate.call_args.kwargs["request"], "task_run_id")
    execute.assert_called_once_with(prepared)
    assert not (tmp_path / "runs" / "task_runs").exists()


def test_main_does_not_unpack_installed_execution_ports() -> None:
    source = RUN_CONSISTENCY_QC_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUN_CONSISTENCY_QC_PATH))
    main_fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    main_source = ast.get_source_segment(source, main_fn) or ""
    forbidden_tokens = (
        "extract_bindings",
        "prepare_analysis_bindings",
        "filter_job_bindings",
        "prepare_analysis_config_registry",
        "load_prepare_request_options",
        "doc_meta_profile",
        "doc_meta_summary_builder",
        "filter_job_variants",
        "filter_output_projection_jobs",
        "filter_output_projection_facade_builder",
        "route_semantic_module_sequence",
        "expected_document_type_bindings",
        "CLINICAL_TRIAL_DOCUMENT_TYPES",
        "build_document_consistency_qc_application_result",
        "run_consistency_qc(",
        "run_document_consistency_qc_flow(",
    )
    for token in forbidden_tokens:
        assert token not in main_source
    assert "composition.capabilities" in main_source
