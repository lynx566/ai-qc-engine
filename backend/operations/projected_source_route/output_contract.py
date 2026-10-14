"""Neutral Route output descriptors derived from stage route counts and paths."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from artifacts.routing.types import ROUTES


def _require_non_empty_str(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    return stripped


def route_unit_count_key(route_output_kind: str) -> str:
    """Return the canonical per-route unit-count key used by RoutedUnitSet.route_counts."""

    return f"{_require_non_empty_str(route_output_kind, field_name='route_output_kind')}_unit_count"


def resolve_route_unit_count(
    route_counts: Mapping[str, int],
    route_output_kind: str,
) -> int:
    """Resolve one route's unit count from canonical or manifest-style count keys."""

    kind = _require_non_empty_str(route_output_kind, field_name="route_output_kind")
    suffixed_key = route_unit_count_key(kind)
    if suffixed_key in route_counts:
        return _non_negative_int(route_counts[suffixed_key], field_name=suffixed_key)
    if kind in route_counts:
        return _non_negative_int(route_counts[kind], field_name=kind)
    return 0


def _non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int")
    if value < 0:
        raise ValueError(f"{field_name} must be a non-negative int")
    return value


@dataclass(frozen=True, slots=True)
class RouteOutputDescriptor:
    """One non-empty routed output produced by a Route stage run."""

    route_output_kind: str
    unit_count: int
    routed_bundle_path: Path

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "route_output_kind",
            _require_non_empty_str(
                self.route_output_kind,
                field_name="route_output_kind",
            ),
        )
        resolved_count = _non_negative_int(self.unit_count, field_name="unit_count")
        if resolved_count <= 0:
            raise ValueError("unit_count must be greater than zero for produced outputs")
        object.__setattr__(self, "unit_count", resolved_count)
        if not isinstance(self.routed_bundle_path, Path):
            raise TypeError("routed_bundle_path must be a pathlib.Path")


def build_produced_route_outputs(
    *,
    route_counts: Mapping[str, int],
    routed_bundle_paths: Mapping[str, Path | str],
) -> tuple[RouteOutputDescriptor, ...]:
    """Derive non-empty Route outputs from neutral stage counts and bundle paths.

  A route output is considered produced when its resolved ``unit_count`` is
  greater than zero. File existence is not consulted.
    """

    if not isinstance(route_counts, Mapping):
        raise TypeError("route_counts must be a mapping")
    if not isinstance(routed_bundle_paths, Mapping):
        raise TypeError("routed_bundle_paths must be a mapping")

    produced: list[RouteOutputDescriptor] = []
    for route_output_kind in ROUTES:
        unit_count = resolve_route_unit_count(route_counts, route_output_kind)
        if unit_count <= 0:
            continue
        raw_path = routed_bundle_paths.get(route_output_kind)
        if raw_path is None:
            raise ValueError(
                "routed_bundle_paths must include a path for produced "
                f"route_output_kind={route_output_kind!r}"
            )
        produced.append(
            RouteOutputDescriptor(
                route_output_kind=route_output_kind,
                unit_count=unit_count,
                routed_bundle_path=Path(raw_path),
            )
        )
    return tuple(produced)


__all__ = [
    "RouteOutputDescriptor",
    "build_produced_route_outputs",
    "resolve_route_unit_count",
    "route_unit_count_key",
]
