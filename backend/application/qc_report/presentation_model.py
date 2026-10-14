"""Immutable renderer input; machine identities live in explicit metadata.

These are transient display values, not persisted report domain entities.
Renderers consume display fields and must not derive business semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IntegrityStatus = Literal["complete", "partial", "failed", "unavailable"]
ConfigurationMode = Literal["default", "adjusted", "unavailable"]
FindingLabel = Literal["fail", "need_review"]


@dataclass(frozen=True, slots=True)
class TaskMetadata:
    task_run_id: str
    task_id: str


@dataclass(frozen=True, slots=True)
class TaskPresentation:
    display_name: str
    created_at: str | None
    updated_at: str | None
    metadata: TaskMetadata


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    document_ref: str
    doc_id: str
    file_hash: str


@dataclass(frozen=True, slots=True)
class DocumentPresentation:
    original_file_name: str
    expected_document_type: str | None
    observed_document_type: str | None
    metadata: DocumentMetadata


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    report_id: str


@dataclass(frozen=True, slots=True)
class ReportHeader:
    title: str
    generated_at: str
    task: TaskPresentation
    documents: tuple[DocumentPresentation, ...]
    metadata: ReportMetadata


@dataclass(frozen=True, slots=True)
class IntegrityNotice:
    display: str
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IntegrityMetadata:
    finalization_status: str | None
    fallback_comparison_modes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FunctionDisplay:
    name: str
    description: str | None
    display_name: str


@dataclass(frozen=True, slots=True)
class ExecutionMetadata:
    outcome: str
    created_at: str | None
    completed_at: str | None


@dataclass(frozen=True, slots=True)
class ContentDomainMetadata:
    semantic_module_id: str


@dataclass(frozen=True, slots=True)
class ContentDomainPresentation:
    display_name: str
    integrity_status: IntegrityStatus
    integrity_notice: IntegrityNotice | None
    metadata: ContentDomainMetadata
    integrity_metadata: IntegrityMetadata


@dataclass(frozen=True, slots=True)
class ScopeItemMetadata:
    anchor_block_id: str
    doc_order_index: int


@dataclass(frozen=True, slots=True)
class ScopeItemPresentation:
    document: DocumentPresentation
    heading_path: tuple[str, ...]
    display: str
    metadata: ScopeItemMetadata


@dataclass(frozen=True, slots=True)
class ConfigurationSelectionMetadata:
    document_ref: str
    slot_id: str
    filter_job_id: str


@dataclass(frozen=True, slots=True)
class ConfigurationSelectionPresentation:
    document: DocumentPresentation
    mode: ConfigurationMode
    display: str
    automatic_scope_items: tuple[ScopeItemPresentation, ...]
    effective_scope_items: tuple[ScopeItemPresentation, ...]
    added_scope_items: tuple[ScopeItemPresentation, ...]
    removed_scope_items: tuple[ScopeItemPresentation, ...]
    metadata: ConfigurationSelectionMetadata


@dataclass(frozen=True, slots=True)
class ConfigurationSummary:
    mode: ConfigurationMode
    display: str
    automatic_scope_items: tuple[ScopeItemPresentation, ...]
    effective_scope_items: tuple[ScopeItemPresentation, ...]
    added_scope_items: tuple[ScopeItemPresentation, ...]
    removed_scope_items: tuple[ScopeItemPresentation, ...]


@dataclass(frozen=True, slots=True)
class ContributionMetadata:
    contribution_ref: str
    flow_id: str
    flow_run_id: str
    capability_id: str


@dataclass(frozen=True, slots=True)
class ContributionPresentation:
    function_display: FunctionDisplay
    content_domains: tuple[ContentDomainPresentation, ...]
    configuration_summary: ConfigurationSummary
    integrity_status: IntegrityStatus
    integrity_notice: IntegrityNotice | None
    execution: ExecutionMetadata
    metadata: ContributionMetadata
    integrity_metadata: IntegrityMetadata


@dataclass(frozen=True, slots=True)
class ScopeSummary:
    contributions: tuple[ContributionPresentation, ...]


@dataclass(frozen=True, slots=True)
class ConfigurationAppendix:
    function_display: FunctionDisplay
    availability: Literal["available", "unavailable"]
    persisted_decision_at: str | None
    selections: tuple[ConfigurationSelectionPresentation, ...]
    metadata: ContributionMetadata


@dataclass(frozen=True, slots=True)
class FindingCount:
    label: FindingLabel
    display_name: str
    count: int


@dataclass(frozen=True, slots=True)
class ResultSummary:
    finding_count: int
    finding_counts: tuple[FindingCount, ...]
    integrity_status: IntegrityStatus
    integrity_notice: IntegrityNotice | None


@dataclass(frozen=True, slots=True)
class ReviewDisplay:
    decision: Literal["pending", "confirmed", "ignored"]
    decision_display: str | None
    marked_display: str | None
    note: str | None
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class SourceAnchorMetadata:
    slot_id: str
    doc_id: str
    block_id: str
    sentence_id: str


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    contribution_ref: str
    anchor: SourceAnchorMetadata
    evidence_ref: str | None
    doc_order_index: int | None


@dataclass(frozen=True, slots=True)
class BlockContextPresentation:
    kind: str
    original_block_text: str | None


@dataclass(frozen=True, slots=True)
class TableContextPresentation:
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class SourcePresentation:
    document: DocumentPresentation
    heading_path: tuple[str, ...]
    location_display: str
    original_sentence_text: str
    block_context: BlockContextPresentation | None
    table_context: TableContextPresentation | None
    metadata: SourceMetadata


@dataclass(frozen=True, slots=True)
class AnnotationMetadata:
    annotation_ref: str
    annotation_id: str
    created_at: str
    updated_at: str
    related_finding_refs: tuple[str, ...]  # co-location, never authorship


@dataclass(frozen=True, slots=True)
class RevisionPresentation:
    selected_original_text: str
    replacement_text: str
    start_offset: int
    end_offset: int
    metadata: AnnotationMetadata


@dataclass(frozen=True, slots=True)
class CommentPresentation:
    selected_original_text: str
    content: str
    metadata: AnnotationMetadata


@dataclass(frozen=True, slots=True)
class SentenceReviewPresentation:
    revisions: tuple[RevisionPresentation, ...]
    comments: tuple[CommentPresentation, ...]
    revised_sentence_text: str | None
    revision_conflict: bool
    revision_conflict_notice: str | None


@dataclass(frozen=True, slots=True)
class EvidencePresentation:
    source: SourcePresentation
    revisions: tuple[RevisionPresentation, ...]
    comments: tuple[CommentPresentation, ...]
    revised_sentence_text: str | None
    revision_conflict: bool
    revision_conflict_notice: str | None


@dataclass(frozen=True, slots=True)
class FindingMetadata:
    finding_ref: str
    finding_id: str
    contribution_ref: str
    semantic_module_id: str
    comparison_mode_id: str | None
    source_finding_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FindingSection:
    sequence_number: int
    sequence_display: str
    label: FindingLabel
    label_display: str
    conclusion: str
    review_display: ReviewDisplay | None
    evidence_items: tuple[EvidencePresentation, ...]
    metadata: FindingMetadata


@dataclass(frozen=True, slots=True)
class IndependentReviewRecordPresentation:
    source: SourcePresentation
    revision: RevisionPresentation | None
    comment: CommentPresentation | None
    revised_sentence_text: str | None
    revision_conflict: bool
    revision_conflict_notice: str | None


@dataclass(frozen=True, slots=True)
class QcReportPresentation:
    report_header: ReportHeader
    scope_summary: ScopeSummary
    result_summary: ResultSummary
    finding_sections: tuple[FindingSection, ...]
    independent_review_records: tuple[IndependentReviewRecordPresentation, ...]
    configuration_appendix: tuple[ConfigurationAppendix, ...]
    report_notes: tuple[str, ...]
