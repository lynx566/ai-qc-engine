"""Installed aggregate ESP phase harness dependency resolution tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_phase_harness_installation import (
    HARNESS_AGGREGATE_EVIDENCE_ASSESS_PHASE,
    HARNESS_AGGREGATE_EVIDENCE_ASSEMBLE_PHASE,
    HARNESS_AGGREGATE_EVIDENCE_ELIGIBILITY_PHASE,
    HARNESS_AGGREGATE_EVIDENCE_PREPARE_PHASE,
    resolve_installed_aggregate_evidence_harness_semantic_module_id,
    resolve_installed_aggregate_evidence_phase_harness_dependencies,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade import (
    run_aggregate_evidence_assess_heading_scopes,
    run_aggregate_evidence_evaluate_heading_scope_eligibility,
    run_aggregate_evidence_prepare,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assemble_aggregate_evidence_source_bundle import (
    assemble_aggregate_evidence_source_bundle,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
)


def test_resolver_defaults_to_single_installed_semantic_module() -> None:
    assert (
        resolve_installed_aggregate_evidence_harness_semantic_module_id()
        == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    )


def test_resolver_returns_installed_clinical_safety_binding() -> None:
    dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies(
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
    )
    assert dependencies.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert dependencies.semantic_binding is CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING
    assert dependencies.semantic_binding.prepare is (
        CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING.prepare
    )
    assert (
        dependencies.semantic_binding.build_heading_scope_eligibility_entries
        is CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING.build_heading_scope_eligibility_entries
    )


def test_unknown_semantic_module_fails_through_harness_resolver() -> None:
    with pytest.raises(ValueError, match="not an installed aggregate evidence semantic module"):
        resolve_installed_aggregate_evidence_phase_harness_dependencies(
            semantic_module_id="clinical_efficacy",
        )


def test_harness_phase_callables_reference_stable_plugin_apis() -> None:
    dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies(
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
    )
    assert dependencies.run_prepare_phase is run_aggregate_evidence_prepare
    assert dependencies.run_assess_phase is run_aggregate_evidence_assess_heading_scopes
    assert (
        dependencies.run_evaluate_eligibility_phase
        is run_aggregate_evidence_evaluate_heading_scope_eligibility
    )
    assert dependencies.run_assemble_phase is assemble_aggregate_evidence_source_bundle


def test_harness_phase_constants_reference_stable_plugin_apis() -> None:
    assert HARNESS_AGGREGATE_EVIDENCE_PREPARE_PHASE is run_aggregate_evidence_prepare
    assert HARNESS_AGGREGATE_EVIDENCE_ASSESS_PHASE is run_aggregate_evidence_assess_heading_scopes
    assert (
        HARNESS_AGGREGATE_EVIDENCE_ELIGIBILITY_PHASE
        is run_aggregate_evidence_evaluate_heading_scope_eligibility
    )
    assert HARNESS_AGGREGATE_EVIDENCE_ASSEMBLE_PHASE is assemble_aggregate_evidence_source_bundle
