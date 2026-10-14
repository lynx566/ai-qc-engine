"""Boundary guards for the neutral ESP canonical entry and aggregate executor."""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
STEP = BACKEND_ROOT / "steps/evidence_source_preparation.py"
EXECUTION = (
    BACKEND_ROOT
    / "plugins/clinical_trial_doc/evidence_source_preparation/clinical_safety/aggregate_evidence/aggregate_evidence_execution.py"
)
EXECUTOR = (
    BACKEND_ROOT
    / "plugins/clinical_trial_doc/evidence_source_preparation/clinical_safety/aggregate_evidence/executor.py"
)
PROCESSOR_PATH = (
    BACKEND_ROOT
    / "plugins/clinical_trial_doc/evidence_source_preparation/processor.py"
)
RUNTIME_OPERATION = (
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/operations.py"
)
PHASE_RUNTIME_MODULES = (
    BACKEND_ROOT / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/prepare.py",
    BACKEND_ROOT / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assess.py",
    BACKEND_ROOT / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/eligibility.py",
    BACKEND_ROOT / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assemble.py",
)
RUNNERS = tuple(
    (
        BACKEND_ROOT
        / "scripts/stage_runners/evidence_source_preparation/aggregate_evidence"
    ).glob("*_runner.py")
)
AGGREGATE_PHASE_HELPER_NAMES = (
    "run_prepare_aggregate_evidence_assessment_input",
    "run_assess_aggregate_evidence_heading_scopes",
    "run_evaluate_aggregate_evidence_heading_scope_eligibility",
    "run_assemble_aggregate_evidence_source_bundle",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def _canonical_run_block() -> str:
    return STEP.read_text(encoding="utf-8")


def test_processor_module_removed() -> None:
    assert not PROCESSOR_PATH.is_file()


def test_execution_orchestrator_is_filesystem_free() -> None:
    source = EXECUTION.read_text(encoding="utf-8")
    assert "run_aggregate_evidence_execution" in source
    assert "runtime." not in source
    assert "scripts." not in source


def test_canonical_step_exposes_only_generic_esp_entry() -> None:
    source = STEP.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(STEP))
    function_names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]
    assert function_names == ["run_evidence_source_preparation"]


def test_canonical_step_has_no_plugin_imports() -> None:
    for module in _imports(STEP):
        assert module is None or not module.startswith("plugins.clinical_trial_doc"), module


def test_canonical_step_delegates_once_to_neutral_executor() -> None:
    block = _canonical_run_block()
    assert "def run_evidence_source_preparation(" in block
    assert block.count("executor(") == 1
    assert "run_aggregate_evidence_execution(" not in block
    assert "load_json" not in block
    assert "Path" not in block


def test_canonical_step_does_not_default_executor() -> None:
    block = _canonical_run_block()
    assert "CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING" not in block
    assert "executor:" in block


def test_aggregate_phase_helpers_removed_from_step() -> None:
    source = STEP.read_text(encoding="utf-8")
    for operation in AGGREGATE_PHASE_HELPER_NAMES:
        assert f"def {operation}(" not in source


def test_aggregate_executor_delegates_to_execution_orchestrator() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert "run_aggregate_evidence_execution(" in source
    assert "AggregateEvidenceExecutionInput" in source
    assert "AggregateEvidenceExecution" in source
    assert "AggregateEvidenceSourcePreparationProcessor" not in source
    assert "processor.execute(" not in source


def test_phase_runtime_does_not_call_pipeline_step_helpers() -> None:
    for path in PHASE_RUNTIME_MODULES:
        source = path.read_text(encoding="utf-8")
        assert "steps" not in source, path.name
        for operation in AGGREGATE_PHASE_HELPER_NAMES:
            assert operation not in source, path.name


def test_phase_runtime_does_not_hardcode_clinical_safety_binding() -> None:
    for path in PHASE_RUNTIME_MODULES:
        source = path.read_text(encoding="utf-8")
        assert "CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING" not in source, path.name


def test_runtime_operation_owns_run_mechanics() -> None:
    source = RUNTIME_OPERATION.read_text(encoding="utf-8")
    for token in (
        "load_json",
        "resolve_stage_phase_artifact_dir",
        "snapshot_git_provenance_before_run",
        "write_run_index",
        "phase_dependencies",
    ):
        assert token in source
    assert "resolve_installed_aggregate_evidence_phase_harness_dependencies" not in source
    assert "resolve_installed_aggregate_evidence_phase_dependencies" not in source
    assert not any(
        module.startswith("application.clinical_trial_doc_consistency_qc")
        for module in _imports(RUNTIME_OPERATION)
    )
    assert not any(
        module.startswith(
            "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence"
        )
        and not module.endswith(".evidence_form_identity")
        for module in _imports(RUNTIME_OPERATION)
    )


def test_runners_resolve_installed_phase_harness_dependencies() -> None:
    for path in RUNNERS:
        source = path.read_text(encoding="utf-8")
        assert (
            "application.clinical_trial_doc_consistency_qc.evidence_source_preparation_phase_harness_installation"
            in source
        )
        assert "resolve_installed_aggregate_evidence_phase_harness_dependencies" in source
        assert "phase_dependencies=" in source
        assert (
            "application.clinical_trial_doc_consistency_qc.evidence_source_preparation_installation"
            not in source
        )


def test_runners_do_not_select_semantic_binding_or_own_run_mechanics() -> None:
    for path in RUNNERS:
        source = path.read_text(encoding="utf-8")
        assert "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.operations" in source
        for forbidden in (
            "CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING",
            "semantic_binding=",
            "load_json",
            "resolve_stage_phase_artifact_dir",
            "write_run_index",
            "application_adapter",
            "assemble_aggregate_evidence_source_bundle",
        ):
            assert forbidden not in source, path.name
