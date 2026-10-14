"""Neutral in-memory contracts for projected-source Route execution."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from artifacts.routing.types import RoutedUnitSet

from operations.filter_output_projection.contracts import ProjectedSource


@runtime_checkable
class ProjectedSourceRouteExecutor(Protocol):
    """Injected projected-source Route semantic boundary."""

    def __call__(
        self,
        *,
        projected_sources: Sequence[ProjectedSource],
        block_manifest: dict[str, Any],
        analysis_bundle: dict[str, Any],
        expected_semantic_module_id: str,
        doc_id: str,
        file_hash: str,
    ) -> RoutedUnitSet: ...


__all__ = ["ProjectedSourceRouteExecutor"]
