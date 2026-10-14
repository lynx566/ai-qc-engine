"""Application read model for internal Document Consistency QC comparison results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InternalResultEvidenceRef:
    """Canonical evidence reference for document navigation."""

    block_id: str
    sentence_id: str
    slot_id: str
    doc_id: str
    sentence_alias: str


@dataclass(frozen=True, slots=True)
class InternalResultFinding:
    """One final finding projected for Result consumption."""

    finding_id: str
    label: str
    conclusion: str
    comparison_mode_id: str
    evidence_refs: tuple[InternalResultEvidenceRef, ...]
    source_finding_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InternalResultScopeResult:
    """Comparison annotation for one canonical document scope."""

    slot_id: str
    doc_id: str
    scope_id: str
    heading_path: tuple[str, ...]
    outline_heading_block_id: str
    semantic_module_id: str
    execution_status: str
    has_successful_check: bool


@dataclass(frozen=True, slots=True)
class DocumentConsistencyQcInternalResultReadModel:
    """Persisted internal comparison result projection for one completed flow."""

    flow_id: str
    flow_run_id: str
    capability_id: str
    flow_status: str
    comparison_run_status: str | None
    finalization_status: str
    fallback_comparison_modes: tuple[str, ...]
    findings: tuple[InternalResultFinding, ...]
    scope_results: tuple[InternalResultScopeResult, ...]


__all__ = [
    "DocumentConsistencyQcInternalResultReadModel",
    "InternalResultEvidenceRef",
    "InternalResultFinding",
    "InternalResultScopeResult",
]
