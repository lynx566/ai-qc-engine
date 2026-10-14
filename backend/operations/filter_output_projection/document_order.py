"""Neutral stable document-order sort for selected projected sources."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from operations.filter_output_projection.contracts import ProjectedSource

ResolveDocumentAnchor = Callable[[ProjectedSource], tuple]


def sort_projected_sources_by_document_position(
    projected_sources: Sequence[ProjectedSource],
    *,
    resolve_document_anchor: ResolveDocumentAnchor,
) -> tuple[ProjectedSource, ...]:
    """Stable sort by resolved document anchor; equal anchors keep input order."""

    indexed = list(enumerate(projected_sources))
    indexed.sort(key=lambda pair: (resolve_document_anchor(pair[1]), pair[0]))
    return tuple(source for _, source in indexed)


__all__ = [
    "ResolveDocumentAnchor",
    "sort_projected_sources_by_document_position",
]
