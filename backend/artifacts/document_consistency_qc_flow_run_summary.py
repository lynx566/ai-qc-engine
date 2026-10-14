"""Formal document_consistency_qc flow_run_summary artifact contract.

Schema semantics (frozen):

- ``0.12.0`` (``PRE_ADMITTED_SOURCE_FLOW_RUN_SUMMARY_SCHEMA_VERSION``): legacy
  execution where the Flow participant ran Request File Intake; success slots
  may record ``intake_run_id``.
- ``0.13.0`` (``FLOW_RUN_SUMMARY_SCHEMA_VERSION``): admitted-source execution
  where Intake completed before Flow; success slots require ``original_file_name``
  and do not record Flow-owned ``intake_run_id``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core.document.doc_identity import validate_file_hash_format

FLOW_RUN_SUMMARY_FILENAME = "flow_run_summary.json"
FLOW_RUN_SUMMARY_ARTIFACT_TYPE = "document_consistency_qc_flow_run_summary"
FLOW_RUN_SUMMARY_SCHEMA_VERSION = "0.13.0"
LEGACY_FLOW_RUN_SUMMARY_SCHEMA_VERSION = "0.11.0"
PRE_ADMITTED_SOURCE_FLOW_RUN_SUMMARY_SCHEMA_VERSION = "0.12.0"
SUPPORTED_FLOW_RUN_SUMMARY_SCHEMA_VERSIONS = (
    LEGACY_FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    PRE_ADMITTED_SOURCE_FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    FLOW_RUN_SUMMARY_SCHEMA_VERSION,
)
DOCUMENT_CONSISTENCY_QC_FLOW_ID = "document_consistency_qc"

FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE = "paused_at_candidate_scope"
SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE = "paused_at_candidate_scope"

_FLOW_STATUS_VALUES = frozenset(
    {"success", "partial", "failed", FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE}
)
_SLOT_STATUS_VALUES = frozenset(
    {
        "not_started",
        "partial",
        "success",
        "failed",
        SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    }
)

_ROOT_KEYS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "flow_id",
        "flow_run_id",
        "capability_id",
        "source_language",
        "status",
        "created_at",
        "completed_at",
        "slots",
    }
)
_ROOT_OPTIONAL_KEYS = frozenset(
    {"evidence_comparison", "candidate_scope_decision_mode"}
)
_ROOT_ALLOWED_KEYS = _ROOT_KEYS | _ROOT_OPTIONAL_KEYS
# Existing 0.12.0/0.13.0 artifacts may carry this former Product backlink.
_HISTORICAL_ROOT_ALLOWED_KEYS = _ROOT_ALLOWED_KEYS | {"task_run_id"}
_SLOT_REQUIRED_KEYS = frozenset(
    {
        "slot_id",
        "status",
        "extract_config_id",
        "prepare_analysis_config_id",
    }
)
_SLOT_OPTIONAL_KEYS = frozenset(
    {
        "intake_run_id",
        "file_hash",
        "original_file_name",
        "doc_id",
        "extract_run_id",
        "prepare_analysis_run_id",
        "analysis_bundle_path",
        "block_manifest_path",
        "prepare_analysis_run_summary_path",
        "doc_meta_run_id",
        "doc_meta_output_dir",
        "doc_meta_bundle_path",
        "doc_meta_run_summary_path",
        "filter_job_ids",
        "filter_jobs",
        "projection_jobs",
        "route_semantic_modules",
        "candidate_scope_decision_path",
    }
)
_FILTER_JOB_REQUIRED_KEYS = frozenset(
    {
        "filter_job_id",
        "source_language",
        "zone_config_name",
        "zone_config_version",
        "filter_run_id",
        "output_dir",
        "zone_match_bundle_path",
        "coverage_bundle_path",
        "run_summary_path",
    }
)
_SLOT_ALLOWED_KEYS = _SLOT_REQUIRED_KEYS | _SLOT_OPTIONAL_KEYS

_PROJECTION_JOB_REQUIRED_KEYS = frozenset(
    {
        "filter_job_id",
        "projection_run_id",
        "output_dir",
        "projection_bundle_path",
        "run_summary_path",
        "projected_source_count",
        "semantic_outcome_count",
    }
)

_ROUTE_SEMANTIC_MODULE_OPTIONAL_KEYS = frozenset(
    {
        "route_run_id",
        "output_dir",
        "routing_manifest_path",
        "run_summary_path",
        "evidence_source_preparation_invoked",
        "evidence_source_preparation_run_id",
        "evidence_source_preparation_stage_executor_id",
        "evidence_source_preparation_declared_output_path",
        "evidence_source_preparation_run_summary_path",
    }
)

_ROUTE_SEMANTIC_MODULE_REQUIRED_KEYS = frozenset(
    {
        "semantic_module_id",
        "selected_projected_source_count",
        "route_invoked",
        "evidence_source_preparation_invoked",
    }
)

_EVIDENCE_COMPARISON_HANDOFF_STATUS_VALUES = frozenset(
    {"unbound", "incomplete", "ready"}
)
_EVIDENCE_COMPARISON_RUN_STATUS_VALUES = frozenset(
    {"success", "partial_failure", "failed"}
)
_EVIDENCE_COMPARISON_REQUIRED_KEYS = frozenset(
    {
        "capability_id",
        "handoff_status",
        "stage_executed",
    }
)
_EVIDENCE_COMPARISON_STAGE_EXECUTED_OPTIONAL_KEYS = frozenset(
    {
        "stage_executor_id",
        "run_id",
        "output_dir",
        "run_status",
        "run_summary_path",
        "declared_output_path",
        "participants",
    }
)
_EVIDENCE_COMPARISON_PARTICIPANT_REQUIRED_KEYS = frozenset(
    {
        "role_id",
        "slot_id",
        "semantic_module_id",
        "declared_output_path",
    }
)


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _validate_filter_job_record(job: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(job, dict):
        raise ValueError(f"{label} must be an object")
    extra = set(job) - _FILTER_JOB_REQUIRED_KEYS
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")
    missing = _FILTER_JOB_REQUIRED_KEYS - set(job)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")
    return {
        key: _require_str(job[key], field=f"{label}.{key}")
        for key in _FILTER_JOB_REQUIRED_KEYS
    }


def _validate_projection_job_record(job: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(job, dict):
        raise ValueError(f"{label} must be an object")
    extra = set(job) - _PROJECTION_JOB_REQUIRED_KEYS
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")
    missing = _PROJECTION_JOB_REQUIRED_KEYS - set(job)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")
    record = {
        key: _require_str(job[key], field=f"{label}.{key}")
        for key in (
            "filter_job_id",
            "projection_run_id",
            "output_dir",
            "projection_bundle_path",
            "run_summary_path",
        )
    }
    for key in ("projected_source_count", "semantic_outcome_count"):
        value = job[key]
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{label}.{key} must be a non-negative integer")
        record[key] = value
    return record


def _validate_route_semantic_module_record(
    module: Any, *, label: str
) -> dict[str, Any]:
    if not isinstance(module, dict):
        raise ValueError(f"{label} must be an object")
    allowed = (
        _ROUTE_SEMANTIC_MODULE_REQUIRED_KEYS | _ROUTE_SEMANTIC_MODULE_OPTIONAL_KEYS
    )
    extra = set(module) - allowed
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")
    missing = _ROUTE_SEMANTIC_MODULE_REQUIRED_KEYS - set(module)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")

    route_invoked = module["route_invoked"]
    if not isinstance(route_invoked, bool):
        raise ValueError(f"{label}.route_invoked must be a boolean")

    esp_invoked = module["evidence_source_preparation_invoked"]
    if not isinstance(esp_invoked, bool):
        raise ValueError(
            f"{label}.evidence_source_preparation_invoked must be a boolean"
        )

    selected_count = module["selected_projected_source_count"]
    if not isinstance(selected_count, int) or selected_count < 0:
        raise ValueError(
            f"{label}.selected_projected_source_count must be a non-negative integer"
        )

    record: dict[str, Any] = {
        "semantic_module_id": _require_str(
            module["semantic_module_id"],
            field=f"{label}.semantic_module_id",
        ),
        "selected_projected_source_count": selected_count,
        "route_invoked": route_invoked,
        "evidence_source_preparation_invoked": esp_invoked,
    }

    if route_invoked:
        for key in (
            "route_run_id",
            "output_dir",
            "routing_manifest_path",
            "run_summary_path",
        ):
            if key not in module:
                raise ValueError(f"{label} with route_invoked=true requires {key!r}")
            record[key] = _require_str(module[key], field=f"{label}.{key}")
    else:
        unexpected = {
            "route_run_id",
            "output_dir",
            "routing_manifest_path",
            "run_summary_path",
        }.intersection(module)
        if unexpected:
            raise ValueError(
                f"{label} with route_invoked=false must not include "
                f"{sorted(unexpected)!r}"
            )

    if esp_invoked:
        for key in (
            "evidence_source_preparation_run_id",
            "evidence_source_preparation_stage_executor_id",
            "evidence_source_preparation_declared_output_path",
            "evidence_source_preparation_run_summary_path",
        ):
            if key not in module:
                raise ValueError(
                    f"{label} with evidence_source_preparation_invoked=true "
                    f"requires {key!r}"
                )
            record[key] = _require_str(module[key], field=f"{label}.{key}")
    else:
        unexpected = {
            "evidence_source_preparation_run_id",
            "evidence_source_preparation_stage_executor_id",
            "evidence_source_preparation_declared_output_path",
            "evidence_source_preparation_run_summary_path",
        }.intersection(module)
        if unexpected:
            raise ValueError(
                f"{label} with evidence_source_preparation_invoked=false must not "
                f"include {sorted(unexpected)!r}"
            )

    return record


def _validate_evidence_comparison_participant_record(
    participant: Any,
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(participant, dict):
        raise ValueError(f"{label} must be an object")
    extra = set(participant) - _EVIDENCE_COMPARISON_PARTICIPANT_REQUIRED_KEYS
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")
    missing = _EVIDENCE_COMPARISON_PARTICIPANT_REQUIRED_KEYS - set(participant)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")
    return {
        key: _require_str(participant[key], field=f"{label}.{key}")
        for key in _EVIDENCE_COMPARISON_PARTICIPANT_REQUIRED_KEYS
    }


def _validate_evidence_comparison_record(record: Any) -> dict[str, Any]:
    label = "evidence_comparison"
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be an object")
    allowed = (
        _EVIDENCE_COMPARISON_REQUIRED_KEYS
        | _EVIDENCE_COMPARISON_STAGE_EXECUTED_OPTIONAL_KEYS
    )
    extra = set(record) - allowed
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")
    missing = _EVIDENCE_COMPARISON_REQUIRED_KEYS - set(record)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")

    capability_id = _require_str(
        record["capability_id"], field=f"{label}.capability_id"
    )
    handoff_status = _require_str(
        record["handoff_status"], field=f"{label}.handoff_status"
    )
    if handoff_status not in _EVIDENCE_COMPARISON_HANDOFF_STATUS_VALUES:
        raise ValueError(
            f"{label}.handoff_status must be one of "
            f"{sorted(_EVIDENCE_COMPARISON_HANDOFF_STATUS_VALUES)!r}, "
            f"got {handoff_status!r}"
        )
    stage_executed = record["stage_executed"]
    if not isinstance(stage_executed, bool):
        raise ValueError(f"{label}.stage_executed must be a boolean")

    normalized: dict[str, Any] = {
        "capability_id": capability_id,
        "handoff_status": handoff_status,
        "stage_executed": stage_executed,
    }
    if stage_executed:
        for key in (
            "stage_executor_id",
            "run_id",
            "output_dir",
            "run_status",
            "run_summary_path",
            "participants",
        ):
            if key not in record:
                raise ValueError(f"{label} with stage_executed=true requires {key!r}")
        run_status = _require_str(record["run_status"], field=f"{label}.run_status")
        if run_status not in _EVIDENCE_COMPARISON_RUN_STATUS_VALUES:
            raise ValueError(
                f"{label}.run_status must be one of "
                f"{sorted(_EVIDENCE_COMPARISON_RUN_STATUS_VALUES)!r}, "
                f"got {run_status!r}"
            )
        participants = record["participants"]
        if not isinstance(participants, Sequence) or isinstance(
            participants,
            (str, bytes),
        ):
            raise ValueError(f"{label}.participants must be a sequence")
        normalized.update(
            {
                "stage_executor_id": _require_str(
                    record["stage_executor_id"],
                    field=f"{label}.stage_executor_id",
                ),
                "run_id": _require_str(record["run_id"], field=f"{label}.run_id"),
                "output_dir": _require_str(
                    record["output_dir"], field=f"{label}.output_dir"
                ),
                "run_status": run_status,
                "run_summary_path": _require_str(
                    record["run_summary_path"],
                    field=f"{label}.run_summary_path",
                ),
                "participants": [
                    _validate_evidence_comparison_participant_record(
                        participant,
                        label=f"{label}.participants[{index}]",
                    )
                    for index, participant in enumerate(participants)
                ],
            }
        )
        if "declared_output_path" in record:
            normalized["declared_output_path"] = _require_str(
                record["declared_output_path"],
                field=f"{label}.declared_output_path",
            )
    else:
        unexpected = _EVIDENCE_COMPARISON_STAGE_EXECUTED_OPTIONAL_KEYS.intersection(
            record
        )
        if unexpected:
            raise ValueError(
                f"{label} with stage_executed=false must not include "
                f"{sorted(unexpected)!r}"
            )
    return normalized


def _validate_slot_record(
    slot: Any,
    *,
    index: int,
    schema_version: str = FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    require_doc_meta_bundle_reference: bool = True,
) -> dict[str, Any]:
    label = f"slots[{index}]"
    if not isinstance(slot, dict):
        raise ValueError(f"{label} must be an object")

    extra = set(slot) - _SLOT_ALLOWED_KEYS
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")

    missing = _SLOT_REQUIRED_KEYS - set(slot)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")

    slot_id = _require_str(slot["slot_id"], field=f"{label}.slot_id")
    status = _require_str(slot["status"], field=f"{label}.status")
    if status not in _SLOT_STATUS_VALUES:
        raise ValueError(
            f"{label}.status must be one of {sorted(_SLOT_STATUS_VALUES)!r}, "
            f"got {status!r}"
        )
    extract_config_id = _require_str(
        slot["extract_config_id"],
        field=f"{label}.extract_config_id",
    )
    prepare_analysis_config_id = _require_str(
        slot["prepare_analysis_config_id"],
        field=f"{label}.prepare_analysis_config_id",
    )

    normalized: dict[str, Any] = {
        "slot_id": slot_id,
        "status": status,
        "extract_config_id": extract_config_id,
        "prepare_analysis_config_id": prepare_analysis_config_id,
    }

    if "intake_run_id" in slot:
        normalized["intake_run_id"] = _require_str(
            slot["intake_run_id"],
            field=f"{label}.intake_run_id",
        )
    if "file_hash" in slot:
        normalized["file_hash"] = validate_file_hash_format(
            slot["file_hash"],
            field=f"{label}.file_hash",
        )
    if "original_file_name" in slot:
        normalized["original_file_name"] = _require_str(
            slot["original_file_name"],
            field=f"{label}.original_file_name",
        )
    if "doc_id" in slot:
        normalized["doc_id"] = _require_str(slot["doc_id"], field=f"{label}.doc_id")
    if "extract_run_id" in slot:
        normalized["extract_run_id"] = _require_str(
            slot["extract_run_id"],
            field=f"{label}.extract_run_id",
        )
    for key in (
        "prepare_analysis_run_id",
        "analysis_bundle_path",
        "block_manifest_path",
        "prepare_analysis_run_summary_path",
        "doc_meta_run_id",
        "doc_meta_output_dir",
        "doc_meta_bundle_path",
        "doc_meta_run_summary_path",
    ):
        if key in slot:
            normalized[key] = _require_str(slot[key], field=f"{label}.{key}")

    if "filter_job_ids" in slot:
        filter_job_ids = slot["filter_job_ids"]
        if not isinstance(filter_job_ids, Sequence) or isinstance(
            filter_job_ids, (str, bytes)
        ):
            raise ValueError(f"{label}.filter_job_ids must be a sequence")
        normalized["filter_job_ids"] = [
            _require_str(job_id, field=f"{label}.filter_job_ids[{idx}]")
            for idx, job_id in enumerate(filter_job_ids)
        ]

    if "filter_jobs" in slot:
        filter_jobs = slot["filter_jobs"]
        if not isinstance(filter_jobs, Sequence) or isinstance(
            filter_jobs, (str, bytes)
        ):
            raise ValueError(f"{label}.filter_jobs must be a sequence")
        normalized["filter_jobs"] = [
            _validate_filter_job_record(job, label=f"{label}.filter_jobs[{idx}]")
            for idx, job in enumerate(filter_jobs)
        ]

    if "projection_jobs" in slot:
        projection_jobs = slot["projection_jobs"]
        if not isinstance(projection_jobs, Sequence) or isinstance(
            projection_jobs,
            (str, bytes),
        ):
            raise ValueError(f"{label}.projection_jobs must be a sequence")
        normalized["projection_jobs"] = [
            _validate_projection_job_record(
                job, label=f"{label}.projection_jobs[{idx}]"
            )
            for idx, job in enumerate(projection_jobs)
        ]

    if "route_semantic_modules" in slot:
        route_semantic_modules = slot["route_semantic_modules"]
        if not isinstance(route_semantic_modules, Sequence) or isinstance(
            route_semantic_modules,
            (str, bytes),
        ):
            raise ValueError(f"{label}.route_semantic_modules must be a sequence")
        normalized["route_semantic_modules"] = [
            _validate_route_semantic_module_record(
                module,
                label=f"{label}.route_semantic_modules[{idx}]",
            )
            for idx, module in enumerate(route_semantic_modules)
        ]

    if "candidate_scope_decision_path" in slot:
        normalized["candidate_scope_decision_path"] = _require_str(
            slot["candidate_scope_decision_path"],
            field=f"{label}.candidate_scope_decision_path",
        )

    if status == "success":
        if schema_version == FLOW_RUN_SUMMARY_SCHEMA_VERSION:
            required_identity = (
                "file_hash",
                "original_file_name",
                "doc_id",
            )
        elif schema_version == PRE_ADMITTED_SOURCE_FLOW_RUN_SUMMARY_SCHEMA_VERSION:
            required_identity = (
                "intake_run_id",
                "file_hash",
                "doc_id",
            )
        else:
            required_identity = (
                "intake_run_id",
                "file_hash",
                "doc_id",
            )
        for key in (
            *required_identity,
            "extract_run_id",
            "prepare_analysis_run_id",
            "analysis_bundle_path",
            "block_manifest_path",
            "prepare_analysis_run_summary_path",
            "doc_meta_run_id",
            "doc_meta_output_dir",
            "doc_meta_bundle_path",
            "doc_meta_run_summary_path",
        ):
            if key == "doc_meta_bundle_path" and not require_doc_meta_bundle_reference:
                continue
            if key not in normalized:
                raise ValueError(f"{label} with status 'success' requires {key!r}")
        configured_filter_jobs = normalized.get("filter_job_ids") or []
        if configured_filter_jobs:
            filter_jobs = normalized.get("filter_jobs")
            if not filter_jobs:
                raise ValueError(
                    f"{label} with status 'success' requires non-empty 'filter_jobs'"
                )
            if len(filter_jobs) != len(configured_filter_jobs):
                raise ValueError(
                    f"{label}.filter_jobs length must match filter_job_ids"
                )
        configured_projection_jobs = normalized.get("projection_jobs") or []
        if configured_filter_jobs:
            if len(configured_projection_jobs) != len(configured_filter_jobs):
                raise ValueError(
                    f"{label}.projection_jobs length must match filter_job_ids"
                )
        configured_route_semantic_modules = normalized.get("route_semantic_modules")
        if configured_filter_jobs and configured_route_semantic_modules is None:
            raise ValueError(
                f"{label} with status 'success' requires 'route_semantic_modules'"
            )

    if status == SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE:
        if schema_version == FLOW_RUN_SUMMARY_SCHEMA_VERSION:
            paused_identity = ("doc_id", "file_hash", "original_file_name")
        else:
            paused_identity = ("intake_run_id", "doc_id")
        for key in (
            *paused_identity,
            "analysis_bundle_path",
            "block_manifest_path",
            "doc_meta_bundle_path",
        ):
            if key == "doc_meta_bundle_path" and not require_doc_meta_bundle_reference:
                continue
            if key not in normalized:
                raise ValueError(
                    f"{label} with status 'paused_at_candidate_scope' requires {key!r}"
                )
        configured_filter_jobs = normalized.get("filter_job_ids") or []
        filter_jobs = normalized.get("filter_jobs")
        if not configured_filter_jobs or not filter_jobs:
            raise ValueError(
                f"{label} with status 'paused_at_candidate_scope' requires filter_jobs"
            )
        if len(filter_jobs) != len(configured_filter_jobs):
            raise ValueError(f"{label}.filter_jobs length must match filter_job_ids")

    return normalized


def validate_flow_run_summary(
    payload: Mapping[str, Any], *, require_doc_meta_bundle_reference: bool = True
) -> None:
    """Validate a formal document_consistency_qc flow_run_summary envelope."""
    if not isinstance(payload, Mapping):
        raise ValueError("flow_run_summary must be a mapping")

    missing_root = _ROOT_KEYS - set(payload)
    if missing_root:
        raise ValueError(
            f"flow_run_summary is missing required root keys: {sorted(missing_root)!r}"
        )

    schema_version = _require_str(payload["schema_version"], field="schema_version")
    if schema_version == FLOW_RUN_SUMMARY_SCHEMA_VERSION:
        allowed_root_keys = _HISTORICAL_ROOT_ALLOWED_KEYS
    elif schema_version in {
        LEGACY_FLOW_RUN_SUMMARY_SCHEMA_VERSION,
        PRE_ADMITTED_SOURCE_FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    }:
        allowed_root_keys = (
            _ROOT_ALLOWED_KEYS
            if schema_version == LEGACY_FLOW_RUN_SUMMARY_SCHEMA_VERSION
            else _HISTORICAL_ROOT_ALLOWED_KEYS
        )
    else:
        raise ValueError(
            "schema_version must be one of "
            f"{list(SUPPORTED_FLOW_RUN_SUMMARY_SCHEMA_VERSIONS)!r}, "
            f"got {schema_version!r}"
        )

    extra_root = set(payload) - allowed_root_keys
    if extra_root:
        raise ValueError(
            f"flow_run_summary has unexpected root keys: {sorted(extra_root)!r}"
        )
    artifact_type = _require_str(payload["artifact_type"], field="artifact_type")
    if artifact_type != FLOW_RUN_SUMMARY_ARTIFACT_TYPE:
        raise ValueError(
            "artifact_type must be "
            f"{FLOW_RUN_SUMMARY_ARTIFACT_TYPE!r}, got {artifact_type!r}"
        )

    flow_id = _require_str(payload["flow_id"], field="flow_id")
    if flow_id != DOCUMENT_CONSISTENCY_QC_FLOW_ID:
        raise ValueError(
            f"flow_id must be {DOCUMENT_CONSISTENCY_QC_FLOW_ID!r}, got {flow_id!r}"
        )

    _require_str(payload["flow_run_id"], field="flow_run_id")
    if "task_run_id" in payload:
        _require_str(payload["task_run_id"], field="task_run_id")
    _require_str(payload["capability_id"], field="capability_id")
    _require_str(payload["source_language"], field="source_language")

    status = _require_str(payload["status"], field="status")
    if status not in _FLOW_STATUS_VALUES:
        raise ValueError(
            f"status must be one of {sorted(_FLOW_STATUS_VALUES)!r}, got {status!r}"
        )

    _require_str(payload["created_at"], field="created_at")
    _require_str(payload["completed_at"], field="completed_at")

    slots = payload["slots"]
    if not isinstance(slots, Sequence) or isinstance(slots, (str, bytes)):
        raise ValueError("slots must be a sequence")
    if not slots:
        raise ValueError("slots must contain at least one entry")

    for index, slot in enumerate(slots):
        _validate_slot_record(
            slot,
            index=index,
            schema_version=schema_version,
            require_doc_meta_bundle_reference=require_doc_meta_bundle_reference,
        )

    if "evidence_comparison" in payload:
        _validate_evidence_comparison_record(payload["evidence_comparison"])
    if "candidate_scope_decision_mode" in payload:
        _require_str(
            payload["candidate_scope_decision_mode"],
            field="candidate_scope_decision_mode",
        )


def build_flow_run_summary(
    *,
    flow_run_id: str,
    capability_id: str,
    source_language: str,
    status: str,
    created_at: str,
    completed_at: str,
    slots: Sequence[Mapping[str, Any]],
    evidence_comparison: Mapping[str, Any] | None = None,
    candidate_scope_decision_mode: str | None = None,
) -> dict[str, Any]:
    """Build and validate a flow_run_summary artifact envelope."""
    if status not in _FLOW_STATUS_VALUES:
        raise ValueError(
            f"status must be one of {sorted(_FLOW_STATUS_VALUES)!r}, got {status!r}"
        )

    normalized_slots = [
        _validate_slot_record(dict(slot), index=index)
        for index, slot in enumerate(slots)
    ]

    envelope: dict[str, Any] = {
        "artifact_type": FLOW_RUN_SUMMARY_ARTIFACT_TYPE,
        "schema_version": FLOW_RUN_SUMMARY_SCHEMA_VERSION,
        "flow_id": DOCUMENT_CONSISTENCY_QC_FLOW_ID,
        "flow_run_id": _require_str(flow_run_id, field="flow_run_id"),
        "capability_id": _require_str(capability_id, field="capability_id"),
        "source_language": _require_str(source_language, field="source_language"),
        "status": status,
        "created_at": _require_str(created_at, field="created_at"),
        "completed_at": _require_str(completed_at, field="completed_at"),
        "slots": normalized_slots,
    }
    if evidence_comparison is not None:
        envelope["evidence_comparison"] = _validate_evidence_comparison_record(
            dict(evidence_comparison)
        )
    if candidate_scope_decision_mode is not None:
        envelope["candidate_scope_decision_mode"] = _require_str(
            candidate_scope_decision_mode,
            field="candidate_scope_decision_mode",
        )
    validate_flow_run_summary(envelope)
    return envelope


def build_flow_run_slot_record(
    *,
    slot_id: str,
    status: str,
    extract_config_id: str,
    prepare_analysis_config_id: str,
    intake_run_id: str | None = None,
    file_hash: str | None = None,
    original_file_name: str | None = None,
    doc_id: str | None = None,
    extract_run_id: str | None = None,
    prepare_analysis_run_id: str | None = None,
    analysis_bundle_path: str | None = None,
    block_manifest_path: str | None = None,
    prepare_analysis_run_summary_path: str | None = None,
    doc_meta_run_id: str | None = None,
    doc_meta_output_dir: str | None = None,
    doc_meta_bundle_path: str | None = None,
    doc_meta_run_summary_path: str | None = None,
    filter_job_ids: Sequence[str] | None = None,
    filter_jobs: Sequence[Mapping[str, Any]] | None = None,
    projection_jobs: Sequence[Mapping[str, Any]] | None = None,
    route_semantic_modules: Sequence[Mapping[str, Any]] | None = None,
    candidate_scope_decision_path: str | None = None,
) -> dict[str, Any]:
    """Build one slot provenance record for inclusion in a flow_run_summary."""
    if status not in _SLOT_STATUS_VALUES:
        raise ValueError(
            f"status must be one of {sorted(_SLOT_STATUS_VALUES)!r}, got {status!r}"
        )

    record: dict[str, Any] = {
        "slot_id": _require_str(slot_id, field="slot_id"),
        "status": status,
        "extract_config_id": _require_str(
            extract_config_id,
            field="extract_config_id",
        ),
        "prepare_analysis_config_id": _require_str(
            prepare_analysis_config_id,
            field="prepare_analysis_config_id",
        ),
    }
    if intake_run_id is not None:
        record["intake_run_id"] = _require_str(
            intake_run_id,
            field="intake_run_id",
        )
    if file_hash is not None:
        record["file_hash"] = validate_file_hash_format(
            file_hash,
            field="file_hash",
        )
    if original_file_name is not None:
        record["original_file_name"] = _require_str(
            original_file_name,
            field="original_file_name",
        )
    if doc_id is not None:
        record["doc_id"] = _require_str(doc_id, field="doc_id")
    if extract_run_id is not None:
        record["extract_run_id"] = _require_str(
            extract_run_id,
            field="extract_run_id",
        )
    for key, value in (
        ("prepare_analysis_run_id", prepare_analysis_run_id),
        ("analysis_bundle_path", analysis_bundle_path),
        ("block_manifest_path", block_manifest_path),
        ("prepare_analysis_run_summary_path", prepare_analysis_run_summary_path),
        ("doc_meta_run_id", doc_meta_run_id),
        ("doc_meta_output_dir", doc_meta_output_dir),
        ("doc_meta_bundle_path", doc_meta_bundle_path),
        ("doc_meta_run_summary_path", doc_meta_run_summary_path),
    ):
        if value is not None:
            record[key] = _require_str(value, field=key)
    if filter_job_ids is not None:
        record["filter_job_ids"] = [
            _require_str(job_id, field=f"filter_job_ids[{index}]")
            for index, job_id in enumerate(filter_job_ids)
        ]
    if filter_jobs is not None:
        record["filter_jobs"] = [
            _validate_filter_job_record(dict(job), label=f"filter_jobs[{index}]")
            for index, job in enumerate(filter_jobs)
        ]
    if projection_jobs is not None:
        record["projection_jobs"] = [
            _validate_projection_job_record(
                dict(job),
                label=f"projection_jobs[{index}]",
            )
            for index, job in enumerate(projection_jobs)
        ]
    if route_semantic_modules is not None:
        record["route_semantic_modules"] = [
            _validate_route_semantic_module_record(
                dict(module),
                label=f"route_semantic_modules[{index}]",
            )
            for index, module in enumerate(route_semantic_modules)
        ]
    if candidate_scope_decision_path is not None:
        record["candidate_scope_decision_path"] = _require_str(
            candidate_scope_decision_path,
            field="candidate_scope_decision_path",
        )
    return record
