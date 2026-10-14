"""Clinical-trial document Evidence Source Preparation plugin package."""

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
    CLINICAL_TRIAL_DOC_PLUGIN_ID,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.executor import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
    execute_clinical_trial_aggregate_evidence_source_preparation,
)

__all__ = [
    "AGGREGATE_EVIDENCE_FORM_ID",
    "CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR",
    "CLINICAL_TRIAL_DOC_PLUGIN_ID",
    "execute_clinical_trial_aggregate_evidence_source_preparation",
]
