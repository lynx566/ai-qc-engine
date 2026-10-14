"""Shared helpers for Filter-output projection contract tests."""

from __future__ import annotations

from operations.filter_output_projection.contracts import (
    ASSEMBLED_SEMANTIC_REPRESENTATION_KIND,
    RAW_SOURCE_REPRESENTATION_KIND,
    CanonicalSourceRef,
    ProjectedSentence,
    ProjectedSource,
)


def projected_sentence(
    *,
    sentence_id: str,
    text: str,
    source_block_id: str,
) -> ProjectedSentence:
    return ProjectedSentence(
        sentence_id=sentence_id,
        text=text,
        source_block_id=source_block_id,
    )


def raw_projected_source(
    *,
    semantic_module_id: str,
    block_id: str,
    sentences: tuple[ProjectedSentence, ...] | None = None,
    block_kind: str = "paragraph",
    source_group: str = "blocks",
    heading_path: list[str] | None = None,
    lineage: dict[str, str] | None = None,
) -> ProjectedSource:
    resolved_sentences = sentences
    if resolved_sentences is None:
        resolved_sentences = (
            projected_sentence(
                sentence_id=f"{block_id}:S001",
                text="sample text",
                source_block_id=block_id,
            ),
        )
    payload: dict[str, object] = {"block_kind": block_kind}
    if heading_path:
        payload["heading_path"] = heading_path
    return ProjectedSource(
        semantic_module_id=semantic_module_id,
        source_refs=(
            CanonicalSourceRef(
                refs={
                    "block_id": block_id,
                    "block_kind": block_kind,
                    "source_group": source_group,
                }
            ),
        ),
        representation_kind=RAW_SOURCE_REPRESENTATION_KIND,
        sentences=resolved_sentences,
        lineage=lineage or {},
        payload=payload,
    )


def assembled_projected_source(
    *,
    semantic_module_id: str,
    sentences: tuple[ProjectedSentence, ...],
    source_refs: tuple[CanonicalSourceRef, ...] | None = None,
    heading_path: list[str] | None = None,
    lineage: dict[str, str] | None = None,
) -> ProjectedSource:
    if source_refs is None:
        seen: set[str] = set()
        refs: list[CanonicalSourceRef] = []
        for sentence in sentences:
            if sentence.source_block_id in seen:
                continue
            seen.add(sentence.source_block_id)
            refs.append(
                CanonicalSourceRef(
                    refs={
                        "block_id": sentence.source_block_id,
                        "source_group": "blocks",
                    }
                )
            )
        source_refs = tuple(refs)
    payload: dict[str, object] = {}
    if heading_path:
        payload["heading_path"] = heading_path
    return ProjectedSource(
        semantic_module_id=semantic_module_id,
        source_refs=source_refs,
        representation_kind=ASSEMBLED_SEMANTIC_REPRESENTATION_KIND,
        sentences=sentences,
        lineage=lineage or {},
        payload=payload,
    )


__all__ = [
    "assembled_projected_source",
    "projected_sentence",
    "raw_projected_source",
]
