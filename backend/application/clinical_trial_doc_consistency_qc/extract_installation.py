"""Installed Extract configuration for clinical-trial Document Consistency QC."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from execution_flow.document_consistency_qc import DocumentConsistencyQcCapabilityConfig

from .capabilities import INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES

INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID = "docx"


def resolve_installed_extract_config_id() -> str:
    """Return the installed extract_config_id for this application."""
    return INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID


def build_installed_clinical_trial_doc_extract_bindings(
    capabilities: Mapping[str, DocumentConsistencyQcCapabilityConfig],
    *,
    extract_config_id: str = INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID,
) -> MappingProxyType[tuple[str, str], str]:
    """Project the installed Extract config onto every installed capability slot."""

    bindings: dict[tuple[str, str], str] = {}
    for capability in capabilities.values():
        for slot in capability.slots:
            bindings[(capability.capability_id, slot.slot_id)] = extract_config_id
    return MappingProxyType(bindings)


INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS = (
    build_installed_clinical_trial_doc_extract_bindings(
        INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
    )
)


__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS",
    "INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_CONFIG_ID",
    "build_installed_clinical_trial_doc_extract_bindings",
    "resolve_installed_extract_config_id",
]
