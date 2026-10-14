"""Aggregate heading-scope assessment artifact contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core.document.doc_identity import require_bundle_file_hash

from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessment_enums import (
    PRODUCT_CONTEXT_ROLE_VALUES,
    ROUTE_QC_OBJECT_FIELDS,
    SAFETY_ROLE_VALUES,
    SUGGESTED_ROUTE_VALUES,
    UNIT_FORM_VALUES,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
)

SCOPE_ASSESSMENTS_FILENAME = "scope_assessments.json"
SCOPE_ASSESSMENTS_SCHEMA_VERSION = "0.6.0"
SCOPE_ASSESSMENTS_ARTIFACT_TYPE = "scope_assessments"
SCOPE_ASSESSMENT_TRACE_FILENAME = "scope_assessment_trace.json"
SCOPE_ASSESSMENT_TRACE_SCHEMA_VERSION = "0.4.0"

_RAW_SCOPE_ASSESSMENT_REQUIRED_KEYS = frozenset(
    {
        "scope_id",
        "product_context_role",
        "unit_form",
        "safety_role",
        "route_qc",
    }
)
_RAW_SCOPE_ASSESSMENT_ALLOWED_KEYS = _RAW_SCOPE_ASSESSMENT_REQUIRED_KEYS
_FORMAL_SCOPE_ASSESSMENT_KEYS = frozenset(
    {
        "scope_id",
        "heading_path",
        "source_unit_ids",
        "product_context_role",
        "unit_form",
        "safety_role",
        "route_qc",
        "post_llm_validation_flags",
    }
)


class ScopeAssessmentContractError(ValueError):
    """Raised when a raw scope assessment response violates the contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        scope_id: str | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.scope_id = scope_id
        self.field = field


def _require_mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScopeAssessmentContractError(
            "invalid_type",
            f"{field} must be an object",
            field=field,
        )
    return value


