"""Load Candidate Scope UI state from a canonical flow checkpoint."""

from __future__ import annotations

from pathlib import Path

from application.clinical_trial_doc_consistency_qc.candidate_scope_content_domain import (
    build_candidate_scope_content_domain_groups,
)
from application.clinical_trial_doc_consistency_qc.document_type_read import (
    read_slot_document_type_diagnostic,
)
from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS,
)
from application.clinical_trial_doc_consistency_qc.presentation_metadata import (
    presentation_for_dcqc_capability_id,
)
from application.clinical_trial_doc_consistency_qc.route_semantic_module_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE,
)
from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig
from bridge.candidate_scope.canonical_context import build_paused_slot_view_context
from bridge.candidate_scope.schemas import (
    CandidateScopeContentDomainGroupResponse,
    CandidateScopeStateResponse,
)
from bridge.candidate_scope.selection_view import build_candidate_scope_slot_state
from execution_flow.document_consistency_qc.flow_loader import (
    can_resume_candidate_scope,
    load_flow_run_execution,
    resolve_candidate_scope_readable_slots,
    resolve_flow_status,
)


def _capability_title(capability_id: str) -> str:
    presentation = presentation_for_dcqc_capability_id(capability_id)
    if presentation is None:
        return capability_id
    return presentation.display_name


def load_candidate_scope_state(
    *,
    config: BridgeRuntimeConfig,
    flow_run_id: str,
) -> CandidateScopeStateResponse:
    execution = load_flow_run_execution(
        project_root=config.workspace_root,
        flow_run_id=flow_run_id,
        require_doc_meta_bundle_reference=False,
    )
    can_resume = can_resume_candidate_scope(execution)
    readable_slots = resolve_candidate_scope_readable_slots(execution)
    slot_states = []
    for slot_provenance in readable_slots:
        decision_path: Path | None = None
        if not can_resume:
            raw_decision_path = str(
                slot_provenance.candidate_scope_decision_path or ""
            ).strip()
            if not raw_decision_path:
                raise ValueError(
                    f"slot {slot_provenance.slot_id!r} is missing "
                    "candidate_scope_decision_path"
                )
            decision_path = Path(raw_decision_path)
        slot_state = build_candidate_scope_slot_state(
            context=build_paused_slot_view_context(
                execution=execution,
                slot_provenance=slot_provenance,
            ),
            decision_path=decision_path,
        )
        slot_state.document_type_diagnostic = read_slot_document_type_diagnostic(
            capability_id=execution.capability_id,
            slot_id=slot_provenance.slot_id,
            doc_meta_bundle_path=slot_provenance.doc_meta_bundle_path,
        )
        slot_states.append(slot_state)
    capability_id = str(execution.capability_id or "").strip()
    content_domain_groups = build_candidate_scope_content_domain_groups(
        capability_id=capability_id,
        filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
        filter_output_projection_jobs=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS,
        route_semantic_module_sequence=(
            INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE
        ),
    )
    return CandidateScopeStateResponse(
        flow_id=execution.flow_id,
        flow_run_id=execution.flow_run_id,
        capability_id=capability_id,
        capability_title=_capability_title(capability_id),
        flow_status=resolve_flow_status(execution.slot_provenance),
        can_resume=can_resume,
        content_domain_groups=[
            CandidateScopeContentDomainGroupResponse(
                content_domain_id=group.content_domain_id,
                display_label=group.display_label,
                filter_job_ids=list(group.filter_job_ids),
            )
            for group in content_domain_groups
        ],
        slots=slot_states,
    )


__all__ = ["load_candidate_scope_state"]
