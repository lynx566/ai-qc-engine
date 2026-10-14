"""Overview projection assembly from validated assessments."""

from __future__ import annotations

from operations.filter_output_projection.contracts import (
    ASSEMBLED_SEMANTIC_REPRESENTATION_KIND,
    CanonicalSourceRef,
    FilterOutputProjectionInput,
    FilterOutputProjectionStepResult,
    ProjectedSentence,
    ProjectedSource,
    SemanticProjectionOutcome,
)
from operations.filter_output_projection.projected_sentence import (
    projected_sentence_from_item,
)

from plugins.clinical_trial_doc.filter_output_projection.overview.prompt import (
    OVERVIEW_SEMANTIC_DECOMPOSITION_PROMPT_VERSION,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.response import (
    ValidatedOverviewAssessment,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.source_items import (
    PreparedOverviewInput,
    PreparedOverviewSourceItem,
    assign_heading_cohort_ids,
    canonical_source_refs_for_item,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.vocabulary import (
    SHARED_CONTEXT_MODULE,
)
from plugins.clinical_trial_doc.filter_output_projection.strategy_ids import (
    OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
)


def _source_item_payload(item: PreparedOverviewSourceItem) -> dict[str, object]:
    return {
        "source_ref": canonical_source_refs_for_item(item),
        "heading_path": list(item.heading_path),
        "text": item.text,
    }


def _canonical_source_ref(item: PreparedOverviewSourceItem) -> CanonicalSourceRef:
    return CanonicalSourceRef(refs=canonical_source_refs_for_item(item))


def _lineage(
    *,
    projection_input: FilterOutputProjectionInput,
    item: PreparedOverviewSourceItem,
) -> dict[str, str]:
    lineage = {
        "filter_job_id": projection_input.filter_job_id,
        "zone_key": projection_input.zone_key,
        "strategy_id": OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        "prompt_version": OVERVIEW_SEMANTIC_DECOMPOSITION_PROMPT_VERSION,
    }
    if item.zone_id:
        lineage["zone_id"] = item.zone_id
    return lineage


def _semantic_outcome(
    *,
    projection_input: FilterOutputProjectionInput,
    item: PreparedOverviewSourceItem,
    semantic_module_id: str,
) -> SemanticProjectionOutcome:
    return SemanticProjectionOutcome(
        semantic_module_id=semantic_module_id,
        source_refs=(_canonical_source_ref(item),),
        strategy_result={
            "source_item": _source_item_payload(item),
            "lineage": _lineage(projection_input=projection_input, item=item),
        },
    )


def _assemble_block_sentences(
    *,
    block_items: list[PreparedOverviewSourceItem],
    assessment_by_alias: dict[str, ValidatedOverviewAssessment],
    target_semantic_module_id: str,
) -> tuple[ProjectedSentence, ...]:
    """Retain this block's pure shared and target sentences in canonical order."""

    sentences: list[ProjectedSentence] = []
    block_id = block_items[0].block_id
    for item in block_items:
        if item.block_id != block_id:
            raise ValueError("overview block assembly received multiple block ids")
        modules = assessment_by_alias[item.prompt_alias].content_modules
        is_pure_shared = modules == (SHARED_CONTEXT_MODULE,)
        is_target = target_semantic_module_id in modules
        if not is_pure_shared and not is_target:
            continue
        sentences.append(
            projected_sentence_from_item(
                sentence_id=item.sentence_id,
                text=item.text,
                source_block_id=item.block_id,
            )
        )
    return tuple(sentences)


def _projected_source(
    *,
    projection_input: FilterOutputProjectionInput,
    target_semantic_module_id: str,
    sentences: tuple[ProjectedSentence, ...],
    lineage_item: PreparedOverviewSourceItem,
) -> ProjectedSource:
    if not sentences or any(
        sentence.source_block_id != lineage_item.block_id for sentence in sentences
    ):
        raise ValueError("overview projected source must contain one retained block")
    source_refs = (
        CanonicalSourceRef(
            refs={
                "block_id": lineage_item.block_id,
                "source_group": lineage_item.source_group,
            }
        ),
    )
    heading_path = list(lineage_item.heading_path)
    payload: dict[str, list[str]] = {}
    if heading_path:
        payload["heading_path"] = heading_path
    return ProjectedSource(
        semantic_module_id=target_semantic_module_id,
        source_refs=source_refs,
        representation_kind=ASSEMBLED_SEMANTIC_REPRESENTATION_KIND,
        sentences=sentences,
        lineage=_lineage(projection_input=projection_input, item=lineage_item),
        payload=payload,
    )


def assemble_overview_projection_result(
    *,
    projection_input: FilterOutputProjectionInput,
    prepared: PreparedOverviewInput,
    assessments: tuple[ValidatedOverviewAssessment, ...],
    target_semantic_module_id: str,
) -> FilterOutputProjectionStepResult:
    """Retain target-bearing cohorts while preserving one source per block."""

    assessment_by_alias = {
        assessment.prompt_alias: assessment for assessment in assessments
    }
    cohort_ids = assign_heading_cohort_ids(prepared.items)
    semantic_outcomes = [
        _semantic_outcome(
            projection_input=projection_input,
            item=item,
            semantic_module_id=module_id,
        )
        for item in prepared.items
        for module_id in assessment_by_alias[item.prompt_alias].content_modules
    ]
    projected_sources: list[ProjectedSource] = []

    cohort_items: dict[int, list[PreparedOverviewSourceItem]] = {}
    for item, cohort_id in zip(prepared.items, cohort_ids, strict=True):
        cohort_items.setdefault(cohort_id, []).append(item)

    for items in cohort_items.values():
        cohort_has_target = any(
            target_semantic_module_id
            in assessment_by_alias[item.prompt_alias].content_modules
            for item in items
        )
        if not cohort_has_target:
            continue

        block_items: dict[str, list[PreparedOverviewSourceItem]] = {}
        for item in items:
            block_items.setdefault(item.block_id, []).append(item)
        for items_for_block in block_items.values():
            sentences = _assemble_block_sentences(
                block_items=items_for_block,
                assessment_by_alias=assessment_by_alias,
                target_semantic_module_id=target_semantic_module_id,
            )
            if not sentences:
                continue
            projected_sources.append(
                _projected_source(
                    projection_input=projection_input,
                    target_semantic_module_id=target_semantic_module_id,
                    sentences=sentences,
                    lineage_item=items_for_block[0],
                )
            )

    return FilterOutputProjectionStepResult(
        filter_job_id=projection_input.filter_job_id,
        doc_id=projection_input.doc_id,
        file_hash=projection_input.file_hash,
        zone_key=projection_input.zone_key,
        projected_sources=tuple(projected_sources),
        semantic_outcomes=tuple(semantic_outcomes),
    )


__all__ = [
    "assemble_overview_projection_result",
]
