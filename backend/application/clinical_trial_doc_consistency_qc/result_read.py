"""Persisted read boundary for internal Document Consistency QC comparison results."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    validate_flow_run_summary,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    validate_aggregate_comparison_evidence,
    validate_final_findings,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    validate_aggregate_evidence_source_bundle,
)
from execution_flow.document_consistency_qc.flow_loader import (
    FlowResumeError,
    resolve_flow_run_output_dir,
)
from runtime.io import load_json

from application.clinical_trial_doc_consistency_qc.result_read_model import (
    DocumentConsistencyQcInternalResultReadModel,
    InternalResultEvidenceRef,
    InternalResultFinding,
    InternalResultScopeResult,
)
from application.clinical_trial_doc_consistency_qc.result_readiness import (
    INTERNAL_RESULT_CAPABILITY_IDS,
    resolve_result_prerequisites,
)
from application.document_consistency_qc.document_read import (
    resolve_slot_extract_bundle,
)

INTERNAL_CAPABILITY_IDS = INTERNAL_RESULT_CAPABILITY_IDS
INTERNAL_COMPARISON_MODES = frozenset(
    {
        "scope_local",
        "focus_comparison",
    }
)
CLINICAL_SAFETY_SEMANTIC_MODULE_ID = "clinical_safety"
_EXTRACT_HEADING_COLLECTIONS = (
    "front_matter_blocks",
    "content_blocks",
    "table_blocks",
)


class ResultReadError(Exception):
    """Base error for application result read."""


class ResultReadNotFoundError(ResultReadError):
    """Flow or required persisted artifact could not be located."""


class ResultReadValidationError(ResultReadError):
    """Persisted result data failed validation or could not be resolved."""


class ResultReadUnsupportedCapabilityError(ResultReadValidationError):
    """Capability is outside the internal Result read model scope."""


class ResultReadUnsupportedComparisonModeError(ResultReadValidationError):
    """Comparison mode is outside the internal Result read model scope."""


@dataclass(frozen=True, slots=True)
class _CanonicalScope:
    scope_id: str
    heading_path: tuple[str, ...]
    scope_order: int
    scope_alias: str
    outline_heading_block_id: str


@dataclass(frozen=True, slots=True)
class _ParticipantContext:
    role_id: str
    slot_id: str
    doc_id: str
    semantic_module_id: str


@dataclass(frozen=True, slots=True)
class _PlannedScopeCheck:
    frozen_job_index: int
    comparison_mode_id: str
    owner_scope_alias: str


def load_document_consistency_qc_result(
    *,
    project_root: Path,
    flow_run_id: str,
) -> DocumentConsistencyQcInternalResultReadModel:
    """Load and project one persisted internal comparison result read model."""

    try:
        output_dir = resolve_flow_run_output_dir(
            project_root=project_root,
            flow_run_id=flow_run_id,
        )
    except FlowResumeError as exc:
        raise ResultReadNotFoundError(str(exc)) from exc

    summary_path = output_dir / "flow_run_summary.json"
    if not summary_path.is_file():
        raise ResultReadNotFoundError(
            f"flow_run_summary not found for flow_run_id={flow_run_id!r}"
        )

    summary = load_json(summary_path)
    validate_flow_run_summary(summary)
    if summary["flow_run_id"] != flow_run_id:
        raise ResultReadValidationError(
            "flow_run_summary.flow_run_id does not match request"
        )

    capability_id = str(summary["capability_id"])
    if capability_id not in INTERNAL_CAPABILITY_IDS:
        raise ResultReadUnsupportedCapabilityError(
            f"capability_id {capability_id!r} is not supported by the internal "
            "Result read model"
        )

    flow_status = str(summary["status"])
    if flow_status == FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE:
        raise ResultReadValidationError(
            f"flow {flow_run_id!r} is paused_at_candidate_scope; result is not available"
        )

    evidence_comparison = summary.get("evidence_comparison")
    if not isinstance(evidence_comparison, Mapping):
        raise ResultReadValidationError(
            f"flow {flow_run_id!r} is missing evidence_comparison provenance"
        )
    if not evidence_comparison.get("stage_executed"):
        raise ResultReadValidationError(
            f"flow {flow_run_id!r} has not executed Evidence Comparison"
        )

    try:
        prerequisites = resolve_result_prerequisites(
            project_root=project_root,
            flow_run_id=flow_run_id,
            summary=summary,
        )
    except (TypeError, ValueError) as exc:
        raise ResultReadValidationError(str(exc)) from exc
    if prerequisites is None:
        raise ResultReadNotFoundError(
            f"Result prerequisites are missing for flow_run_id={flow_run_id!r}"
        )
    final_findings_path = prerequisites.final_findings_path
    run_summary_path = prerequisites.run_summary_path
    aggregate_comparison_evidence_path = (
        prerequisites.aggregate_comparison_evidence_path
    )
    plan_path = prerequisites.plan_path

    final_findings_payload = load_json(final_findings_path)
    validate_final_findings(final_findings_payload)
    aggregate_comparison_evidence = load_json(aggregate_comparison_evidence_path)
    validate_aggregate_comparison_evidence(aggregate_comparison_evidence)
    comparison_run_summary = load_json(run_summary_path)
    plan_payload = load_json(plan_path)

    participants = _load_participant_contexts(
        summary=summary,
        evidence_comparison=evidence_comparison,
        aggregate_comparison_evidence=aggregate_comparison_evidence,
    )
    if len(participants) != 1:
        raise ResultReadValidationError(
            "internal Result read model requires exactly one comparison participant"
        )
    participant = participants[0]

    esp_path = _resolve_participant_esp_path(
        evidence_comparison=evidence_comparison,
        participant=participant,
    )
    esp_bundle = load_json(esp_path)
    validate_aggregate_evidence_source_bundle(esp_bundle)

    extract_bundle = resolve_slot_extract_bundle(
        project_root=project_root,
        flow_run_id=flow_run_id,
        slot_id=participant.slot_id,
    )
    heading_block_index = _build_heading_block_index(extract_bundle)
    scope_by_alias = _build_scope_index(aggregate_comparison_evidence)
    esp_scope_meta = _build_esp_scope_meta(esp_bundle)
    sentence_to_block = _build_sentence_to_block_index(esp_bundle)
    sentence_alias_index = _build_sentence_alias_index(
        aggregate_comparison_evidence=aggregate_comparison_evidence,
        participant=participant,
    )

    planned_checks = _load_planned_scope_checks(plan_payload)
    run_jobs_by_index = _index_run_summary_jobs(comparison_run_summary)

    scope_check_statuses: dict[str, list[str]] = defaultdict(list)

    for planned_check in planned_checks:
        canonical_scope = _resolve_canonical_scope(
            owner_scope_alias=planned_check.owner_scope_alias,
            scope_by_alias=scope_by_alias,
            esp_scope_meta=esp_scope_meta,
            heading_block_index=heading_block_index,
        )
        run_job = run_jobs_by_index.get(planned_check.frozen_job_index)
        *_, job_status = _resolve_job_execution(
            run_job=run_job,
            frozen_job_index=planned_check.frozen_job_index,
        )
        scope_check_statuses[canonical_scope.scope_id].append(job_status)

    findings = tuple(
        _project_finding(
            finding=finding,
            participant=participant,
            sentence_alias_index=sentence_alias_index,
            sentence_to_block=sentence_to_block,
        )
        for finding in final_findings_payload["findings"]
    )

    scope_results = _assemble_scope_results(
        participant=participant,
        scope_check_statuses=scope_check_statuses,
        scope_by_alias=scope_by_alias,
        esp_scope_meta=esp_scope_meta,
        heading_block_index=heading_block_index,
    )

    return DocumentConsistencyQcInternalResultReadModel(
        flow_id=str(summary["flow_id"]),
        flow_run_id=flow_run_id,
        capability_id=capability_id,
        flow_status=flow_status,
        comparison_run_status=_optional_str(evidence_comparison.get("run_status")),
        finalization_status=str(final_findings_payload["finalization_status"]),
        fallback_comparison_modes=tuple(
            str(mode) for mode in final_findings_payload["fallback_comparison_modes"]
        ),
        findings=findings,
        scope_results=scope_results,
    )


def internal_result_read_model_to_mapping(
    result: DocumentConsistencyQcInternalResultReadModel,
) -> dict[str, object]:
    """Serialize one internal Result read model for transport layers."""

    return {
        "flow_id": result.flow_id,
        "flow_run_id": result.flow_run_id,
        "capability_id": result.capability_id,
        "flow_status": result.flow_status,
        "comparison_run_status": result.comparison_run_status,
        "finalization_status": result.finalization_status,
        "fallback_comparison_modes": list(result.fallback_comparison_modes),
        "findings": [_finding_to_mapping(finding) for finding in result.findings],
        "scope_results": [
            _scope_result_to_mapping(scope_result)
            for scope_result in result.scope_results
        ],
    }


def _scope_result_to_mapping(
    scope_result: InternalResultScopeResult,
) -> dict[str, object]:
    return {
        "slot_id": scope_result.slot_id,
        "doc_id": scope_result.doc_id,
        "scope_id": scope_result.scope_id,
        "heading_path": list(scope_result.heading_path),
        "outline_heading_block_id": scope_result.outline_heading_block_id,
        "semantic_module_id": scope_result.semantic_module_id,
        "execution_status": scope_result.execution_status,
        "has_successful_check": scope_result.has_successful_check,
    }


def _finding_to_mapping(finding: InternalResultFinding) -> dict[str, object]:
    return {
        "finding_id": finding.finding_id,
        "label": finding.label,
        "conclusion": finding.conclusion,
        "comparison_mode_id": finding.comparison_mode_id,
        "evidence_refs": [
            _evidence_ref_to_mapping(evidence_ref)
            for evidence_ref in finding.evidence_refs
        ],
    }


def _evidence_ref_to_mapping(
    evidence_ref: InternalResultEvidenceRef,
) -> dict[str, object]:
    return {
        "block_id": evidence_ref.block_id,
        "sentence_id": evidence_ref.sentence_id,
        "slot_id": evidence_ref.slot_id,
        "doc_id": evidence_ref.doc_id,
        "sentence_alias": evidence_ref.sentence_alias,
    }


def _require_existing_path(value: Any, *, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ResultReadValidationError(f"{field} must be a non-empty string")
    path = Path(value.strip())
    if not path.is_file() and not path.is_dir():
        raise ResultReadNotFoundError(f"{field} does not exist: {path.as_posix()}")
    return path


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ResultReadValidationError("expected non-empty string")
    return value.strip()


def _load_participant_contexts(
    *,
    summary: Mapping[str, Any],
    evidence_comparison: Mapping[str, Any],
    aggregate_comparison_evidence: Mapping[str, Any],
) -> tuple[_ParticipantContext, ...]:
    slot_doc_ids: dict[str, str] = {}
    slots = summary.get("slots")
    if not isinstance(slots, list):
        raise ResultReadValidationError("flow_run_summary.slots must be an array")
    for slot in slots:
        if not isinstance(slot, Mapping):
            continue
        slot_id = slot.get("slot_id")
        doc_id = slot.get("doc_id")
        if isinstance(slot_id, str) and slot_id.strip() and isinstance(doc_id, str):
            slot_doc_ids[slot_id.strip()] = doc_id.strip()

    ace_roles: dict[str, str] = {}
    for participant in aggregate_comparison_evidence.get("participants") or []:
        if not isinstance(participant, Mapping):
            raise ResultReadValidationError("ACE participant must be an object")
        role_id = _require_non_empty_str(participant.get("role_id"), field="role_id")
        ace_roles[role_id] = _require_non_empty_str(
            participant.get("doc_id"), field="doc_id"
        )

    contexts: list[_ParticipantContext] = []
    participants = evidence_comparison.get("participants")
    if not isinstance(participants, list) or not participants:
        raise ResultReadValidationError(
            "evidence_comparison.participants must be a non-empty array"
        )
    for participant in participants:
        if not isinstance(participant, Mapping):
            raise ResultReadValidationError("participant provenance must be an object")
        role_id = _require_non_empty_str(participant.get("role_id"), field="role_id")
        slot_id = _require_non_empty_str(participant.get("slot_id"), field="slot_id")
        semantic_module_id = _require_non_empty_str(
            participant.get("semantic_module_id"),
            field="semantic_module_id",
        )
        doc_id = slot_doc_ids.get(slot_id) or ace_roles.get(role_id)
        if doc_id is None:
            raise ResultReadValidationError(
                f"unable to resolve doc_id for participant role_id={role_id!r}"
            )
        contexts.append(
            _ParticipantContext(
                role_id=role_id,
                slot_id=slot_id,
                doc_id=doc_id,
                semantic_module_id=semantic_module_id,
            )
        )
    return tuple(contexts)


def _resolve_participant_esp_path(
    *,
    evidence_comparison: Mapping[str, Any],
    participant: _ParticipantContext,
) -> Path:
    participants = evidence_comparison.get("participants")
    if not isinstance(participants, list):
        raise ResultReadValidationError(
            "evidence_comparison.participants must be an array"
        )
    for record in participants:
        if not isinstance(record, Mapping):
            continue
        if record.get("role_id") != participant.role_id:
            continue
        declared_output_path = record.get("declared_output_path")
        if (
            not isinstance(declared_output_path, str)
            or not declared_output_path.strip()
        ):
            break
        path = Path(declared_output_path.strip())
        if not path.is_file():
            raise ResultReadNotFoundError(
                f"ESP bundle is missing for role_id={participant.role_id!r}"
            )
        return path
    raise ResultReadValidationError(
        f"unable to resolve ESP bundle path for role_id={participant.role_id!r}"
    )


def _build_scope_index(
    aggregate_comparison_evidence: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    scope_by_alias: dict[str, Mapping[str, Any]] = {}
    for participant in aggregate_comparison_evidence["participants"]:
        if not isinstance(participant, Mapping):
            raise ResultReadValidationError("ACE participant must be an object")
        for scope in participant.get("scopes") or []:
            if not isinstance(scope, Mapping):
                raise ResultReadValidationError("ACE scope must be an object")
            scope_alias = _require_non_empty_str(
                scope.get("scope_alias"),
                field="scope_alias",
            )
            if scope_alias in scope_by_alias:
                raise ResultReadValidationError(
                    f"duplicate ACE scope_alias {scope_alias!r}"
                )
            scope_by_alias[scope_alias] = scope
    return scope_by_alias


def _build_esp_scope_meta(
    esp_bundle: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    for scope in esp_bundle.get("heading_scopes") or []:
        if not isinstance(scope, Mapping):
            raise ResultReadValidationError("ESP heading_scope must be an object")
        scope_id = _require_non_empty_str(scope.get("scope_id"), field="scope_id")
        heading_path = tuple(str(item) for item in (scope.get("heading_path") or []))
        scope_order = scope.get("scope_order")
        if not isinstance(scope_order, int):
            raise ResultReadValidationError(
                f"ESP scope {scope_id!r} is missing integer scope_order"
            )
        meta[scope_id] = {
            "scope_id": scope_id,
            "heading_path": heading_path,
            "scope_order": scope_order,
        }
    return meta


def _build_heading_block_index(
    extract_bundle: Mapping[str, Any],
) -> dict[tuple[str, ...], str]:
    index: dict[tuple[str, ...], str] = {}
    for collection in _EXTRACT_HEADING_COLLECTIONS:
        for block in extract_bundle.get(collection) or []:
            if not isinstance(block, Mapping):
                continue
            if block.get("kind") != "heading":
                continue
            heading_path = tuple(
                str(item) for item in (block.get("heading_path") or [])
            )
            block_id = _require_non_empty_str(block.get("block_id"), field="block_id")
            if heading_path in index:
                raise ResultReadValidationError(
                    f"duplicate extract heading_path {list(heading_path)!r}"
                )
            index[heading_path] = block_id
    return index


def _build_sentence_to_block_index(
    esp_bundle: Mapping[str, Any],
) -> dict[str, str]:
    index: dict[str, str] = {}
    for scope in esp_bundle.get("heading_scopes") or []:
        if not isinstance(scope, Mapping):
            continue
        for unit in scope.get("units") or []:
            if not isinstance(unit, Mapping):
                continue
            for sentence in unit.get("sentences") or []:
                if not isinstance(sentence, Mapping):
                    continue
                sentence_id = _require_non_empty_str(
                    sentence.get("sentence_id"),
                    field="sentence_id",
                )
                source_block_ids = sentence.get("source_block_ids")
                if not isinstance(source_block_ids, list) or not source_block_ids:
                    raise ResultReadValidationError(
                        f"sentence {sentence_id!r} is missing source_block_ids"
                    )
                block_ids = [
                    _require_non_empty_str(block_id, field="source_block_ids[]")
                    for block_id in source_block_ids
                ]
                if len(set(block_ids)) != 1:
                    raise ResultReadValidationError(
                        f"sentence {sentence_id!r} must resolve to exactly one block_id"
                    )
                if sentence_id in index and index[sentence_id] != block_ids[0]:
                    raise ResultReadValidationError(
                        f"duplicate sentence_id {sentence_id!r} with conflicting block_id"
                    )
                index[sentence_id] = block_ids[0]
    return index


def _build_sentence_alias_index(
    *,
    aggregate_comparison_evidence: Mapping[str, Any],
    participant: _ParticipantContext,
) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for ace_participant in aggregate_comparison_evidence["participants"]:
        if not isinstance(ace_participant, Mapping):
            continue
        role_id = _require_non_empty_str(
            ace_participant.get("role_id"),
            field="role_id",
        )
        for scope in ace_participant.get("scopes") or []:
            if not isinstance(scope, Mapping):
                continue
            scope_alias = _require_non_empty_str(
                scope.get("scope_alias"),
                field="scope_alias",
            )
            for unit in scope.get("units") or []:
                if not isinstance(unit, Mapping):
                    continue
                for sentence in unit.get("sentences") or []:
                    if not isinstance(sentence, Mapping):
                        continue
                    sentence_alias = _require_non_empty_str(
                        sentence.get("sentence_alias"),
                        field="sentence_alias",
                    )
                    sentence_id = _require_non_empty_str(
                        sentence.get("sentence_id"),
                        field="sentence_id",
                    )
                    if sentence_alias in index:
                        raise ResultReadValidationError(
                            f"duplicate sentence_alias {sentence_alias!r}"
                        )
                    index[sentence_alias] = {
                        "sentence_id": sentence_id,
                        "scope_alias": scope_alias,
                        "role_id": role_id,
                    }
    if not index:
        raise ResultReadValidationError(
            "aggregate_comparison_evidence has no sentences"
        )
    if participant.role_id not in {entry["role_id"] for entry in index.values()}:
        raise ResultReadValidationError(
            f"participant role_id {participant.role_id!r} is absent from ACE"
        )
    return index


def _load_planned_scope_checks(
    plan_payload: Mapping[str, Any],
) -> tuple[_PlannedScopeCheck, ...]:
    jobs = plan_payload.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ResultReadValidationError(
            "comparison plan jobs must be a non-empty array"
        )

    planned: list[_PlannedScopeCheck] = []
    for frozen_job_index, job in enumerate(jobs, start=1):
        if not isinstance(job, Mapping):
            raise ResultReadValidationError("comparison plan job must be an object")
        comparison_mode_id = _require_non_empty_str(
            job.get("comparison_mode_id"),
            field="comparison_mode_id",
        )
        if comparison_mode_id not in INTERNAL_COMPARISON_MODES:
            raise ResultReadUnsupportedComparisonModeError(
                f"comparison mode {comparison_mode_id!r} is not supported by the "
                "internal Result read model"
            )
        groups = job.get("groups")
        if not isinstance(groups, list) or not groups:
            raise ResultReadValidationError(
                "comparison plan groups must be a non-empty array"
            )
        normalized_groups = [
            {
                "group_role": _require_non_empty_str(
                    group.get("group_role"),
                    field="group_role",
                ),
                "scope_aliases": [
                    _require_non_empty_str(alias, field="scope_aliases[]")
                    for alias in (group.get("scope_aliases") or [])
                ],
            }
            for group in groups
            if isinstance(group, Mapping)
        ]
        owner_scope_alias = resolve_owner_scope_alias(
            comparison_mode_id=comparison_mode_id,
            comparison_groups=normalized_groups,
        )
        planned.append(
            _PlannedScopeCheck(
                frozen_job_index=frozen_job_index,
                comparison_mode_id=comparison_mode_id,
                owner_scope_alias=owner_scope_alias,
            )
        )
    return tuple(planned)


def resolve_owner_scope_alias(
    *,
    comparison_mode_id: str,
    comparison_groups: Sequence[Mapping[str, Any]],
) -> str:
    """Resolve the owner scope alias for one internal comparison job."""

    groups_by_role = {
        str(group["group_role"]): tuple(group["scope_aliases"])
        for group in comparison_groups
    }
    if comparison_mode_id == "scope_local":
        aliases = groups_by_role.get("scope")
        if aliases is None:
            raise ResultReadValidationError(
                "scope_local job is missing group_role='scope'"
            )
        if len(aliases) != 1:
            raise ResultReadValidationError(
                "scope_local job must have exactly one owner scope alias"
            )
        return aliases[0]
    if comparison_mode_id == "focus_comparison":
        aliases = groups_by_role.get("focus_scope")
        if aliases is None:
            raise ResultReadValidationError(
                "focus_comparison job is missing group_role='focus_scope'"
            )
        if len(aliases) != 1:
            raise ResultReadValidationError(
                "focus_comparison job must have exactly one focus scope alias"
            )
        return aliases[0]
    raise ResultReadUnsupportedComparisonModeError(
        f"unsupported comparison mode {comparison_mode_id!r}"
    )


def _index_run_summary_jobs(
    comparison_run_summary: Mapping[str, Any],
) -> dict[int, Mapping[str, Any]]:
    jobs = comparison_run_summary.get("jobs")
    if not isinstance(jobs, list):
        raise ResultReadValidationError("comparison run_summary.jobs must be an array")
    indexed: dict[int, Mapping[str, Any]] = {}
    for job in jobs:
        if not isinstance(job, Mapping):
            continue
        frozen_job_index = job.get("frozen_job_index")
        if not isinstance(frozen_job_index, int) or frozen_job_index < 1:
            raise ResultReadValidationError(
                "comparison run_summary job frozen_job_index must be a positive integer"
            )
        indexed[frozen_job_index] = job
    return indexed


def _resolve_job_execution(
    *,
    run_job: Mapping[str, Any] | None,
    frozen_job_index: int,
) -> tuple[str, str | None, str | None, str]:
    if run_job is None:
        raise ResultReadValidationError(
            f"missing run_summary job record for frozen_job_index={frozen_job_index}"
        )
    assessment = run_job.get("assessment")
    assessment_second_pass = run_job.get("assessment_second_pass")
    verification = run_job.get("verification")
    if not isinstance(assessment, Mapping):
        raise ResultReadValidationError(
            f"run_summary job {frozen_job_index} is missing assessment record"
        )
    assessment_status = _require_non_empty_str(
        assessment.get("status"),
        field="assessment.status",
    )
    assessment_second_pass_status = None
    if assessment_second_pass is not None:
        if not isinstance(assessment_second_pass, Mapping):
            raise ResultReadValidationError(
                f"run_summary job {frozen_job_index} assessment_second_pass must be "
                "an object"
            )
        assessment_second_pass_status = _require_non_empty_str(
            assessment_second_pass.get("status"),
            field="assessment_second_pass.status",
        )
    verification_status = None
    if verification is not None:
        if not isinstance(verification, Mapping):
            raise ResultReadValidationError(
                f"run_summary job {frozen_job_index} verification must be an object"
            )
        verification_status = _require_non_empty_str(
            verification.get("status"),
            field="verification.status",
        )
    normal_branch_succeeded = (
        assessment_status == "success"
        and assessment_second_pass_status is None
        and verification_status == "success"
    )
    second_pass_branch_succeeded = (
        assessment_status == "success"
        and assessment_second_pass_status == "success"
        and verification_status is None
    )
    job_status = (
        "success"
        if normal_branch_succeeded or second_pass_branch_succeeded
        else "failed"
    )
    return (
        assessment_status,
        assessment_second_pass_status,
        verification_status,
        job_status,
    )


def _resolve_canonical_scope(
    *,
    owner_scope_alias: str,
    scope_by_alias: Mapping[str, Mapping[str, Any]],
    esp_scope_meta: Mapping[str, Mapping[str, Any]],
    heading_block_index: Mapping[tuple[str, ...], str],
) -> _CanonicalScope:
    ace_scope = scope_by_alias.get(owner_scope_alias)
    if ace_scope is None:
        raise ResultReadValidationError(
            f"unknown owner scope_alias {owner_scope_alias!r}"
        )
    scope_id = _require_non_empty_str(ace_scope.get("scope_id"), field="scope_id")
    heading_path = tuple(str(item) for item in (ace_scope.get("heading_path") or []))
    esp_meta = esp_scope_meta.get(scope_id)
    if esp_meta is None:
        raise ResultReadValidationError(f"unknown ESP scope_id {scope_id!r}")
    if tuple(esp_meta["heading_path"]) != heading_path:
        raise ResultReadValidationError(
            f"ACE/ESP heading_path mismatch for scope_id {scope_id!r}"
        )
    outline_heading_block_id = heading_block_index.get(heading_path)
    if outline_heading_block_id is None:
        raise ResultReadValidationError(
            f"unable to resolve extract heading block for heading_path "
            f"{list(heading_path)!r}"
        )
    return _CanonicalScope(
        scope_id=scope_id,
        heading_path=heading_path,
        scope_order=int(esp_meta["scope_order"]),
        scope_alias=owner_scope_alias,
        outline_heading_block_id=outline_heading_block_id,
    )


def _project_finding(
    *,
    finding: Mapping[str, Any],
    participant: _ParticipantContext,
    sentence_alias_index: Mapping[str, Mapping[str, str]],
    sentence_to_block: Mapping[str, str],
) -> InternalResultFinding:
    finding_id = _require_non_empty_str(finding.get("finding_id"), field="finding_id")
    label = _require_non_empty_str(finding.get("label"), field="label")
    conclusion = _require_non_empty_str(finding.get("conclusion"), field="conclusion")
    comparison_mode_id = _require_non_empty_str(
        finding.get("comparison_mode_id"),
        field="comparison_mode_id",
    )

    aliases = finding.get("source_sentence_aliases")
    if not isinstance(aliases, list) or not aliases:
        raise ResultReadValidationError(
            f"finding {finding_id!r} is missing source_sentence_aliases"
        )

    evidence_refs: list[InternalResultEvidenceRef] = []
    for raw_alias in aliases:
        sentence_alias = _require_non_empty_str(
            raw_alias, field="source_sentence_aliases[]"
        )
        alias_entry = sentence_alias_index.get(sentence_alias)
        if alias_entry is None:
            raise ResultReadValidationError(
                f"unknown sentence_alias {sentence_alias!r} for finding {finding_id!r}"
            )
        if alias_entry["role_id"] != participant.role_id:
            raise ResultReadValidationError(
                f"sentence_alias {sentence_alias!r} does not belong to participant "
                f"{participant.role_id!r}"
            )
        sentence_id = alias_entry["sentence_id"]
        block_id = sentence_to_block.get(sentence_id)
        if block_id is None:
            raise ResultReadValidationError(
                f"unable to resolve block_id for sentence_id {sentence_id!r}"
            )
        evidence_refs.append(
            InternalResultEvidenceRef(
                block_id=block_id,
                sentence_id=sentence_id,
                slot_id=participant.slot_id,
                doc_id=participant.doc_id,
                sentence_alias=sentence_alias,
            )
        )

    return InternalResultFinding(
        finding_id=finding_id,
        label=label,
        conclusion=conclusion,
        comparison_mode_id=comparison_mode_id,
        evidence_refs=tuple(evidence_refs),
        source_finding_ids=tuple(
            _require_non_empty_str(source_finding_id, field="source_finding_ids[]")
            for source_finding_id in finding.get("source_finding_ids") or []
        ),
    )


def _assemble_scope_results(
    *,
    participant: _ParticipantContext,
    scope_check_statuses: Mapping[str, list[str]],
    scope_by_alias: Mapping[str, Mapping[str, Any]],
    esp_scope_meta: Mapping[str, Mapping[str, Any]],
    heading_block_index: Mapping[tuple[str, ...], str],
) -> tuple[InternalResultScopeResult, ...]:
    scope_ids = sorted(
        scope_check_statuses,
        key=lambda scope_id: (
            int(esp_scope_meta[scope_id]["scope_order"])
            if scope_id in esp_scope_meta
            else 10_000
        ),
    )
    results: list[InternalResultScopeResult] = []
    for scope_id in scope_ids:
        check_statuses = tuple(scope_check_statuses.get(scope_id, ()))
        if not check_statuses:
            continue
        owner_alias = next(
            alias
            for alias, ace_scope in scope_by_alias.items()
            if ace_scope.get("scope_id") == scope_id
        )
        canonical_scope = _resolve_canonical_scope(
            owner_scope_alias=owner_alias,
            scope_by_alias=scope_by_alias,
            esp_scope_meta=esp_scope_meta,
            heading_block_index=heading_block_index,
        )
        execution_status = _resolve_scope_execution_status(check_statuses)
        has_successful_check = any(status == "success" for status in check_statuses)
        results.append(
            InternalResultScopeResult(
                slot_id=participant.slot_id,
                doc_id=participant.doc_id,
                scope_id=canonical_scope.scope_id,
                heading_path=canonical_scope.heading_path,
                outline_heading_block_id=canonical_scope.outline_heading_block_id,
                semantic_module_id=participant.semantic_module_id,
                execution_status=execution_status,
                has_successful_check=has_successful_check,
            )
        )
    return tuple(results)


def _resolve_scope_execution_status(job_statuses: Sequence[str]) -> str:
    if not job_statuses:
        return "not_checked"
    success_count = sum(1 for status in job_statuses if status == "success")
    if success_count == len(job_statuses):
        return "complete"
    if success_count == 0:
        return "failed"
    return "partial"


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResultReadValidationError(f"{field} must be a non-empty string")
    return value.strip()


__all__ = [
    "INTERNAL_CAPABILITY_IDS",
    "INTERNAL_COMPARISON_MODES",
    "DocumentConsistencyQcInternalResultReadModel",
    "ResultReadError",
    "ResultReadNotFoundError",
    "ResultReadUnsupportedCapabilityError",
    "ResultReadUnsupportedComparisonModeError",
    "ResultReadValidationError",
    "internal_result_read_model_to_mapping",
    "load_document_consistency_qc_result",
    "resolve_owner_scope_alias",
]
