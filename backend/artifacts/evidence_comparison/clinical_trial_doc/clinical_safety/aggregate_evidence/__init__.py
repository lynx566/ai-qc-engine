"""Formal clinical-safety aggregate Evidence Comparison artifact contracts."""

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_comparison_evidence import (
    AGGREGATE_COMPARISON_EVIDENCE_ARTIFACT_TYPE,
    AGGREGATE_COMPARISON_EVIDENCE_FILENAME,
    AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION,
    build_aggregate_comparison_evidence,
    validate_aggregate_comparison_evidence,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    COMPARISON_ALIAS_DIGIT_WIDTH,
    COMPARISON_ALIAS_MAX_INDEX,
    SENTENCE_ALIAS_PATTERN,
    format_scope_alias,
    format_sentence_alias,
    format_unit_alias,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.final_findings import (
    FINAL_FINDINGS_ARTIFACT_TYPE,
    FINAL_FINDINGS_COMPARISON_MODE_ORDER,
    FINAL_FINDINGS_FILENAME,
    FINAL_FINDINGS_SCHEMA_VERSION,
    build_final_findings,
    validate_final_findings,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDINGS_ARTIFACT_TYPE,
    FINDINGS_FILENAME,
    FINDINGS_SCHEMA_VERSION,
    build_findings,
    validate_findings,
)

__all__ = [
    "AGGREGATE_COMPARISON_EVIDENCE_ARTIFACT_TYPE",
    "AGGREGATE_COMPARISON_EVIDENCE_FILENAME",
    "AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION",
    "COMPARISON_ALIAS_DIGIT_WIDTH",
    "COMPARISON_ALIAS_MAX_INDEX",
    "FINAL_FINDINGS_ARTIFACT_TYPE",
    "FINAL_FINDINGS_COMPARISON_MODE_ORDER",
    "FINAL_FINDINGS_FILENAME",
    "FINAL_FINDINGS_SCHEMA_VERSION",
    "FINDINGS_ARTIFACT_TYPE",
    "FINDINGS_FILENAME",
    "FINDINGS_SCHEMA_VERSION",
    "SENTENCE_ALIAS_PATTERN",
    "build_aggregate_comparison_evidence",
    "build_final_findings",
    "build_findings",
    "format_scope_alias",
    "format_sentence_alias",
    "format_unit_alias",
    "validate_aggregate_comparison_evidence",
    "validate_final_findings",
    "validate_findings",
]
