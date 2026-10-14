"""Neutral structural validation for Evidence Source Preparation stage input."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from operations.projected_source_route.output_contract import resolve_route_unit_count


def _require_non_empty_str(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    return stripped


def _non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int")
    if value < 0:
        raise ValueError(f"{field_name} must be a non-negative int")
    return value


def validate_selected_route_output_reference(
    selected_route_output: Any,
    *,
    route_counts: object,
    routed_bundle_paths: object,
) -> None:
    """Validate one selected Route output against its parent Route stage facts."""

    if not isinstance(route_counts, dict):
        raise TypeError("route_stage.route_counts must be a mapping")
    if not isinstance(routed_bundle_paths, dict):
        raise TypeError("route_stage.routed_bundle_paths must be a mapping")

    route_output_kind = _require_non_empty_str(
        selected_route_output.route_output_kind,
        field_name="selected_route_output.route_output_kind",
    )
    unit_count = _non_negative_int(
        selected_route_output.unit_count,
        field_name="selected_route_output.unit_count",
    )
    if unit_count <= 0:
        raise ValueError("selected_route_output.unit_count must be greater than zero")

    routed_bundle_path = selected_route_output.routed_bundle_path
    if not isinstance(routed_bundle_path, Path):
        raise TypeError("selected_route_output.routed_bundle_path must be a pathlib.Path")

    stage_path = routed_bundle_paths.get(route_output_kind)
    if stage_path is None:
        raise ValueError(
            "selected_route_output.route_output_kind must exist in "
            "route_stage.routed_bundle_paths"
        )
    if Path(stage_path).resolve() != routed_bundle_path.resolve():
        raise ValueError(
            "selected_route_output.routed_bundle_path must match "
            "route_stage.routed_bundle_paths[route_output_kind]"
        )

    expected_unit_count = resolve_route_unit_count(route_counts, route_output_kind)
    if expected_unit_count != unit_count:
        raise ValueError(
            "selected_route_output.unit_count must match route_stage.route_counts "
            f"for route_output_kind={route_output_kind!r}"
        )


def validate_evidence_source_preparation_stage_input(
    stage_input: Any,
) -> None:
    """Validate neutral handoff invariants for one ESP stage invocation."""

    _require_non_empty_str(
        stage_input.evidence_form_id,
        field_name="evidence_form_id",
    )
    validate_selected_route_output_reference(
        stage_input.selected_route_output,
        route_counts=stage_input.route_stage.route_counts,
        routed_bundle_paths=stage_input.route_stage.routed_bundle_paths,
    )


__all__ = [
    "validate_evidence_source_preparation_stage_input",
    "validate_selected_route_output_reference",
]
