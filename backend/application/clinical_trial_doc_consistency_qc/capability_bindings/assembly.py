"""Mechanical assembly of per-capability slot-local bindings into flat maps."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TypeVar

from operations.prepare_analysis.contracts import PrepareAnalysisConfigId
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentCapabilityDeclaration,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation import (
    ComparisonFindingConsolidationCapabilityDeclaration,
)

from . import dsur_updated_ib, internal_csr, internal_dsur, internal_ib

_CAPABILITY_BINDING_MODULES = (
    internal_dsur,
    internal_ib,
    internal_csr,
    dsur_updated_ib,
)

_T = TypeVar("_T")


def _prefix_and_merge(
    target: dict[tuple[str, str], _T],
    capability_id: str,
    slot_bindings: Mapping[str, _T],
) -> None:
    for slot_id, value in slot_bindings.items():
        key = (capability_id, slot_id)
        if key in target:
            raise ValueError(
                f"duplicate capability slot binding key during assembly: {key!r}"
            )
        target[key] = value


def assemble_capability_slot_bindings() -> tuple[
    MappingProxyType[tuple[str, str], PrepareAnalysisConfigId],
    MappingProxyType[tuple[str, str], tuple[str, ...]],
    MappingProxyType[tuple[str, str], str],
    MappingProxyType[tuple[str, str], str],
]:
    """Prefix capability_id onto slot-local maps and merge into flat bindings."""

    prepare: dict[tuple[str, str], PrepareAnalysisConfigId] = {}
    filter_jobs: dict[tuple[str, str], tuple[str, ...]] = {}
    expected_document_type: dict[tuple[str, str], str] = {}
    manual_default_filter_jobs: dict[tuple[str, str], str] = {}

    for module in _CAPABILITY_BINDING_MODULES:
        capability_id = module.CAPABILITY_ID
        _prefix_and_merge(prepare, capability_id, module.PREPARE_ANALYSIS_BINDINGS)
        _prefix_and_merge(filter_jobs, capability_id, module.FILTER_JOB_BINDINGS)
        _prefix_and_merge(
            expected_document_type,
            capability_id,
            module.EXPECTED_DOCUMENT_TYPE_BINDINGS,
        )
        slot_bindings = getattr(
            module,
            "CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS",
            {},
        )
        _prefix_and_merge(
            manual_default_filter_jobs,
            capability_id,
            slot_bindings,
        )

    return (
        MappingProxyType(prepare),
        MappingProxyType(filter_jobs),
        MappingProxyType(expected_document_type),
        MappingProxyType(manual_default_filter_jobs),
    )


def assemble_comparison_finding_assessment_declarations() -> MappingProxyType[
    str,
    ComparisonFindingAssessmentCapabilityDeclaration,
]:
    """Collect per-capability Comparison Finding Assessment declarations."""

    declarations: dict[str, ComparisonFindingAssessmentCapabilityDeclaration] = {}
    for module in _CAPABILITY_BINDING_MODULES:
        capability_id = module.CAPABILITY_ID
        declaration = module.COMPARISON_FINDING_ASSESSMENT_DECLARATION
        if not isinstance(
            declaration,
            ComparisonFindingAssessmentCapabilityDeclaration,
        ):
            raise TypeError(
                f"{capability_id} COMPARISON_FINDING_ASSESSMENT_DECLARATION must be a "
                "ComparisonFindingAssessmentCapabilityDeclaration"
            )
        if capability_id in declarations:
            raise ValueError(
                f"duplicate Comparison Finding Assessment declaration: {capability_id!r}"
            )
        expected_role_ids = tuple(module.FILTER_JOB_BINDINGS)
        if tuple(declaration.participant_role_ids) != expected_role_ids:
            raise ValueError(
                f"{capability_id} participant_role_ids must match FILTER_JOB_BINDINGS "
                f"slot keys: {declaration.participant_role_ids!r} != {expected_role_ids!r}"
            )
        declarations[capability_id] = declaration
    return MappingProxyType(declarations)


def assemble_comparison_finding_consolidation_declarations() -> MappingProxyType[
    str,
    ComparisonFindingConsolidationCapabilityDeclaration,
]:
    """Collect per-capability Comparison Finding Consolidation declarations."""

    declarations: dict[str, ComparisonFindingConsolidationCapabilityDeclaration] = {}
    for module in _CAPABILITY_BINDING_MODULES:
        capability_id = module.CAPABILITY_ID
        declaration = module.COMPARISON_FINDING_CONSOLIDATION_DECLARATION
        if not isinstance(
            declaration,
            ComparisonFindingConsolidationCapabilityDeclaration,
        ):
            raise TypeError(
                f"{capability_id} COMPARISON_FINDING_CONSOLIDATION_DECLARATION "
                "must be a ComparisonFindingConsolidationCapabilityDeclaration"
            )
        if capability_id in declarations:
            raise ValueError(
                "duplicate Comparison Finding Consolidation declaration: "
                f"{capability_id!r}"
            )
        declarations[capability_id] = declaration
    return MappingProxyType(declarations)


(
    INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS,
) = assemble_capability_slot_bindings()

INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS = (
    assemble_comparison_finding_assessment_declarations()
)
INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_CONSOLIDATION_DECLARATIONS = (
    assemble_comparison_finding_consolidation_declarations()
)

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS",
    "INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS",
    "INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_CONSOLIDATION_DECLARATIONS",
    "INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS",
    "INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS",
    "INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS",
    "assemble_capability_slot_bindings",
    "assemble_comparison_finding_assessment_declarations",
    "assemble_comparison_finding_consolidation_declarations",
]
