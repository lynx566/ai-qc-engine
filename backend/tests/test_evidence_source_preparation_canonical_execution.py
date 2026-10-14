"""Canonical unified Evidence Source Preparation execution tests."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION,
)
from llm.invocation import LLMInvocationRecord
from operations.evidence_source_preparation.contracts import (
    EvidenceSourcePreparationExecutor,
    EvidenceSourcePreparationInvocation,
    EvidenceSourcePreparationResult,
)
from steps import evidence_source_preparation as esp_step
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.aggregate_evidence_execution import (
    run_aggregate_evidence_execution,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING,
    CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceExecution,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.executor import (
    execute_clinical_trial_aggregate_evidence_source_preparation,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceExecutionInput,
    AggregateEvidenceRouteArtifactsInput,
    EvidenceSourcePreparationUpstreamInput,
)
from runtime.io import load_json
from tests.route_runtime_test_helpers import (
    persist_route_artifacts_from_coverage,
    write_upstream_route_fixtures,
)

STEP_PATH = BACKEND_ROOT / "steps/evidence_source_preparation.py"
EXECUTION_PATH = (
    BACKEND_ROOT
    / "plugins/clinical_trial_doc/evidence_source_preparation/clinical_safety/aggregate_evidence/aggregate_evidence_execution.py"
)
EXECUTOR_PATH = (
    BACKEND_ROOT
    / "plugins/clinical_trial_doc/evidence_source_preparation/clinical_safety/aggregate_evidence/executor.py"
)


def _build_execution_input(tmp_path: Path) -> AggregateEvidenceExecutionInput:
    paths = write_upstream_route_fixtures(tmp_path)
    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=tmp_path / "route_out",
        run_id="canonical_route",
    )
    aggregate_bundle = load_json(route_result.routed_bundle_paths["aggregate"])
    routing_manifest = load_json(route_result.routing_manifest_path)
    return AggregateEvidenceExecutionInput(
        upstream=EvidenceSourcePreparationUpstreamInput(
            coverage_bundle=load_json(paths["coverage"]),
            block_manifest=load_json(paths["block_manifest"]),
            doc_meta_bundle=load_json(paths["doc_meta_bundle"]),
            analysis_bundle=load_json(paths["analysis"]),
        ),
        route_artifacts=AggregateEvidenceRouteArtifactsInput(
            route_counts=dict(route_result.route_counts),
            aggregate_bundle=aggregate_bundle,
            routing_manifest=routing_manifest,
            source_routed_unit_bundle_filename="routed_units_aggregate.json",
            routing_manifest_filename="routing_manifest.json",
        ),
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        llm_mode="mock",
    )


def _canonical_run_block() -> str:
    source = STEP_PATH.read_text(encoding="utf-8")
    return source.split("def run_evidence_source_preparation", 1)[1]


def test_run_evidence_source_preparation_is_canonical_entry(tmp_path: Path) -> None:
    invocation = _build_execution_input(tmp_path)
    execution = esp_step.run_evidence_source_preparation(
        invocation=invocation,
        executor=INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
    )
    assert isinstance(execution, AggregateEvidenceExecution)
    assert execution.aggregate_evidence_source_bundle["artifact_type"] == (
        "aggregate_evidence_source_bundle"
    )
    assert (
        execution.aggregate_evidence_source_bundle["schema_version"]
        == AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION
    )


def test_canonical_entry_delegates_exactly_once_to_injected_executor(
    tmp_path: Path,
) -> None:
    invocation = _build_execution_input(tmp_path)
    captured: dict[str, Any] = {}

    def _recording_executor(
        *,
        invocation: EvidenceSourcePreparationInvocation,
    ) -> EvidenceSourcePreparationResult:
        captured["invocation"] = invocation
        return execute_clinical_trial_aggregate_evidence_source_preparation(
            invocation=invocation,
        )

    execution = esp_step.run_evidence_source_preparation(
        invocation=invocation,
        executor=_recording_executor,
    )
    assert captured["invocation"] is invocation
    assert execution.assemble.aggregate_evidence_source_bundle


def test_run_aggregate_evidence_execution_runs_prepare_assess_eligibility_assemble_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution_input = _build_execution_input(tmp_path)
    calls: list[str] = []

    import plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.aggregate_evidence_execution as execution_module

    original_prepare = execution_module.run_aggregate_evidence_prepare
    original_assess = execution_module.run_aggregate_evidence_assess_heading_scopes
    original_eligibility = (
        execution_module.run_aggregate_evidence_evaluate_heading_scope_eligibility
    )
    original_assemble = execution_module.assemble_aggregate_evidence_source_bundle

    def _track_prepare(**kwargs: Any) -> Any:
        calls.append("prepare")
        return original_prepare(**kwargs)

    def _track_assess(**kwargs: Any) -> Any:
        calls.append("assess")
        return original_assess(**kwargs)

    def _track_eligibility(**kwargs: Any) -> Any:
        calls.append("eligibility")
        return original_eligibility(**kwargs)

    def _track_assemble(**kwargs: Any) -> Any:
        calls.append("assemble")
        return original_assemble(**kwargs)

    monkeypatch.setattr(execution_module, "run_aggregate_evidence_prepare", _track_prepare)
    monkeypatch.setattr(
        execution_module,
        "run_aggregate_evidence_assess_heading_scopes",
        _track_assess,
    )
    monkeypatch.setattr(
        execution_module,
        "run_aggregate_evidence_evaluate_heading_scope_eligibility",
        _track_eligibility,
    )
    monkeypatch.setattr(
        execution_module,
        "assemble_aggregate_evidence_source_bundle",
        _track_assemble,
    )

    run_aggregate_evidence_execution(
        execution_input=execution_input,
        semantic_binding=CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
    )
    assert calls == ["prepare", "assess", "eligibility", "assemble"]


def test_run_aggregate_evidence_execution_uses_clinical_safety_semantic_binding(
    tmp_path: Path,
) -> None:
    execution = run_aggregate_evidence_execution(
        execution_input=_build_execution_input(tmp_path),
        semantic_binding=CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
    )
    assert (
        execution.prepare.assessment_input["assessment_profile_ref"]
        == CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.assessment_profile_ref
    )
    assert (
        execution.prepare.assessment_input["instructions"]
        == CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.instructions
    )


def test_canonical_execution_assess_call_has_no_review_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution_input = _build_execution_input(tmp_path)
    captured_prepare: dict[str, Any] = {}
    captured_assess: dict[str, Any] = {}

    import plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.aggregate_evidence_execution as execution_module

    original_prepare = execution_module.run_aggregate_evidence_prepare
    original_assess = execution_module.run_aggregate_evidence_assess_heading_scopes

    def _capture_prepare(**kwargs: Any) -> Any:
        captured_prepare.update(kwargs)
        return original_prepare(**kwargs)

    def _capture_assess(**kwargs: Any) -> Any:
        captured_assess.update(kwargs)
        return original_assess(**kwargs)

    monkeypatch.setattr(
        execution_module,
        "run_aggregate_evidence_prepare",
        _capture_prepare,
    )
    monkeypatch.setattr(
        execution_module,
        "run_aggregate_evidence_assess_heading_scopes",
        _capture_assess,
    )

    run_aggregate_evidence_execution(
        execution_input=execution_input,
        semantic_binding=CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
    )

    assert "pre_llm_review_mode" not in captured_prepare
    for residue_key in (
        "pre_llm_review_state",
        "formal_pre_llm_review_state",
        "pre_llm_review_state_path",
    ):
        assert residue_key not in captured_assess


def test_canonical_unified_persist_omits_retired_review_artifacts(
    tmp_path: Path,
) -> None:
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
        persist_unified_aggregate_evidence_execution,
    )

    execution = run_aggregate_evidence_execution(
        execution_input=_build_execution_input(tmp_path),
        semantic_binding=CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
    )
    execution = replace(
        execution,
        assess=replace(
            execution.assess,
            llm_invocations=(
                LLMInvocationRecord(
                    provider="test-provider",
                    model="test-model",
                    config_id="clinical_trial_doc_esp_aggregate",
                    profile_id="test-profile",
                    status="success",
                    elapsed_ms=17,
                    request_id="request-17",
                    usage={"total_tokens": 9},
                    error_type=None,
                    error_message=None,
                    attempt_index=1,
                ),
            ),
        ),
    )
    paths = write_upstream_route_fixtures(tmp_path)
    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=tmp_path / "route_persist",
        run_id="canonical_persist",
    )
    out_dir = tmp_path / "esp_out"
    persist_unified_aggregate_evidence_execution(
        execution=execution,
        output_dir=out_dir,
        run_id="canonical_persist_run",
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        routed_aggregate_bundle_path=route_result.routed_bundle_paths["aggregate"],
        routing_manifest_path=route_result.routing_manifest_path,
    )
    assert not (out_dir / "pre_llm_review_state.json").is_file()
    assert not (out_dir / "pre_llm_review_bundle.json").is_file()
    assert not (out_dir / "pre_llm_audit_bundle_private.json").is_file()
    summary = load_json(out_dir / "run_summary.json")
    assert summary["llm_invocations"] == [
        {
            "provider": "test-provider",
            "model": "test-model",
            "config_id": "clinical_trial_doc_esp_aggregate",
            "profile_id": "test-profile",
            "status": "success",
            "elapsed_ms": 17,
            "request_id": "request-17",
            "usage": {"total_tokens": 9},
            "error_type": None,
            "error_message": None,
            "attempt_index": 1,
            "response_format_applied": False,
        }
    ]


@dataclass
class _SyntheticInvocation(EvidenceSourcePreparationInvocation):
    token: str


@dataclass
class _SyntheticResult(EvidenceSourcePreparationResult):
    token: str


class _SyntheticExecutor:
    def __call__(
        self,
        *,
        invocation: EvidenceSourcePreparationInvocation,
    ) -> EvidenceSourcePreparationResult:
        return _SyntheticResult(token=str(getattr(invocation, "token", "unknown")))


def test_synthetic_non_aggregate_executor_satisfies_neutral_contract(
    tmp_path: Path,
) -> None:
    invocation = _SyntheticInvocation(token="synthetic")
    result = esp_step.run_evidence_source_preparation(
        invocation=invocation,
        executor=_SyntheticExecutor(),
    )
    assert isinstance(result, _SyntheticResult)
    assert result.token == "synthetic"


def test_canonical_entry_rejects_non_neutral_executor_result(tmp_path: Path) -> None:
    invocation = _build_execution_input(tmp_path)

    class _BadExecutor:
        def __call__(
            self,
            *,
            invocation: EvidenceSourcePreparationInvocation,
        ) -> object:
            return object()

    with pytest.raises(TypeError, match="EvidenceSourcePreparationResult"):
        esp_step.run_evidence_source_preparation(
            invocation=invocation,
            executor=_BadExecutor(),
        )


def test_aggregate_executor_delegates_to_execution_orchestrator(tmp_path: Path) -> None:
    invocation = _build_execution_input(tmp_path)
    captured: dict[str, Any] = {}

    import plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.executor as executor_module

    original_run = executor_module.run_aggregate_evidence_execution

    def _track_run(
        *,
        execution_input: AggregateEvidenceExecutionInput,
        semantic_binding: Any,
    ) -> AggregateEvidenceExecution:
        captured["execution_input"] = execution_input
        captured["semantic_binding"] = semantic_binding
        return original_run(
            execution_input=execution_input,
            semantic_binding=semantic_binding,
        )

    executor_module.run_aggregate_evidence_execution = _track_run  # type: ignore[method-assign]
    try:
        execution = execute_clinical_trial_aggregate_evidence_source_preparation(
            invocation=invocation,
            semantic_binding=CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
        )
    finally:
        executor_module.run_aggregate_evidence_execution = original_run  # type: ignore[method-assign]
    assert captured["execution_input"] is invocation
    assert captured["semantic_binding"] is CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING
    assert isinstance(execution, AggregateEvidenceExecution)


def test_processor_module_removed() -> None:
    processor_path = (
        BACKEND_ROOT
        / "plugins/clinical_trial_doc/evidence_source_preparation/processor.py"
    )
    assert not processor_path.is_file()


def test_generic_step_exposes_only_canonical_entry() -> None:

    source = STEP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(STEP_PATH))
    function_names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]
    assert function_names == ["run_evidence_source_preparation"]
    for retired_helper in (
        "run_prepare_aggregate_evidence_assessment_input",
        "run_assess_aggregate_evidence_heading_scopes",
        "run_evaluate_aggregate_evidence_heading_scope_eligibility",
        "run_assemble_aggregate_evidence_source_bundle",
    ):
        assert retired_helper not in source


def test_canonical_execution_input_has_no_review_controls() -> None:
    params = AggregateEvidenceExecutionInput.__dataclass_fields__
    assert "pre_llm_review_mode" not in params
    assert "skip_review_gate" not in params


def test_canonical_api_has_no_through_operation() -> None:
    step_source = STEP_PATH.read_text(encoding="utf-8")
    assert "through_operation" not in step_source
    execution_source = EXECUTION_PATH.read_text(encoding="utf-8")
    assert "through_operation" not in execution_source
    assert "run_pre_assemble_sequence" not in execution_source
    assert "sequence.py" not in execution_source


def test_neutral_canonical_entry_imports_only_operation_contracts() -> None:
    block = _canonical_run_block()
    assert "operations.evidence_source_preparation" in STEP_PATH.read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "AggregateEvidenceExecutionInput",
        "AggregateEvidenceExecution",
        "CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING",
        "plugins.clinical_trial_doc",
        "validate_aggregate_evidence_source_bundle",
        "validate_heading_scope_eligibility",
    ):
        assert forbidden not in block


def test_neutral_step_does_not_import_clinical_safety_semantic_modules() -> None:
    block = _canonical_run_block()
    forbidden = (
        "clinical_safety_semantic_binding",
        "clinical_safety_aggregate_heading_scope_assessment_zh",
        "heading_scope_eligibility_policy",
    )
    for token in forbidden:
        assert token not in block


def test_neutral_step_does_not_sequence_aggregate_phases_directly() -> None:
    run_evidence_block = _canonical_run_block()
    assert "facade.prepare(" not in run_evidence_block
    assert "facade.assess(" not in run_evidence_block
    assert "facade.eligibility(" not in run_evidence_block
    assert "facade.assemble(" not in run_evidence_block
    assert "executor(" in run_evidence_block


def test_canonical_execution_does_not_write_files(tmp_path: Path) -> None:
    invocation = _build_execution_input(tmp_path)
    before = set(tmp_path.rglob("*"))
    esp_step.run_evidence_source_preparation(
        invocation=invocation,
        executor=INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
    )
    after = set(tmp_path.rglob("*"))
    assert before == after


def test_aggregate_executor_owns_aggregate_validation() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    for token in (
        "validate_aggregate_evidence_prepare_route_artifacts",
        "validate_aggregate_evidence_prepare_assessment_artifacts",
        "validate_scope_assessments_envelope",
        "validate_heading_scope_eligibility",
        "validate_aggregate_evidence_source_bundle",
        "run_aggregate_evidence_execution",
    ):
        assert token in source


def test_installed_executor_matches_plugin_executor() -> None:
    from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_installation import (
        INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
    )
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.executor import (
        CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
    )

    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR
        is not CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR
    )
    assert isinstance(
        INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
        EvidenceSourcePreparationExecutor,
    )
