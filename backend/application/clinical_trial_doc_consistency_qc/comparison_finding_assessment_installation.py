"""Comparison Finding Assessment installation for clinical-trial Document Consistency QC."""

from __future__ import annotations

from types import MappingProxyType

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentCapabilityDeclaration,
    ResolvedClinicalSafetyComparisonFindingAssessmentConfig,
)

from .capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS,
)


def resolve_clinical_safety_comparison_finding_assessment_config(
    declaration: ComparisonFindingAssessmentCapabilityDeclaration,
) -> ResolvedClinicalSafetyComparisonFindingAssessmentConfig:
    """Validate and freeze one capability declaration into resolved planning config."""

    if not isinstance(
        declaration,
        ComparisonFindingAssessmentCapabilityDeclaration,
    ):
        raise TypeError(
            "declaration must be a ComparisonFindingAssessmentCapabilityDeclaration"
        )

    return ResolvedClinicalSafetyComparisonFindingAssessmentConfig(
        enabled_comparison_modes=tuple(declaration.enabled_comparison_modes),
        participant_role_ids=tuple(declaration.participant_role_ids),
        ib_to_dsur=declaration.ib_to_dsur,
        dsur_to_ib=declaration.dsur_to_ib,
    )


def build_installed_clinical_trial_doc_comparison_finding_assessment_configs() -> (
    MappingProxyType[str, ResolvedClinicalSafetyComparisonFindingAssessmentConfig]
):
    """Resolve all installed capability declarations into frozen planning configs."""

    resolved: dict[str, ResolvedClinicalSafetyComparisonFindingAssessmentConfig] = {}
    for (
        capability_id,
        declaration,
    ) in INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS.items():
        resolved[capability_id] = (
            resolve_clinical_safety_comparison_finding_assessment_config(declaration)
        )
    return MappingProxyType(resolved)


def resolve_installed_comparison_finding_assessment_config(
    capability_id: str,
) -> ResolvedClinicalSafetyComparisonFindingAssessmentConfig:
    """Resolve one installed capability into frozen planning config."""

    if not isinstance(capability_id, str) or not capability_id.strip():
        raise ValueError("capability_id must be a non-empty string")
    normalized = capability_id.strip()
    declaration = (
        INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS.get(
            normalized
        )
    )
    if declaration is None:
        raise KeyError(f"unknown capability_id: {normalized!r}")
    return resolve_clinical_safety_comparison_finding_assessment_config(declaration)


INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_CONFIGS = (
    build_installed_clinical_trial_doc_comparison_finding_assessment_configs()
)

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_CONFIGS",
    "build_installed_clinical_trial_doc_comparison_finding_assessment_configs",
    "resolve_clinical_safety_comparison_finding_assessment_config",
    "resolve_installed_comparison_finding_assessment_config",
]
