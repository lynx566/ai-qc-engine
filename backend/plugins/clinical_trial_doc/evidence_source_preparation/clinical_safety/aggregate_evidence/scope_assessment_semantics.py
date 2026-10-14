"""Scope-assessment semantic normalization for canonical ESP assess."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessment_enums import (
    PRODUCT_CONTEXT_ROLE_VALUES,
    SAFETY_ROLE_VALUES,
    SUGGESTED_ROUTE_VALUES,
    UNIT_FORM_VALUES,
)

DEFAULT_ROUTE_QC: dict[str, Any] = {
    "route_mismatch": False,
    "suggested_route": None,
    "reason": None,
}

_LEGACY_SAFETY_ROLE_NORMALIZATION: dict[str, tuple[str, str]] = {
    "exclude": ("not_applicable", "safety_role_legacy_exclude_to_not_applicable"),
    "route_qc_only": ("unknown", "safety_role_legacy_route_qc_only_to_unknown"),
    "safety_context_exposure": (
        "safety_context",
        "safety_role_legacy_context_variant_to_safety_context",
    ),
    "safety_context_denominator": (
        "safety_context",
        "safety_role_legacy_context_variant_to_safety_context",
    ),
    "safety_context_trial_status": (
        "safety_context",
        "safety_role_legacy_context_variant_to_safety_context",
    ),
}


@dataclass(frozen=True)
class ResolvedAnnotationQc:
    """Resolved QC fields and ordered validation flags."""

    unit_form: str
    safety_role: str
    route_qc: dict[str, Any]
    validation_flags: tuple[str, ...]


def resolve_product_context_role(raw_value: Any) -> tuple[str, list[str]]:
    if raw_value is None:
        return "unknown", ["invalid_product_context_role"]
    token = str(raw_value)
    if token not in PRODUCT_CONTEXT_ROLE_VALUES:
        return "unknown", ["invalid_product_context_role"]
    return token, []


def resolve_unit_form(raw_value: Any) -> tuple[str, list[str]]:
    if raw_value is None:
        return "unknown", ["invalid_unit_form"]
    token = str(raw_value)
    if token not in UNIT_FORM_VALUES:
        return "unknown", ["invalid_unit_form"]
    return token, []


def resolve_safety_role(raw_value: Any) -> tuple[str, list[str]]:
    if raw_value is None:
        return "unknown", ["invalid_safety_role"]
    token = str(raw_value)
    legacy = _LEGACY_SAFETY_ROLE_NORMALIZATION.get(token)
    if legacy is not None:
        return legacy[0], [legacy[1]]
    if token not in SAFETY_ROLE_VALUES:
        return "unknown", ["invalid_safety_role"]
    return token, []


def resolve_route_qc(raw_value: Any) -> tuple[dict[str, Any], list[str]]:
    if raw_value is None:
        return dict(DEFAULT_ROUTE_QC), ["missing_route_qc"]

    if not isinstance(raw_value, dict):
        return dict(DEFAULT_ROUTE_QC), ["invalid_route_qc"]

    flags: list[str] = []
    route_mismatch = raw_value.get("route_mismatch")
    if not isinstance(route_mismatch, bool):
        flags.append("invalid_route_qc")
        route_mismatch = False

    suggested_route = raw_value.get("suggested_route")
    if suggested_route is not None:
        suggested_route = str(suggested_route)
        if suggested_route not in SUGGESTED_ROUTE_VALUES:
            flags.append("invalid_suggested_route")
            suggested_route = "unknown"

    reason = raw_value.get("reason")
    if reason is not None:
        reason = str(reason) or None

    return {
        "route_mismatch": route_mismatch,
        "suggested_route": suggested_route,
        "reason": reason,
    }, flags


def resolve_annotation_qc_fields(llm_item: dict[str, Any]) -> ResolvedAnnotationQc:
    """Resolve unit_form/safety_role/route_qc as pure semantic-QC output."""
    flags: list[str] = []
    unit_form, unit_form_flags = resolve_unit_form(llm_item.get("unit_form"))
    flags.extend(unit_form_flags)

    safety_role, safety_role_flags = resolve_safety_role(llm_item.get("safety_role"))
    flags.extend(safety_role_flags)

    route_qc, route_qc_flags = resolve_route_qc(llm_item.get("route_qc"))
    flags.extend(route_qc_flags)

    return ResolvedAnnotationQc(
        unit_form=unit_form,
        safety_role=safety_role,
        route_qc=route_qc,
        validation_flags=tuple(flags),
    )
