"""Next boundary: translate HTTP selections into canonical application resume."""

from __future__ import annotations

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc import (
    resume_installed_clinical_trial_document_consistency_qc,
)
from application.document_consistency_qc.create_flow_result import (
    build_document_consistency_qc_create_flow_result,
)
from application.document_consistency_qc.resume_request import (
    DocumentConsistencyQcResumeRequest,
)
from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig
from bridge.candidate_scope.errors import (
    CandidateScopeBridgeError,
    CandidateScopeRuntimeError,
    CandidateScopeValidationError,
    map_flow_resume_error,
)
from bridge.candidate_scope.schemas import (
    CandidateScopeNextRequest,
    CandidateScopeNextResponse,
    CandidateScopeSlotDecision,
)
from execution_flow.document_consistency_qc.contracts import (
    FilterJobCandidateScopeSelection,
)
from execution_flow.document_consistency_qc.flow_loader import FlowResumeError


def _candidate_scope_selections(
    slot_decision: CandidateScopeSlotDecision,
) -> tuple[FilterJobCandidateScopeSelection, ...]:
    return tuple(
        FilterJobCandidateScopeSelection(
            filter_job_id=item.filter_job_id,
            anchor_block_ids=tuple(item.anchor_block_ids),
        )
        for item in slot_decision.candidate_scope
    )


def _candidate_scope_decisions_by_slot(
    request: CandidateScopeNextRequest,
) -> dict[str, tuple[FilterJobCandidateScopeSelection, ...]]:
    return {
        slot_decision.slot_id: _candidate_scope_selections(slot_decision)
        for slot_decision in request.slot_decisions
    }


def run_candidate_scope_next_request(
    request: CandidateScopeNextRequest,
    *,
    config: BridgeRuntimeConfig,
) -> CandidateScopeNextResponse:
    composition = build_installed_document_consistency_qc_application_composition()
    resume_request = DocumentConsistencyQcResumeRequest(
        flow_run_id=request.flow_run_id,
        candidate_scope_decisions_by_slot=_candidate_scope_decisions_by_slot(request),
        project_root=config.workspace_root,
        participant_privacy_paths=config.participant_privacy_paths,
    )

    try:
        application_result = resume_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=resume_request,
            projection_runtime_dependencies=config.projection_runtime_dependencies,
            evidence_source_preparation_execution_dependencies=(
                config.evidence_source_preparation_execution_dependencies
            ),
            evidence_comparison_execution_dependencies=(
                config.evidence_comparison_execution_dependencies
            ),
        )
    except FlowResumeError as exc:
        raise map_flow_resume_error(exc) from exc
    except ValueError as exc:
        raise CandidateScopeValidationError(str(exc)) from exc
    except CandidateScopeBridgeError:
        raise
    except Exception as exc:
        raise CandidateScopeRuntimeError(str(exc)) from exc

    flow_result = build_document_consistency_qc_create_flow_result(application_result)
    return CandidateScopeNextResponse(
        status="ready",
        flow_id=flow_result.flow_id,
        flow_run_id=flow_result.flow_run_id,
        flow_status=flow_result.flow_status,
        paused_at_candidate_scope=flow_result.paused_at_candidate_scope,
        paused_slot_ids=list(flow_result.paused_slot_ids),
        completed=flow_result.completed,
    )


__all__ = ["run_candidate_scope_next_request"]
