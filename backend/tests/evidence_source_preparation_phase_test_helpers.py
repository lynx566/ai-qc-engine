"""Shared helpers for aggregate ESP phase runtime tests."""

from __future__ import annotations

from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_phase_harness_installation import (
    resolve_installed_aggregate_evidence_phase_harness_dependencies,
)


def installed_prepare_phase_kwargs(
    *,
    semantic_module_id: str | None = None,
) -> dict[str, object]:
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies(
        semantic_module_id=semantic_module_id,
    )
    return {
        "run_prepare_phase": phase_dependencies.run_prepare_phase,
        "prepare_semantic": phase_dependencies.semantic_binding.prepare,
    }


def installed_assess_phase_kwargs(
    *,
    semantic_module_id: str | None = None,
) -> dict[str, object]:
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies(
        semantic_module_id=semantic_module_id,
    )
    return {"run_assess_phase": phase_dependencies.run_assess_phase}


def installed_eligibility_phase_kwargs(
    *,
    semantic_module_id: str | None = None,
) -> dict[str, object]:
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies(
        semantic_module_id=semantic_module_id,
    )
    return {
        "run_evaluate_eligibility_phase": phase_dependencies.run_evaluate_eligibility_phase,
        "build_heading_scope_eligibility_entries": (
            phase_dependencies.semantic_binding.build_heading_scope_eligibility_entries
        ),
    }


def installed_assemble_phase_kwargs(
    *,
    semantic_module_id: str | None = None,
) -> dict[str, object]:
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies(
        semantic_module_id=semantic_module_id,
    )
    return {"run_assemble_phase": phase_dependencies.run_assemble_phase}
