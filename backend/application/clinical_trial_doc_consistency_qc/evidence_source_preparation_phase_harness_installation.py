"""Aggregate-evidence phase dev/debug harness installation for clinical-trial documents."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assemble_aggregate_evidence_source_bundle import (
    assemble_aggregate_evidence_source_bundle,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade import (
    run_aggregate_evidence_assess_heading_scopes,
    run_aggregate_evidence_evaluate_heading_scope_eligibility,
    run_aggregate_evidence_prepare,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.semantic_binding import (
    AggregateEvidenceSemanticBinding,
)

from .evidence_source_preparation_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SEMANTIC_BINDING,
)
from .filter_output_projection_installation import CLINICAL_SAFETY_SEMANTIC_MODULE_ID

HARNESS_AGGREGATE_EVIDENCE_SEMANTIC_BINDINGS: Mapping[str, AggregateEvidenceSemanticBinding] = (
    MappingProxyType(
        {
            CLINICAL_SAFETY_SEMANTIC_MODULE_ID: (
                INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SEMANTIC_BINDING
            ),
        }
    )
)

HARNESS_AGGREGATE_EVIDENCE_PREPARE_PHASE = run_aggregate_evidence_prepare
HARNESS_AGGREGATE_EVIDENCE_ASSESS_PHASE = run_aggregate_evidence_assess_heading_scopes
HARNESS_AGGREGATE_EVIDENCE_ELIGIBILITY_PHASE = (
    run_aggregate_evidence_evaluate_heading_scope_eligibility
)
HARNESS_AGGREGATE_EVIDENCE_ASSEMBLE_PHASE = assemble_aggregate_evidence_source_bundle


@dataclass(frozen=True)
class AggregateEvidencePhaseHarnessDependencies:
    """Installed aggregate ESP phase-dev harness dependencies for one semantic module."""

    semantic_module_id: str
    semantic_binding: AggregateEvidenceSemanticBinding
    run_prepare_phase: Callable[..., Any]
    run_assess_phase: Callable[..., Any]
    run_evaluate_eligibility_phase: Callable[..., Any]
    run_assemble_phase: Callable[..., Any]


def resolve_installed_aggregate_evidence_harness_semantic_module_id(
    *,
    semantic_module_id: str | None = None,
) -> str:
    """Resolve an installed semantic module id for phase harness runs."""
    if semantic_module_id is not None:
        resolved = semantic_module_id.strip()
        if not resolved:
            raise ValueError("semantic_module_id must be a non-empty string when provided")
        return resolved
    installed_ids = tuple(HARNESS_AGGREGATE_EVIDENCE_SEMANTIC_BINDINGS)
    if len(installed_ids) == 1:
        return installed_ids[0]
    raise ValueError(
        "semantic_module_id is required when multiple aggregate semantic modules are installed"
    )


def resolve_installed_aggregate_evidence_harness_semantic_binding(
    *,
    semantic_module_id: str | None = None,
) -> AggregateEvidenceSemanticBinding:
    """Resolve the installed aggregate semantic binding for standalone phase harness runs."""
    resolved_id = resolve_installed_aggregate_evidence_harness_semantic_module_id(
        semantic_module_id=semantic_module_id,
    )
    binding = HARNESS_AGGREGATE_EVIDENCE_SEMANTIC_BINDINGS.get(resolved_id)
    if binding is None:
        raise ValueError(
            f"semantic_module_id {resolved_id!r} is not an installed aggregate "
            "evidence semantic module"
        )
    return binding


def resolve_installed_aggregate_evidence_phase_harness_dependencies(
    *,
    semantic_module_id: str | None = None,
) -> AggregateEvidencePhaseHarnessDependencies:
    """Resolve installed aggregate phase-dev harness dependencies for dev runners."""
    resolved_id = resolve_installed_aggregate_evidence_harness_semantic_module_id(
        semantic_module_id=semantic_module_id,
    )
    return AggregateEvidencePhaseHarnessDependencies(
        semantic_module_id=resolved_id,
        semantic_binding=resolve_installed_aggregate_evidence_harness_semantic_binding(
            semantic_module_id=resolved_id,
        ),
        run_prepare_phase=HARNESS_AGGREGATE_EVIDENCE_PREPARE_PHASE,
        run_assess_phase=HARNESS_AGGREGATE_EVIDENCE_ASSESS_PHASE,
        run_evaluate_eligibility_phase=HARNESS_AGGREGATE_EVIDENCE_ELIGIBILITY_PHASE,
        run_assemble_phase=HARNESS_AGGREGATE_EVIDENCE_ASSEMBLE_PHASE,
    )


__all__ = [
    "HARNESS_AGGREGATE_EVIDENCE_ASSEMBLE_PHASE",
    "HARNESS_AGGREGATE_EVIDENCE_ASSESS_PHASE",
    "HARNESS_AGGREGATE_EVIDENCE_ELIGIBILITY_PHASE",
    "HARNESS_AGGREGATE_EVIDENCE_PREPARE_PHASE",
    "HARNESS_AGGREGATE_EVIDENCE_SEMANTIC_BINDINGS",
    "AggregateEvidencePhaseHarnessDependencies",
    "resolve_installed_aggregate_evidence_harness_semantic_binding",
    "resolve_installed_aggregate_evidence_harness_semantic_module_id",
    "resolve_installed_aggregate_evidence_phase_harness_dependencies",
]
