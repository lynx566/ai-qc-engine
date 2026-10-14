"""Clinical-safety Comparison Finding Verification plugin."""

from ..comparison_mode import ComparisonModeId
from .additional_finding_eligibility import (
    ADDITIONAL_FINDING_ELIGIBILITY_DEBUG_FILENAME,
    AdditionalFindingEligibilityResult,
    DroppedAdditionalFinding,
    filter_eligible_additional_findings,
    serialize_additional_finding_eligibility_audit,
)
from .execution import (
    ComparisonFindingVerificationExecution,
    ComparisonFindingVerificationJobExecution,
    execute_comparison_finding_verification_job,
    execute_comparison_finding_verification_jobs,
)
from .finding_reconciliation import (
    ComparisonFindingVerificationJobReconciliationResult,
    ComparisonFindingVerificationReconciliationResult,
    assemble_verified_findings_artifact,
    max_finding_sequence_number,
    reconcile_existing_findings,
    reconcile_verification_job,
)
from .findings_rendering import render_verification_findings_section
from .input_materialization import (
    VERIFICATION_FINDINGS_HEADING,
    VERIFICATION_SOURCE_SCOPE_HEADING,
    ComparisonFindingVerificationInput,
    assemble_verification_user_input_text,
    materialize_comparison_finding_verification_input,
    materialize_comparison_finding_verification_inputs,
)
from .job_pairing import (
    resolve_frozen_assessment_job,
    serialize_comparison_groups_for_provenance,
    verify_findings_job_matches_frozen_job,
)
from .prompts import (
    FormalComparisonFindingVerificationPromptId,
    FormalPromptDefinition,
    formal_prompt_dir,
    load_formal_prompt_definition,
    load_formal_prompt_template_messages,
    render_formal_comparison_finding_verification_messages,
    render_formal_prompt_messages,
    resolve_formal_comparison_finding_verification_prompt_id,
    resolve_formal_prompt_id,
)
from .response_validation import (
    ComparisonFindingVerificationAdditionalFinding,
    ComparisonFindingVerificationConfirmedEntry,
    ComparisonFindingVerificationEntry,
    ComparisonFindingVerificationRejectedEntry,
    ComparisonFindingVerificationRevisedEntry,
    ComparisonFindingVerificationValidatedResponse,
    parse_and_validate_comparison_finding_verification_response,
    parse_comparison_finding_verification_response,
    serialize_validated_response,
    validate_comparison_finding_verification_response_structure,
)

__all__ = [
    "ADDITIONAL_FINDING_ELIGIBILITY_DEBUG_FILENAME",
    "VERIFICATION_FINDINGS_HEADING",
    "VERIFICATION_SOURCE_SCOPE_HEADING",
    "AdditionalFindingEligibilityResult",
    "ComparisonFindingVerificationAdditionalFinding",
    "ComparisonFindingVerificationConfirmedEntry",
    "ComparisonFindingVerificationEntry",
    "ComparisonFindingVerificationRejectedEntry",
    "ComparisonFindingVerificationRevisedEntry",
    "ComparisonFindingVerificationInput",
    "ComparisonFindingVerificationJobReconciliationResult",
    "ComparisonFindingVerificationReconciliationResult",
    "ComparisonFindingVerificationExecution",
    "ComparisonFindingVerificationJobExecution",
    "ComparisonFindingVerificationValidatedResponse",
    "ComparisonModeId",
    "DroppedAdditionalFinding",
    "FormalComparisonFindingVerificationPromptId",
    "FormalPromptDefinition",
    "assemble_verification_user_input_text",
    "assemble_verified_findings_artifact",
    "execute_comparison_finding_verification_job",
    "execute_comparison_finding_verification_jobs",
    "formal_prompt_dir",
    "load_formal_prompt_definition",
    "load_formal_prompt_template_messages",
    "materialize_comparison_finding_verification_input",
    "materialize_comparison_finding_verification_inputs",
    "max_finding_sequence_number",
    "parse_and_validate_comparison_finding_verification_response",
    "parse_comparison_finding_verification_response",
    "reconcile_existing_findings",
    "reconcile_verification_job",
    "render_formal_comparison_finding_verification_messages",
    "render_formal_prompt_messages",
    "render_verification_findings_section",
    "resolve_formal_comparison_finding_verification_prompt_id",
    "resolve_formal_prompt_id",
    "resolve_frozen_assessment_job",
    "serialize_additional_finding_eligibility_audit",
    "serialize_comparison_groups_for_provenance",
    "serialize_validated_response",
    "validate_comparison_finding_verification_response_structure",
    "verify_findings_job_matches_frozen_job",
]
