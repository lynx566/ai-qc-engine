"""Evidence Source Preparation consumer bindings for clinical-trial documents."""

from __future__ import annotations

from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBinding,
    EvidenceSourcePreparationConsumerBindings,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)

from .evidence_source_preparation_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
)
from .filter_output_projection_installation import CLINICAL_SAFETY_SEMANTIC_MODULE_ID

CLINICAL_SAFETY_AGGREGATE_ROUTE_OUTPUT_KIND = "aggregate"

_INSTALLED_CLINICAL_SAFETY_AGGREGATE_EVIDENCE_CONSUMER_BINDING = (
    EvidenceSourcePreparationConsumerBinding(
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        required_route_output_kind=CLINICAL_SAFETY_AGGREGATE_ROUTE_OUTPUT_KIND,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        stage_executor=(
            INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
        ),
    )
)

INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS = (
    EvidenceSourcePreparationConsumerBindings(
        bindings={
            CLINICAL_SAFETY_SEMANTIC_MODULE_ID: (
                _INSTALLED_CLINICAL_SAFETY_AGGREGATE_EVIDENCE_CONSUMER_BINDING
            ),
        }
    )
)

__all__ = [
    "CLINICAL_SAFETY_AGGREGATE_ROUTE_OUTPUT_KIND",
    "INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS",
]
