"""Canonical Prepare Analysis runtime operation."""

from __future__ import annotations

from typing import Any

__all__ = [
    "PrepareAnalysisDocumentResult",
    "PrepareAnalysisExecutionContext",
    "PrepareAnalysisOperationReport",
    "run_prepare_analysis_operation",
]


def __getattr__(name: str) -> Any:
    """Load operation facade exports lazily so context imports stay cycle-free."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from runtime.prepare_analysis import operations

    value = getattr(operations, name)
    globals()[name] = value
    return value
