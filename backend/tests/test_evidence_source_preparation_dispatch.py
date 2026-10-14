"""Evidence Source Preparation execution-boundary tests."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from steps import evidence_source_preparation as step
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade import (
    run_aggregate_evidence_assess_heading_scopes,
)
from tests.test_assessment_input_compact import (
    _aggregate_unit,
    _compact_assessment_input_from_units,
)


def _source(relative: str) -> str:
    return (BACKEND_ROOT / relative).read_text(encoding="utf-8")


def _imports(relative: str) -> set[str]:
    tree = ast.parse(_source(relative))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def _canonical_run_block() -> str:
    return _source("steps/evidence_source_preparation.py")


def test_step_surface_is_canonical_unified_execution() -> None:
    assert callable(step.run_evidence_source_preparation)
    for retired_generic_name in ("run_prepare", "run_assess", "run_eligibility", "run_assemble"):
        assert not hasattr(step, retired_generic_name)
    for retired_helper in (
        "run_prepare_aggregate_evidence_assessment_input",
        "run_assess_aggregate_evidence_heading_scopes",
        "run_evaluate_aggregate_evidence_heading_scope_eligibility",
        "run_assemble_aggregate_evidence_source_bundle",
    ):
        assert not hasattr(step, retired_helper)


def test_canonical_entry_is_pure_memory() -> None:
    block = _canonical_run_block()
    assert "Path" not in block
    assert "load_json" not in block
    assert "save_json" not in block
    assert "run_id" not in block


def test_canonical_entry_does_not_reference_aggregate_types() -> None:
    block = _canonical_run_block()
    for forbidden in (
        "AggregateEvidenceExecutionInput",
        "AggregateEvidenceExecution",
        "CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING",
        "plugins.clinical_trial_doc",
    ):
        assert forbidden not in block


def test_application_adapter_assess_phase_validates_and_returns_execution() -> None:
    assessment_input, assessment_runtime_context = _compact_assessment_input_from_units(
        [
            _aggregate_unit(
                unit_id="TU0001",
                heading_path=["Safety"],
                context_block_ids=["C0010"],
            )
        ]
    )
    execution = run_aggregate_evidence_assess_heading_scopes(
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
        assessment_profile_name=(
            "clinical_safety_aggregate_heading_scope_assessment_zh"
        ),
        llm_mode="mock",
    )

    assert execution.scope_assessments["artifact_type"] == "scope_assessments"
    assert execution.scope_assessment_count == 1


@pytest.mark.parametrize(
    "runner",
    [
        "scripts/stage_runners/evidence_source_preparation/aggregate_evidence/prepare_runner.py",
        "scripts/stage_runners/evidence_source_preparation/aggregate_evidence/assess_runner.py",
        "scripts/stage_runners/evidence_source_preparation/aggregate_evidence/eligibility_runner.py",
        "scripts/stage_runners/evidence_source_preparation/aggregate_evidence/assemble_runner.py",
    ],
)
def test_runner_is_only_cli_adapter(runner: str) -> None:
    source = _source(runner)
    assert "parse_args" in source
    assert "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.operations" in source
    assert "resolve_installed_aggregate_evidence_phase_harness_dependencies" in source
    for forbidden in (
        "CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING",
        "semantic_binding=",
        "load_json",
        "resolve_stage_phase_artifact_dir",
        "write_run_index",
        "snapshot_git_provenance_before_run",
        "phase_facade",
    ):
        assert forbidden not in source


def test_runtime_and_step_do_not_import_private_aggregate_implementation() -> None:
    targets = [
        "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/prepare.py",
        "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assess.py",
        "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/eligibility.py",
        "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assemble.py",
        "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/persistence.py",
        "steps/evidence_source_preparation.py",
    ]
    for target in targets:
        for module in _imports(target):
            if not module or not module.startswith(
                "plugins.clinical_trial_doc.evidence_source_preparation"
            ):
                continue
            if module.endswith(
                (
                    ".input_types",
                    ".execution_types",
                    ".evidence_form_identity",
                )
            ):
                continue
            if module == "plugins.clinical_trial_doc.evidence_source_preparation":
                continue
            raise AssertionError(
                f"{target} imports private aggregate implementation {module!r}"
            )