def _require_list(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ScopeAssessmentContractError(
            "invalid_type",
            f"{field} must be a list",
            field=field,
        )
    return value


def _validate_raw_response_root(raw_response: Mapping[str, Any]) -> list[Any]:
    if not isinstance(raw_response, Mapping):
        raise ScopeAssessmentContractError(
            "invalid_scope_response_root",
            "raw response must be a JSON object",
        )
    keys = set(raw_response)
    if keys != {"scope_assessments"}:
        if "scope_assessments" not in keys:
            raise ScopeAssessmentContractError(
                "missing_scope_assessments",
                "raw response must include scope_assessments",
            )
        extra = sorted(keys - {"scope_assessments"})
        raise ScopeAssessmentContractError(
            "extra_top_level_field",
            f"raw response has unexpected top-level fields: {', '.join(extra)}",
        )
    return _require_list(raw_response.get("scope_assessments"), field="scope_assessments")


def _validate_enum(
    value: Any,
    *,
    allowed: frozenset[str],
    field: str,
    scope_id: str,
) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ScopeAssessmentContractError(
            "invalid_enum",
            f"invalid {field} {value!r}",
            scope_id=scope_id,
            field=field,
        )
    return value


def _validate_route_qc(route_qc: Any, *, scope_id: str) -> dict[str, Any]:
    payload = _require_mapping(route_qc, field="route_qc")
    keys = set(payload)
    if keys != ROUTE_QC_OBJECT_FIELDS:
        missing = sorted(ROUTE_QC_OBJECT_FIELDS - keys)
        extra = sorted(keys - ROUTE_QC_OBJECT_FIELDS)
        raise ScopeAssessmentContractError(
            "invalid_route_qc_field",
            f"route_qc has invalid fields: missing={missing!r}, extra={extra!r}",
            scope_id=scope_id,
            field="route_qc",
        )
    route_mismatch = payload.get("route_mismatch")
    if not isinstance(route_mismatch, bool):
        raise ScopeAssessmentContractError(
            "invalid_route_qc_field",
            "route_qc.route_mismatch must be boolean",
            scope_id=scope_id,
            field="route_qc.route_mismatch",
        )
    suggested_route = payload.get("suggested_route")
    if suggested_route is not None and (
        not isinstance(suggested_route, str)
        or suggested_route not in SUGGESTED_ROUTE_VALUES
    ):
        raise ScopeAssessmentContractError(
            "invalid_enum",
            f"invalid route_qc.suggested_route {suggested_route!r}",
            scope_id=scope_id,
            field="route_qc.suggested_route",
        )
    reason = payload.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ScopeAssessmentContractError(
            "invalid_route_qc_field",
            "route_qc.reason must be null or string",
            scope_id=scope_id,
            field="route_qc.reason",
        )
    return {
        "route_mismatch": route_mismatch,
        "suggested_route": suggested_route,
        "reason": reason,
    }


def _validate_raw_scope_assessment(entry: Any) -> tuple[str, dict[str, Any]]:
    payload = _require_mapping(entry, field="scope_assessments[]")
    keys = set(payload)
    missing = sorted(_RAW_SCOPE_ASSESSMENT_REQUIRED_KEYS - keys)
    if missing:
        raise ScopeAssessmentContractError(
            "missing_scope_assessment_field",
            f"missing scope assessment fields: {', '.join(missing)}",
        )
    extra = sorted(keys - _RAW_SCOPE_ASSESSMENT_ALLOWED_KEYS)
    if extra:
        raise ScopeAssessmentContractError(
            "extra_scope_assessment_field",
            f"scope assessment has unexpected fields: {', '.join(extra)}",
        )

    raw_scope_id = payload.get("scope_id")
    if not isinstance(raw_scope_id, str) or not raw_scope_id.strip():
        raise ScopeAssessmentContractError(
            "missing_scope_id",
            "scope assessment scope_id is required",
        )
    scope_id = raw_scope_id.strip()
    return scope_id, {
        "scope_id": scope_id,
        "product_context_role": _validate_enum(
            payload.get("product_context_role"),
            allowed=PRODUCT_CONTEXT_ROLE_VALUES,
            field="product_context_role",
            scope_id=scope_id,
        ),
        "unit_form": _validate_enum(
            payload.get("unit_form"),
            allowed=UNIT_FORM_VALUES,
            field="unit_form",
            scope_id=scope_id,
        ),
        "safety_role": _validate_enum(
            payload.get("safety_role"),
            allowed=SAFETY_ROLE_VALUES,
            field="safety_role",
            scope_id=scope_id,
        ),
        "route_qc": _validate_route_qc(payload.get("route_qc"), scope_id=scope_id),
    }


def _source_unit_ids_for_scope(scope: Mapping[str, Any]) -> list[str]:
    return [
        str(unit.get("unit_id")).strip()
        for unit in (scope.get("units") or [])
        if isinstance(unit, dict)
        and isinstance(unit.get("unit_id"), str)
        and str(unit.get("unit_id")).strip()
    ]


def validate_and_canonicalize_scope_assessment_response(
    *,
    raw_response: Mapping[str, Any],
    heading_scopes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate a raw LLM response and bind it to canonical scope identity."""
    raw_entries = _validate_raw_response_root(raw_response)
    response_by_scope_id: dict[str, dict[str, Any]] = {}
    for entry in raw_entries:
        scope_id, fields = _validate_raw_scope_assessment(entry)
        if scope_id in response_by_scope_id:
            raise ScopeAssessmentContractError(
                "duplicate_scope_id",
                f"duplicate scope_id {scope_id!r} in raw response",
                scope_id=scope_id,
            )
        response_by_scope_id[scope_id] = fields

    expected_scope_ids = [
        str(scope.get("scope_id") or "").strip()
        for scope in heading_scopes
        if isinstance(scope, Mapping) and str(scope.get("scope_id") or "").strip()
    ]
    missing = [scope_id for scope_id in expected_scope_ids if scope_id not in response_by_scope_id]
    if missing:
        raise ScopeAssessmentContractError(
            "missing_scope_id",
            f"missing scope assessments for: {', '.join(missing)}",
        )
    extra = sorted(set(response_by_scope_id) - set(expected_scope_ids))
    if extra:
        raise ScopeAssessmentContractError(
            "extra_scope_id",
            f"unexpected scope assessments for: {', '.join(extra)}",
        )

    canonical: list[dict[str, Any]] = []
    for scope in heading_scopes:
        if not isinstance(scope, Mapping):
            continue
        scope_id = str(scope.get("scope_id") or "").strip()
        if not scope_id:
            continue
        heading_path = scope.get("heading_path")
        canonical.append(
            {
                "scope_id": scope_id,
                "heading_path": [
                    str(item) for item in (heading_path if isinstance(heading_path, list) else [])
                ],
                "source_unit_ids": _source_unit_ids_for_scope(scope),
                **response_by_scope_id[scope_id],
            }
        )
    return canonical


def build_scope_assessments_envelope(
    *,
    assessment_input: Mapping[str, Any],
    assessment_runtime_context: Mapping[str, Any],
    canonical_scope_assessments: Sequence[Mapping[str, Any]],
    assessment_profile_name: str,
    prompt_name: str,
    prompt_version: str,
    llm_mode: str,
    llm_profile: str | None,
    debug_trace: Mapping[str, Any] | None = None,
    assessment_input_path: str | None = None,
    assessment_runtime_context_path: str | None = None,
) -> dict[str, Any]:
    llm_input_bundle_id = str(assessment_input.get("llm_input_bundle_id") or "")
    runtime_context_ref = assessment_input.get("runtime_context_ref")
    if not isinstance(runtime_context_ref, Mapping):
        raise ScopeAssessmentContractError(
            "missing_runtime_context_ref",
            "assessment_input.runtime_context_ref must be an object",
        )
    runtime_context_id = str(runtime_context_ref.get("runtime_context_id") or "").strip()
    if not runtime_context_id:
        raise ScopeAssessmentContractError(
            "missing_runtime_context_id",
            "assessment_input.runtime_context_ref.runtime_context_id is required",
        )
    loaded_runtime_context_id = str(
        assessment_runtime_context.get("runtime_context_id")
        or assessment_runtime_context.get("assessment_runtime_context_id")
        or ""
    ).strip()
    if loaded_runtime_context_id and loaded_runtime_context_id != runtime_context_id:
        raise ScopeAssessmentContractError(
            "runtime_context_id_mismatch",
            "assessment_input runtime_context_id does not match loaded runtime context",
        )

    source_assessment_input_ref: dict[str, str] = {
        "llm_input_bundle_id": llm_input_bundle_id
    }
    if assessment_input_path:
        source_assessment_input_ref["path"] = assessment_input_path
    source_assessment_runtime_context_ref: dict[str, str] = {
        "assessment_runtime_context_id": runtime_context_id
    }
    if assessment_runtime_context_path:
        source_assessment_runtime_context_ref["path"] = assessment_runtime_context_path

    envelope: dict[str, Any] = {
        "artifact_type": SCOPE_ASSESSMENTS_ARTIFACT_TYPE,
        "schema_version": SCOPE_ASSESSMENTS_SCHEMA_VERSION,
        "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
        "phase": EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
        "doc_id": assessment_input.get("doc_id"),
        "file_hash": require_bundle_file_hash(assessment_input, label="assessment_input"),
        "document_type": assessment_input.get("document_type"),
        "zone_key": assessment_input.get("zone_key"),
        "assessment_profile_name": assessment_profile_name,
        "prompt_name": prompt_name,
        "prompt_version": prompt_version,
        "llm_mode": llm_mode,
        "source_assessment_input_ref": source_assessment_input_ref,
        "source_assessment_runtime_context_ref": source_assessment_runtime_context_ref,
        "scope_assessment_count": len(canonical_scope_assessments),
        "scope_assessments": [dict(item) for item in canonical_scope_assessments],
    }
    if llm_profile is not None:
        envelope["llm_profile"] = llm_profile
    if debug_trace and isinstance(debug_trace.get("api_result"), dict):
        envelope["api_result"] = dict(debug_trace["api_result"])
    return envelope


def _validate_envelope_scope_assessment(entry: Mapping[str, Any]) -> None:
    keys = set(entry)
    if keys != _FORMAL_SCOPE_ASSESSMENT_KEYS:
        missing = sorted(_FORMAL_SCOPE_ASSESSMENT_KEYS - keys)
        extra = sorted(keys - _FORMAL_SCOPE_ASSESSMENT_KEYS)
        raise ValueError(
            f"scope assessment has invalid fields: missing={missing!r}, extra={extra!r}"
        )
    scope_id = entry.get("scope_id")
    if not isinstance(scope_id, str) or not scope_id.strip():
        raise ValueError("scope assessment scope_id is required")
    if not isinstance(entry.get("heading_path"), list):
        raise TypeError("scope assessment heading_path must be a list")
    if not isinstance(entry.get("source_unit_ids"), list):
        raise TypeError("scope assessment source_unit_ids must be a list")
    _validate_enum(
        entry.get("product_context_role"),
        allowed=PRODUCT_CONTEXT_ROLE_VALUES,
        field="product_context_role",
        scope_id=scope_id,
    )
    _validate_enum(
        entry.get("unit_form"),
        allowed=UNIT_FORM_VALUES,
        field="unit_form",
        scope_id=scope_id,
    )
    _validate_enum(
        entry.get("safety_role"),
        allowed=SAFETY_ROLE_VALUES,
        field="safety_role",
        scope_id=scope_id,
    )
    _validate_route_qc(entry.get("route_qc"), scope_id=scope_id)
    flags = entry.get("post_llm_validation_flags")
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        raise ValueError("post_llm_validation_flags must be a list of strings")


def validate_scope_assessments_envelope(payload: Mapping[str, Any]) -> None:
    if payload.get("artifact_type") != SCOPE_ASSESSMENTS_ARTIFACT_TYPE:
        raise ValueError(f"artifact_type must be {SCOPE_ASSESSMENTS_ARTIFACT_TYPE!r}")
    if payload.get("schema_version") != SCOPE_ASSESSMENTS_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported scope_assessments schema_version {payload.get('schema_version')!r}"
        )
    if payload.get("stage") != EVIDENCE_SOURCE_PREPARATION_STAGE:
        raise ValueError(
            "scope_assessments.stage must be 'evidence_source_preparation'"
        )
    if payload.get("phase") != EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE:
        raise ValueError("scope_assessments.phase must be 'assess'")
    scope_assessments = payload.get("scope_assessments")
    if not isinstance(scope_assessments, list):
        raise TypeError("scope_assessments must be a list")
    for entry in scope_assessments:
        if not isinstance(entry, dict):
            raise TypeError("scope_assessments entries must be objects")
        _validate_envelope_scope_assessment(entry)
    expected_count = payload.get("scope_assessment_count")
    if expected_count is not None and int(expected_count) != len(scope_assessments):
        raise ValueError("scope_assessment_count mismatch")


def is_scope_assessments_artifact(payload: Mapping[str, Any]) -> bool:
    if payload.get("artifact_type") == SCOPE_ASSESSMENTS_ARTIFACT_TYPE:
        return True
    return "scope_assessments" in payload and payload.get("schema_version") in {
        "0.2.0",
        SCOPE_ASSESSMENTS_SCHEMA_VERSION,
    }


def build_scope_assessment_trace(
    *,
    raw_scope_assessments: list[Any] | None = None,
    canonical_scope_assessments: list[Any] | None = None,
    scope_processing: list[Any] | None = None,
    contract_error: str | None = None,
    api_response_rejected: bool = False,
    fallback_used: bool = False,
    fallback_source: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCOPE_ASSESSMENT_TRACE_SCHEMA_VERSION,
        "raw_scope_assessments": list(raw_scope_assessments or []),
        "canonical_scope_assessments": list(canonical_scope_assessments or []),
        "scope_processing": list(scope_processing or []),
        "contract_error": contract_error,
        "api_response_rejected": api_response_rejected,
        "fallback_used": fallback_used,
        "fallback_source": fallback_source,
    }


def build_mock_scope_assessment(scope_id: str) -> dict[str, Any]:
    """Conservative schema-valid mock assessment for one scope."""
    return {
        "scope_id": scope_id,
        "product_context_role": "unknown",
        "unit_form": "unknown",
        "safety_role": "unknown",
        "route_qc": {
            "route_mismatch": False,
            "suggested_route": None,
            "reason": None,
        },
    }
