"""Comparison Finding Consolidation installation for clinical-trial DCQC."""

from __future__ import annotations

from types import MappingProxyType

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation import (
    ComparisonFindingConsolidationCapabilityDeclaration,
    ResolvedComparisonFindingConsolidationConfig,
)

from .capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_CONSOLIDATION_DECLARATIONS,
)


def resolve_comparison_finding_consolidation_config(
    declaration: ComparisonFindingConsolidationCapabilityDeclaration,
) -> ResolvedComparisonFindingConsolidationConfig:
    if not isinstance(
        declaration,
        ComparisonFindingConsolidationCapabilityDeclaration,
    ):
        raise TypeError(
            "declaration must be a "
            "ComparisonFindingConsolidationCapabilityDeclaration"
        )
    return ResolvedComparisonFindingConsolidationConfig(
        enabled_comparison_modes=tuple(declaration.enabled_comparison_modes),
    )


def build_installed_comparison_finding_consolidation_configs() -> MappingProxyType[
    str,
    ResolvedComparisonFindingConsolidationConfig,
]:
    return MappingProxyType(
        {
            capability_id: resolve_comparison_finding_consolidation_config(
                declaration
            )
            for capability_id, declaration in (
                INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_CONSOLIDATION_DECLARATIONS.items()
            )
        }
    )


def resolve_installed_comparison_finding_consolidation_config(
    capability_id: str,
) -> ResolvedComparisonFindingConsolidationConfig:
    if not isinstance(capability_id, str) or not capability_id.strip():
        raise ValueError("capability_id must be a non-empty string")
    normalized = capability_id.strip()
    declaration = (
        INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_CONSOLIDATION_DECLARATIONS.get(
            normalized
        )
    )
    if declaration is None:
        raise KeyError(f"unknown capability_id: {normalized!r}")
    return resolve_comparison_finding_consolidation_config(declaration)


INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_CONSOLIDATION_CONFIGS = (
    build_installed_comparison_finding_consolidation_configs()
)

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_CONSOLIDATION_CONFIGS",
    "build_installed_comparison_finding_consolidation_configs",
    "resolve_comparison_finding_consolidation_config",
    "resolve_installed_comparison_finding_consolidation_config",
]
