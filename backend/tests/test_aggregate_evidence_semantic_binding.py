"""Aggregate-evidence semantic binding injection and ownership tests."""

from __future__ import annotations

import ast
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade import (
    run_aggregate_evidence_evaluate_heading_scope_eligibility,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING,
    CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.heading_scope_eligibility_policy import (
    build_heading_scope_eligibility_entries as clinical_safety_build_entries,
    evaluate_heading_scope_eligibility as clinical_safety_evaluate_eligibility,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    prepare_aggregate_evidence_semantic_result,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.semantic_binding import (
    AggregateEvidencePrepareSemanticBinding,
    AggregateEvidenceSemanticBinding,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade import (
    run_aggregate_evidence_assess_heading_scopes,
    run_aggregate_evidence_evaluate_heading_scope_eligibility,
)
from tests.test_aggregate_prepare_preparation import _minimal_prepare_inputs
from tests.test_heading_scope_eligibility import _scope_assessments_payload


SYNTHETIC_PREPARE_BINDING = AggregateEvidencePrepareSemanticBinding(
    assessment_profile_ref="synthetic_aggregate_profile_ref",
    instructions="Synthetic aggregate heading-scope instructions.",
)

SYNTHETIC_ELIGIBILITY_CALLS: list[Sequence[Mapping[str, Any]]] = []


def _synthetic_build_entries(
    *,
    scope_assessments: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    SYNTHETIC_ELIGIBILITY_CALLS.append(scope_assessments)
    return [
        {
            "scope_id": str(scope.get("scope_id") or ""),
            "heading_path": list(scope.get("heading_path") or []),
            "source_unit_ids": list(scope.get("source_unit_ids") or []),
            "eligibility_decision": {
                "status": "auto_included",
                "reasons": [
                    "unit_form:aggregate",
                    "route_qc.route_mismatch:false",
                    "safety_role:primary_safety_finding",
                    "product_context_role:target_study_drug",
                ],
            },
        }
        for scope in scope_assessments
    ]


SYNTHETIC_SEMANTIC_BINDING = AggregateEvidenceSemanticBinding(
    prepare=SYNTHETIC_PREPARE_BINDING,
    build_heading_scope_eligibility_entries=_synthetic_build_entries,
)


def test_prepare_uses_injected_profile_and_instructions() -> None:
    inputs = _minimal_prepare_inputs()
    inputs["assessment_profile_ref"] = SYNTHETIC_PREPARE_BINDING.assessment_profile_ref
    inputs["instructions"] = SYNTHETIC_PREPARE_BINDING.instructions
    result = prepare_aggregate_evidence_semantic_result(**inputs)
    shared = result["shared_metadata"]
    assert shared["assessment_profile_ref"] == "synthetic_aggregate_profile_ref"
    assert shared["instructions"] == SYNTHETIC_PREPARE_BINDING.instructions


def test_default_clinical_safety_aggregate_package_exports_prepare_binding() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence import (
        CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
    )

    assert (
        CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING.prepare
        == CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING
    )
    assert (
        CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING.prepare.assessment_profile_ref
        == CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.assessment_profile_ref
    )


def test_executor_accepts_injected_semantic_binding() -> None:
    import inspect

    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.executor import (
        execute_clinical_trial_aggregate_evidence_source_preparation,
    )

    signature = inspect.signature(execute_clinical_trial_aggregate_evidence_source_preparation)
    assert "semantic_binding" in signature.parameters


def test_eligibility_adapter_uses_injected_policy() -> None:
    SYNTHETIC_ELIGIBILITY_CALLS.clear()
    scope_assessments = _scope_assessments_payload()
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import build_source_scope_assessments_ref

    source_ref = build_source_scope_assessments_ref(
        scope_assessments_payload=scope_assessments,
        scope_assessments_path=Path("runs/evidence_source_preparation/assess/test_run/doc_test/ib_clinical_safety_zh/aggregate_evidence/scope_assessments.json"),
        project_root=BACKEND_ROOT,
        run_id="test_run",
    )
    execution = run_aggregate_evidence_evaluate_heading_scope_eligibility(
        scope_assessments=scope_assessments,
        source_scope_assessments_ref=source_ref,
        build_heading_scope_eligibility_entries=_synthetic_build_entries,
    )
    assert SYNTHETIC_ELIGIBILITY_CALLS
    assert execution.auto_included_scope_count == 1
    entry = execution.heading_scope_eligibility["scope_eligibility_entries"][0]
    assert entry["eligibility_decision"]["status"] == "auto_included"


def test_clinical_safety_binding_preserves_eligibility_behavior() -> None:
    included = clinical_safety_evaluate_eligibility(
        scope_assessment={
            "scope_id": "HS0001",
            "unit_form": "aggregate",
            "safety_role": "primary_safety_finding",
            "product_context_role": "target_study_drug",
            "route_qc": {"route_mismatch": False},
        }
    )
    assert included["status"] == "auto_included"

    excluded = clinical_safety_evaluate_eligibility(
        scope_assessment={
            "scope_id": "HS0001",
            "unit_form": "aggregate",
            "safety_role": "safety_context",
            "product_context_role": "target_study_drug",
            "route_qc": {"route_mismatch": False},
        }
    )
    assert excluded["status"] == "excluded_non_primary_safety"


def test_injected_semantic_binding_eligibility_uses_clinical_safety_policy() -> None:
    scope_assessments = _scope_assessments_payload()
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import build_source_scope_assessments_ref

    source_ref = build_source_scope_assessments_ref(
        scope_assessments_payload=scope_assessments,
        scope_assessments_path=Path(
            "runs/evidence_source_preparation/assess/test_run/doc_test/ib_clinical_safety_zh/aggregate_evidence/scope_assessments.json"
        ),
        project_root=BACKEND_ROOT,
        run_id="test_run",
    )
    direct_entries = clinical_safety_build_entries(
        scope_assessments=scope_assessments["scope_assessments"],
    )
    execution = run_aggregate_evidence_evaluate_heading_scope_eligibility(
        scope_assessments=scope_assessments,
        source_scope_assessments_ref=source_ref,
        build_heading_scope_eligibility_entries=(
            CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING.build_heading_scope_eligibility_entries
        ),
    )
    assert (
        execution.heading_scope_eligibility["scope_eligibility_entries"]
        == direct_entries
    )


def test_phase_facade_has_no_heading_scope_eligibility_policy_import() -> None:
    adapter_path = (
        BACKEND_ROOT
        / "plugins"
        / "clinical_trial_doc"
        / "evidence_source_preparation"
        / "clinical_safety"
        / "aggregate_evidence"
        / "phase_facade.py"
    )
    tree = ast.parse(adapter_path.read_text(encoding="utf-8"), filename=str(adapter_path))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(
        name.endswith("heading_scope_eligibility_policy")
        for name in imported
    )


def test_preparation_module_has_no_clinical_safety_prompt_import() -> None:
    preparation_path = (
        BACKEND_ROOT
        / "plugins"
        / "clinical_trial_doc"
        / "evidence_source_preparation"
        / "clinical_safety"
        / "aggregate_evidence"
        / "preparation.py"
    )
    source = preparation_path.read_text(encoding="utf-8")
    assert "clinical_safety_aggregate_heading_scope_assessment_zh" not in source
