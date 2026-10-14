"""Deterministic direct Filter-output projection for clinical-trial documents."""

from __future__ import annotations

from dataclasses import dataclass

from operations.filter_output_projection.contracts import (
    RAW_SOURCE_REPRESENTATION_KIND,
    CanonicalSourceRef,
    FilterOutputProjectionInput,
    FilterOutputProjectionStepResult,
    ProjectedSentence,
    ProjectedSource,
    ProjectionSourceBlock,
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.projected_sentence import (
    projected_sentence_from_item,
)

DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID = "direct"
DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY = "semantic_module_id"


def _require_semantic_module_id(job: ResolvedFilterOutputProjectionJob) -> str:
    raw = job.strategy_config.get(DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(
            "strategy_config.semantic_module_id is required for direct projection"
        )
    return raw.strip()


def _canonical_source_ref(source: ProjectionSourceBlock) -> CanonicalSourceRef:
    refs: dict[str, str] = {
        "block_id": source.block_id,
        "block_kind": source.kind,
        "source_group": source.source_group,
    }
    return CanonicalSourceRef(refs=refs)


def _projected_sentences_from_block(source: ProjectionSourceBlock) -> tuple[ProjectedSentence, ...]:
    if not source.sentences:
        raise ValueError(
            f"projection source block {source.block_id!r} must include at least one "
            "canonical sentence for direct projection"
        )
    return tuple(
        projected_sentence_from_item(
            sentence_id=sentence.sentence_id,
            text=sentence.text,
            source_block_id=source.block_id,
        )
        for sentence in source.sentences
    )


def _projected_source_from_projection_block(
    *,
    source: ProjectionSourceBlock,
    semantic_module_id: str,
    projection_input: FilterOutputProjectionInput,
) -> ProjectedSource:
    source_ref = _canonical_source_ref(source)
    payload: dict[str, str | list[str]] = {"block_kind": source.kind}
    if source.heading_path:
        payload["heading_path"] = list(source.heading_path)

    return ProjectedSource(
        semantic_module_id=semantic_module_id,
        source_refs=(source_ref,),
        representation_kind=RAW_SOURCE_REPRESENTATION_KIND,
        sentences=_projected_sentences_from_block(source),
        lineage={
            "filter_job_id": projection_input.filter_job_id,
            "zone_key": projection_input.zone_key,
            "zone_id": source.zone_id,
            "source_group": source.source_group,
        },
        payload=payload,
    )


def project_direct_filter_output(
    *,
    projection_input: FilterOutputProjectionInput,
    job: ResolvedFilterOutputProjectionJob,
) -> FilterOutputProjectionStepResult:
    """Project every matched zone source to one configured semantic module."""
    if job.strategy_id != DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID:
        raise ValueError(
            "direct projection requires "
            f"strategy_id={DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID!r}"
        )

    semantic_module_id = _require_semantic_module_id(job)
    projected_sources: list[ProjectedSource] = []
    for source in projection_input.projection_sources:
        projected_sources.append(
            _projected_source_from_projection_block(
                source=source,
                semantic_module_id=semantic_module_id,
                projection_input=projection_input,
            )
        )

    return FilterOutputProjectionStepResult(
        filter_job_id=projection_input.filter_job_id,
        doc_id=projection_input.doc_id,
        file_hash=projection_input.file_hash,
        zone_key=projection_input.zone_key,
        projected_sources=tuple(projected_sources),
        semantic_outcomes=(),
    )


@dataclass(frozen=True, slots=True)
class DirectFilterOutputProjectionFacade:
    """Public facade for deterministic direct Filter-output projection."""

    def project(
        self,
        *,
        projection_input: FilterOutputProjectionInput,
        job: ResolvedFilterOutputProjectionJob,
    ) -> FilterOutputProjectionStepResult:
        return project_direct_filter_output(
            projection_input=projection_input,
            job=job,
        )


DIRECT_FILTER_OUTPUT_PROJECTION_FACADE = DirectFilterOutputProjectionFacade()


__all__ = [
    "DIRECT_FILTER_OUTPUT_PROJECTION_FACADE",
    "DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID",
    "DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY",
    "DirectFilterOutputProjectionFacade",
    "project_direct_filter_output",
]
