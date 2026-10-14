"""Evidence Comparison consumer bindings for clinical-trial documents."""

from __future__ import annotations

from operations.evidence_comparison.consumer_bindings import (
    EvidenceComparisonConsumerBinding,
    EvidenceComparisonConsumerBindings,
)
from operations.evidence_comparison.participants import (
    EvidenceComparisonParticipantRequirement,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentCapabilityDeclaration,
)

from .capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS,
)
from .evidence_comparison_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_STAGE_EXECUTOR,
)
from .filter_output_projection_installation import CLINICAL_SAFETY_SEMANTIC_MODULE_ID


def build_evidence_comparison_participant_requirements(
    *,
    declaration: ComparisonFindingAssessmentCapabilityDeclaration,
) -> tuple[EvidenceComparisonParticipantRequirement, ...]:
    """Build ordered participant requirements from one capability declaration."""

    return tuple(
        EvidenceComparisonParticipantRequirement(
            role_id=role_id,
            slot_id=role_id,
            semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        )
        for role_id in declaration.participant_role_ids
    )


def build_installed_clinical_trial_doc_evidence_comparison_consumer_bindings() -> (
    EvidenceComparisonConsumerBindings
):
    """Assemble per-capability Comparison consumer bindings from declarations."""

    bindings: dict[str, EvidenceComparisonConsumerBinding] = {}
    for (
        capability_id,
        declaration,
    ) in INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS.items():
        bindings[capability_id] = EvidenceComparisonConsumerBinding(
            capability_id=capability_id,
            participant_requirements=build_evidence_comparison_participant_requirements(
                declaration=declaration,
            ),
            stage_executor=INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_STAGE_EXECUTOR,
        )
    return EvidenceComparisonConsumerBindings(bindings=bindings)


def validate_evidence_comparison_consumer_installation(
    *,
    consumer_bindings: EvidenceComparisonConsumerBindings,
) -> None:
    """Validate installed Comparison bindings align with capability declarations."""

    declared_capability_ids = frozenset(
        INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS
    )
    installed_capability_ids = frozenset(consumer_bindings.bindings)
    if installed_capability_ids != declared_capability_ids:
        missing = declared_capability_ids - installed_capability_ids
        extra = installed_capability_ids - declared_capability_ids
        raise ValueError(
            "installed Evidence Comparison consumer bindings must match "
            f"Comparison Finding Assessment declarations: missing={sorted(missing)!r} "
            f"extra={sorted(extra)!r}"
        )

    for capability_id, binding in consumer_bindings.bindings.items():
        declaration = (
            INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS[
                capability_id
            ]
        )
        expected_roles = declaration.participant_role_ids
        actual_roles = tuple(
            requirement.role_id for requirement in binding.participant_requirements
        )
        if actual_roles != expected_roles:
            raise ValueError(
                f"{capability_id} participant requirements must follow declaration order: "
                f"{actual_roles!r} != {expected_roles!r}"
            )
        for requirement in binding.participant_requirements:
            if requirement.slot_id != requirement.role_id:
                raise ValueError(
                    f"{capability_id} participant slot_id must match role_id for "
                    f"current clinical-trial bindings: "
                    f"{requirement.slot_id!r} != {requirement.role_id!r}"
                )
            if requirement.semantic_module_id != CLINICAL_SAFETY_SEMANTIC_MODULE_ID:
                raise ValueError(
                    f"{capability_id} participant semantic_module_id must be "
                    f"{CLINICAL_SAFETY_SEMANTIC_MODULE_ID!r}; "
                    f"got {requirement.semantic_module_id!r}"
                )


INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS = (
    build_installed_clinical_trial_doc_evidence_comparison_consumer_bindings()
)

validate_evidence_comparison_consumer_installation(
    consumer_bindings=INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS,
)

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS",
    "build_evidence_comparison_participant_requirements",
    "build_installed_clinical_trial_doc_evidence_comparison_consumer_bindings",
    "validate_evidence_comparison_consumer_installation",
]
