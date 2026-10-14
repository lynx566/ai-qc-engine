"""Projected-source sentence index and routed primary sentence materialization."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from operations.filter_output_projection.contracts import (
    RAW_SOURCE_REPRESENTATION_KIND,
    ProjectedSentence,
    ProjectedSource,
)
from operations.filter_output_projection.projected_sentence import declared_source_block_ids

ProjectedSentencesByBlockId = dict[str, tuple[ProjectedSentence, ...]]


def _primary_block_id(source: ProjectedSource) -> str:
    if not source.source_refs:
        raise ValueError("projected source must include at least one source_ref")
    block_id = source.source_refs[0].refs.get("block_id")
    if not isinstance(block_id, str) or not block_id.strip():
        raise ValueError("projected source source_ref must include block_id")
    return block_id.strip()


def validate_direct_projected_sentence_integrity(
    source: ProjectedSource,
    *,
    label: str,
) -> None:
    """Ensure Direct projected sentences belong to the source's declared block provenance."""

    if not source.sentences:
        raise ValueError(f"{label} must include non-empty sentences")
    primary_block_id = _primary_block_id(source)
    declared_blocks = declared_source_block_ids(source)
    for index, sentence in enumerate(source.sentences):
        if sentence.source_block_id not in declared_blocks:
            raise ValueError(
                f"{label}.sentences[{index}].source_block_id={sentence.source_block_id!r} "
                f"is not declared in source_refs: {sorted(declared_blocks)!r}"
            )
        if sentence.source_block_id != primary_block_id:
            raise ValueError(
                f"{label}.sentences[{index}].source_block_id={sentence.source_block_id!r} "
                f"must match direct projected source primary block_id "
                f"{primary_block_id!r}"
            )


def build_projected_sentences_by_block_id(
    projected_sources: Sequence[ProjectedSource],
) -> ProjectedSentencesByBlockId:
    """Index Direct projected substantive sentences by ``source_block_id``."""

    index: dict[str, list[ProjectedSentence]] = {}
    for source_index, source in enumerate(projected_sources):
        if source.representation_kind != RAW_SOURCE_REPRESENTATION_KIND:
            continue
        label = f"projected_sources[{source_index}]"
        validate_direct_projected_sentence_integrity(source, label=label)
        block_id = _primary_block_id(source)
        index[block_id] = list(source.sentences)
    return {block_id: tuple(sentences) for block_id, sentences in index.items()}


def routed_primary_sentence_from_projected(sentence: ProjectedSentence) -> dict[str, Any]:
    """Map one projected sentence to the routed primary body sentence shape."""

    return {
        "sentence_id": sentence.sentence_id,
        "text": sentence.text,
        "source_block_id": sentence.source_block_id,
    }


__all__ = [
    "ProjectedSentencesByBlockId",
    "build_projected_sentences_by_block_id",
    "routed_primary_sentence_from_projected",
    "validate_direct_projected_sentence_integrity",
]
