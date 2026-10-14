# ruff: noqa: TRY004
"""Deterministic heading-scope eligibility policy for aggregate-evidence processing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

TARGET_PRODUCT_CONTEXT_ROLES = frozenset(
    {
        "target_study_drug",
        "target_combination",
    }
)


def _require_gate_field(scope_assessment: Mapping[str, Any], field: str) -> Any:
    if field not in scope_assessment:
        raise ValueError(f"scope assessment missing eligibility field: {field!r}")
    return scope_assessment[field]


def _require_route_mismatch(scope_assessment: Mapping[str, Any]) -> bool:
    route_qc = _require_gate_field(scope_assessment, "route_qc")
    if not isinstance(route_qc, dict):
        raise ValueError("scope assessment route_qc must be an object")
    if "route_mismatch" not in route_qc:
        raise ValueError("scope assessment route_qc.route_mismatch is required")
    route_mismatch = route_qc["route_mismatch"]
    if not isinstance(route_mismatch, bool):
        raise ValueError("scope assessment route_qc.route_mismatch must be a boolean")
    return route_mismatch


def _build_reasons(
    *,
    unit_form: str,
    route_mismatch: bool,
    safety_role: str,
    product_context_role: str,
) -> list[str]:
    return [
        f"unit_form:{unit_form}",
        f"route_qc.route_mismatch:{str(route_mismatch).lower()}",
        f"safety_role:{safety_role}",
        f"product_context_role:{product_context_role}",
    ]


def evaluate_heading_scope_eligibility(
    *,
    scope_assessment: Mapping[str, Any],
) -> dict[str, Any]:
    unit_form_raw = _require_gate_field(scope_assessment, "unit_form")
    if not isinstance(unit_form_raw, str) or not unit_form_raw.strip():
        raise ValueError("scope assessment unit_form is required")
    unit_form = unit_form_raw.strip()

    safety_role_raw = _require_gate_field(scope_assessment, "safety_role")
    if not isinstance(safety_role_raw, str) or not safety_role_raw.strip():
        raise ValueError("scope assessment safety_role is required")
    safety_role = safety_role_raw.strip()

    product_context_role_raw = _require_gate_field(scope_assessment, "product_context_role")
    if not isinstance(product_context_role_raw, str) or not product_context_role_raw.strip():
        raise ValueError("scope assessment product_context_role is required")
    product_context_role = product_context_role_raw.strip()

    route_mismatch = _require_route_mismatch(scope_assessment)

    reasons = _build_reasons(
        unit_form=unit_form,
        route_mismatch=route_mismatch,
        safety_role=safety_role,
        product_context_role=product_context_role,
    )

    if unit_form != "aggregate":
        status = "excluded_non_aggregate_form"
    elif route_mismatch is True:
        status = "excluded_route_mismatch"
    elif safety_role == "unknown" or product_context_role == "unknown":
        status = "review_ambiguous"
    elif safety_role != "primary_safety_finding":
        status = "excluded_non_primary_safety"
    elif product_context_role not in TARGET_PRODUCT_CONTEXT_ROLES:
        status = "excluded_non_target_product"
    else:
        status = "auto_included"

    return {"status": status, "reasons": reasons}


def build_heading_scope_eligibility_entries(
    *,
    scope_assessments: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for scope_assessment in scope_assessments:
        scope_id = scope_assessment.get("scope_id")
        if not isinstance(scope_id, str) or not scope_id.strip():
            raise ValueError("scope assessment scope_id is required")
        heading_path = scope_assessment.get("heading_path")
        if not isinstance(heading_path, list):
            raise ValueError("scope assessment heading_path must be a list")
        source_unit_ids = scope_assessment.get("source_unit_ids")
        if not isinstance(source_unit_ids, list):
            raise ValueError("scope assessment source_unit_ids must be a list")

        eligibility_decision = evaluate_heading_scope_eligibility(
            scope_assessment=scope_assessment,
        )
        entries.append(
            {
                "scope_id": scope_id.strip(),
                "heading_path": [str(item) for item in heading_path],
                "source_unit_ids": [str(item) for item in source_unit_ids],
                "eligibility_decision": eligibility_decision,
            }
        )
    return entries
