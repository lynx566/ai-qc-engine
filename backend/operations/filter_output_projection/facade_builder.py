"""Neutral facade construction contract for Filter-output projection."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from operations.filter_output_projection.contracts import (
    FilterOutputProjectionFacade,
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)


@runtime_checkable
class FilterOutputProjectionFacadeBuilder(Protocol):
    """Application-installed strategy → facade construction boundary."""

    def build(
        self,
        *,
        job: ResolvedFilterOutputProjectionJob,
        runtime_dependencies: FilterOutputProjectionRuntimeDependencies,
    ) -> FilterOutputProjectionFacade: ...


__all__ = ["FilterOutputProjectionFacadeBuilder"]
