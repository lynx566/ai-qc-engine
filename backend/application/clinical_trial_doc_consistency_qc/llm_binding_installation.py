"""Installed LLM execution dependency bindings for clinical-trial Document Consistency QC."""

from __future__ import annotations

from types import MappingProxyType

from llm.execution_configs import (
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID,
    resolve_llm_execution_config,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT,
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_LLM_SLOT,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.dependencies import (
    OVERVIEW_SEMANTIC_LLM_SLOT,
)

INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS: MappingProxyType[str, str] = (
    MappingProxyType(
        {
            OVERVIEW_SEMANTIC_LLM_SLOT: (
                CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
            ),
            CLINICAL_SAFETY_AGGREGATE_LLM_SLOT: (
                CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID
            ),
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT: (
                CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID
            ),
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT: (
                CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID
            ),
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT: (
                CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID
            ),
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT: (
                CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID
            ),
        }
    )
)


def validate_llm_dependency_bindings(
    *,
    llm_dependency_bindings: MappingProxyType[str, str] | dict[str, str],
) -> None:
    """Validate installed dependency-slot bindings reference known execution configs."""
    for slot_id, config_id in llm_dependency_bindings.items():
        if not isinstance(slot_id, str) or not slot_id.strip():
            raise ValueError("llm dependency slot IDs must be non-empty strings")
        if not isinstance(config_id, str) or not config_id.strip():
            raise ValueError(
                f"llm execution config ID for slot {slot_id!r} must be a non-empty string"
            )
        resolve_llm_execution_config(config_id)


validate_llm_dependency_bindings(
    llm_dependency_bindings=INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS,
)


__all__ = [
    "CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_LLM_SLOT",
    "CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_ASSESSMENT_SECOND_PASS_LLM_SLOT",
    "CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT",
    "CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_VERIFICATION_LLM_SLOT",
    "CLINICAL_SAFETY_AGGREGATE_LLM_SLOT",
    "INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS",
    "validate_llm_dependency_bindings",
]
