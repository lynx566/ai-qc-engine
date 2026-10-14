"""Shared helpers for Document Consistency QC flow tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_FACADE_BUILDER,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS,
    INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
)
from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS,
)
from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_consumer_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS,
)
from application.clinical_trial_doc_consistency_qc.projected_source_route_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR,
)
from application.clinical_trial_doc_consistency_qc.route_semantic_module_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE,
)
from core.document.doc_identity import compute_file_hash
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
)
from llm.providers.base import LLMRawResult
from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBindings,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from operations.prepare_analysis.contracts import PrepareAnalysisConfigId
from plugins.clinical_trial_doc.doc_meta import (
    CLINICAL_TRIAL_DOC_META_PROFILE,
    build_clinical_trial_doc_meta_summary,
)
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies,
)

DEFAULT_SOURCE_LANGUAGE = "zh"


def admit_participant_source_binding(
    tmp_path: Path,
    source: Path,
) -> DocumentIntakeSourceBinding:
    """Construct an already-admitted source binding for low-level DCQC tests."""

    _ = tmp_path
    resolved = Path(source).resolve()
    return DocumentIntakeSourceBinding(
        file_hash=compute_file_hash(resolved),
        original_file_name=resolved.name,
        source_path=resolved,
    )


def admitted_source_bindings(
    uploads: dict[str, Path | str | DocumentIntakeSourceBinding],
) -> dict[str, DocumentIntakeSourceBinding]:
    """Normalize low-level DCQC test inputs to already-admitted bindings."""

    bindings: dict[str, DocumentIntakeSourceBinding] = {}
    for slot_id, source in uploads.items():
        if isinstance(source, DocumentIntakeSourceBinding):
            bindings[slot_id] = source
            continue
        resolved = Path(source).resolve()
        bindings[slot_id] = DocumentIntakeSourceBinding(
            file_hash=compute_file_hash(resolved),
            original_file_name=resolved.name,
            source_path=resolved,
        )
    return bindings


@dataclass(frozen=True)
class FlowOverviewFakeProvider:
    """Return minimal valid Overview assessments for integration flow tests."""

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        content = messages[-1]["content"]
        marker = "## Overview source\n\n"
        if marker not in content:
            raise ValueError("overview fake provider expected Overview source section")
        payload = json.loads(content.split(marker, 1)[1].strip())
        aliases: list[str] = []
        for scope in payload:
            if not isinstance(scope, dict):
                continue
            for item in scope.get("source_items", []):
                if isinstance(item, dict) and isinstance(item.get("source_id"), str):
                    aliases.append(item["source_id"])
        assessments = [
            {"source_id": alias, "content_modules": ["clinical_safety"]}
            for alias in aliases
        ]
        return LLMRawResult(
            provider_name="fake",
            model="fake-flow-overview",
            raw_text=json.dumps(
                {"sentence_assessments": assessments},
                ensure_ascii=False,
            ),
        )


def flow_projection_runtime_dependencies() -> FilterOutputProjectionRuntimeDependencies:
    return FilterOutputProjectionRuntimeDependencies(
        llm_provider=FlowOverviewFakeProvider(),
    )


def synthetic_operation_bindings_for_capability(
    capability_config: DocumentConsistencyQcCapabilityConfig,
    *,
    extract_config_id: str = "docx",
    prepare_analysis_config_id: PrepareAnalysisConfigId,
    filter_job_ids: tuple[str, ...] = (),
    per_slot_prepare_analysis_config_ids: dict[str, PrepareAnalysisConfigId]
    | None = None,
    per_slot_filter_job_ids: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, object]:
    """Build neutral synthetic operation bindings for a test capability."""

    extract_bindings: dict[tuple[str, str], str] = {}
    prepare_analysis_bindings: dict[tuple[str, str], PrepareAnalysisConfigId] = {}
    filter_job_bindings: dict[tuple[str, str], tuple[str, ...]] = {}
    for slot in capability_config.slots:
        key = (capability_config.capability_id, slot.slot_id)
        extract_bindings[key] = extract_config_id
        prepare_analysis_bindings[key] = (
            per_slot_prepare_analysis_config_ids[slot.slot_id]
            if per_slot_prepare_analysis_config_ids is not None
            else prepare_analysis_config_id
        )
        filter_job_bindings[key] = (
            per_slot_filter_job_ids[slot.slot_id]
            if per_slot_filter_job_ids is not None
            else filter_job_ids
        )
    return {
        "extract_bindings": extract_bindings,
        "prepare_analysis_bindings": prepare_analysis_bindings,
        "filter_job_bindings": filter_job_bindings,
    }


def installed_doc_meta_flow_dependencies() -> dict[str, object]:
    """Return installed clinical Doc Meta dependencies for flow integration tests."""

    return {
        "doc_meta_profile": CLINICAL_TRIAL_DOC_META_PROFILE,
        "doc_meta_summary_builder": build_clinical_trial_doc_meta_summary,
    }


def installed_filter_flow_dependencies() -> dict[str, object]:
    """Return installed clinical Filter variant data for flow integration tests."""

    return {
        "filter_job_variants": INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
    }


def installed_operation_binding_flow_dependencies() -> dict[str, object]:
    """Return installed clinical capability-slot operation bindings for flow tests."""

    return {
        "extract_bindings": INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS,
        "prepare_analysis_bindings": INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
        "filter_job_bindings": INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    }


def installed_projection_route_flow_dependencies() -> dict[str, object]:
    """Return installed clinical projection and Route dependencies for flow tests."""

    return {
        "filter_output_projection_jobs": (
            INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS
        ),
        "filter_output_projection_facade_builder": (
            INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_FACADE_BUILDER
        ),
        "route_semantic_module_sequence": (
            INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE
        ),
        "projected_source_route_executor": (
            INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR
        ),
    }


def empty_evidence_source_preparation_flow_dependencies() -> dict[str, object]:
    """Return neutral ESP bindings with no installed consumer executors."""

    return {
        "evidence_source_preparation_consumer_bindings": (
            EvidenceSourcePreparationConsumerBindings(bindings={})
        ),
        "evidence_source_preparation_execution_dependencies": (
            ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
                llm_mode="mock",
            )
        ),
    }


def installed_evidence_source_preparation_flow_dependencies() -> dict[str, object]:
    """Return installed clinical ESP consumer bindings and mock execution dependencies."""

    return {
        "evidence_source_preparation_consumer_bindings": (
            INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS
        ),
        "evidence_source_preparation_execution_dependencies": (
            ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
                llm_mode="mock",
            )
        ),
    }


def installed_clinical_flow_dependencies() -> dict[str, object]:
    """Return installed clinical Doc Meta, Filter, projection, Route, and binding deps."""

    return {
        **installed_doc_meta_flow_dependencies(),
        **installed_filter_flow_dependencies(),
        **installed_operation_binding_flow_dependencies(),
        **installed_projection_route_flow_dependencies(),
    }


def clinical_flow_invocation_kwargs() -> dict[str, object]:
    """Return canonical run-level source language and installed clinical Flow deps."""

    return {
        "source_language": DEFAULT_SOURCE_LANGUAGE,
        "projection_runtime_dependencies": flow_projection_runtime_dependencies(),
        **installed_clinical_flow_dependencies(),
        **empty_evidence_source_preparation_flow_dependencies(),
    }


def clinical_flow_resume_invocation_kwargs() -> dict[str, object]:
    """Return installed clinical Flow deps for Candidate Scope resume."""

    return {
        "projection_runtime_dependencies": flow_projection_runtime_dependencies(),
        **installed_projection_route_flow_dependencies(),
        **installed_evidence_source_preparation_flow_dependencies(),
        "candidate_scope_manual_default_filter_job_bindings": (
            INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS
        ),
    }


def single_filter_ib_safety_flow_capability() -> DocumentConsistencyQcCapabilityConfig:
    """Capability with one safety Filter job for ESP integration tests."""

    return DocumentConsistencyQcCapabilityConfig(
        capability_id="test_ib_safety_esp",
        slots=(DocumentConsistencyQcParticipantSlot(slot_id="source"),),
    )


def single_filter_ib_safety_flow_invocation(
    *,
    prepare_analysis_config_id: PrepareAnalysisConfigId,
) -> dict[str, object]:
    """Flow deps for ESP integration with one contributing Filter job."""

    capability = single_filter_ib_safety_flow_capability()
    return {
        **clinical_flow_invocation_kwargs(),
        **synthetic_operation_bindings_for_capability(
            capability,
            prepare_analysis_config_id=prepare_analysis_config_id,
            filter_job_ids=("ib_clinical_safety",),
        ),
        **installed_evidence_source_preparation_flow_dependencies(),
        "projection_runtime_dependencies": flow_projection_runtime_dependencies(),
    }
