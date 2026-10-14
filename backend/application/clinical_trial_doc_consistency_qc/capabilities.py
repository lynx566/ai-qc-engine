"""Installed clinical-trial capability catalogue for Document Consistency QC."""

from __future__ import annotations

from types import MappingProxyType

from capability.clinical_trial_doc_consistency_qc import (
    DSUR_UPDATED_IB_CONSISTENCY_QC,
    INTERNAL_CSR_CONSISTENCY_QC,
    INTERNAL_DSUR_CONSISTENCY_QC,
    INTERNAL_IB_CONSISTENCY_QC,
)
from execution_flow.document_consistency_qc import (
    DocumentConsistencyQcCapabilityConfig,
)

_INSTALLED_CAPABILITIES = (
    INTERNAL_DSUR_CONSISTENCY_QC,
    INTERNAL_IB_CONSISTENCY_QC,
    INTERNAL_CSR_CONSISTENCY_QC,
    DSUR_UPDATED_IB_CONSISTENCY_QC,
)
_INSTALLED_CAPABILITY_IDS = tuple(
    config.capability_id for config in _INSTALLED_CAPABILITIES
)
if len(set(_INSTALLED_CAPABILITY_IDS)) != len(_INSTALLED_CAPABILITY_IDS):
    raise ValueError("installed clinical consistency-QC capability IDs must be unique")

INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES: MappingProxyType[
    str, DocumentConsistencyQcCapabilityConfig
] = MappingProxyType(
    {config.capability_id: config for config in _INSTALLED_CAPABILITIES}
)

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES",
]
