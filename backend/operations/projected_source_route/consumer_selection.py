"""Neutral structural selection over produced Route outputs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from operations.projected_source_route.output_contract import RouteOutputDescriptor


def _require_non_empty_str(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    return stripped


@dataclass(frozen=True, slots=True)
class RouteOutputSelectionResult:
    """Mechanical match of one required route output kind to a produced output."""

    required_route_output_kind: str
    selected_route_output: RouteOutputDescriptor


def select_produced_route_output(
    *,
    produced_route_outputs: Sequence[RouteOutputDescriptor],
    required_route_output_kind: str,
) -> RouteOutputSelectionResult | None:
    """Return the produced output for one required kind, or None when absent."""

    required_kind = _require_non_empty_str(
        required_route_output_kind,
        field_name="required_route_output_kind",
    )

    selected: RouteOutputDescriptor | None = None
    for index, produced in enumerate(produced_route_outputs):
        if not isinstance(produced, RouteOutputDescriptor):
            raise TypeError(
                f"produced_route_outputs[{index}] must be a RouteOutputDescriptor"
            )
        if produced.route_output_kind != required_kind:
            continue
        if selected is not None:
            raise ValueError(
                "produced_route_outputs contains duplicate "
                f"route_output_kind={required_kind!r}"
            )
        selected = produced

    if selected is None:
        return None

    return RouteOutputSelectionResult(
        required_route_output_kind=required_kind,
        selected_route_output=selected,
    )


__all__ = [
    "RouteOutputSelectionResult",
    "select_produced_route_output",
]
