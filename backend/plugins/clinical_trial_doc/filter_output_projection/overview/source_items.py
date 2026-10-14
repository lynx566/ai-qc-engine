"""Deterministic Overview source-item preparation from ProjectionSource."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from operations.filter_output_projection.contracts import (
    ProjectionSourceBlock,
)


@dataclass(frozen=True, slots=True)
class PreparedOverviewSourceItem:
    """Prompt-local Overview assessment unit with canonical sentence provenance."""

    prompt_alias: str
    sentence_id: str
    text: str
    block_id: str
    source_group: str
    heading_path: tuple[str, ...]
    zone_id: str = ""


def canonical_source_refs_for_item(item: PreparedOverviewSourceItem) -> dict[str, str]:
    """Build precise canonical refs for one prepared source item."""

    return {
        "block_id": item.block_id,
        "sentence_id": item.sentence_id,
        "source_group": item.source_group,
    }


@dataclass(frozen=True, slots=True)
class PreparedOverviewInput:
    """Ordered Overview source items and prompt-alias lookup."""

    items: tuple[PreparedOverviewSourceItem, ...]
    prompt_alias_index: Mapping[str, PreparedOverviewSourceItem]


def prepare_overview_source_items(
    projection_sources: Sequence[ProjectionSourceBlock],
) -> PreparedOverviewInput:
    """Build deterministic prompt-local source items from canonical ProjectionSource."""

    prepared_items: list[PreparedOverviewSourceItem] = []
    alias_counter = 0
    for source_block in projection_sources:
        for sentence in source_block.sentences:
            alias_counter += 1
            prepared_items.append(
                PreparedOverviewSourceItem(
                    prompt_alias=f"O{alias_counter:03d}",
                    sentence_id=sentence.sentence_id,
                    text=sentence.text,
                    block_id=source_block.block_id,
                    source_group=source_block.source_group,
                    heading_path=source_block.heading_path,
                    zone_id=source_block.zone_id,
                )
            )

    prompt_alias_index = {item.prompt_alias: item for item in prepared_items}
    if len(prompt_alias_index) != len(prepared_items):
        raise ValueError("duplicate prompt-local Overview source alias")

    return PreparedOverviewInput(
        items=tuple(prepared_items),
        prompt_alias_index=prompt_alias_index,
    )


def build_overview_prompt_input_json(prepared: PreparedOverviewInput) -> str:
    """Serialize grouped source items for the Overview assessment prompt."""

    cohort_ids = assign_heading_cohort_ids(prepared.items)
    scopes: dict[int, list[dict[str, str]]] = {}
    scope_heading_paths: dict[int, tuple[str, ...]] = {}
    for item, cohort_id in zip(prepared.items, cohort_ids, strict=True):
        scopes.setdefault(cohort_id, [])
        scope_heading_paths.setdefault(cohort_id, item.heading_path)
        scopes[cohort_id].append(
            {
                "source_id": item.prompt_alias,
                "text": item.text,
            }
        )

    payload = [
        {
            "heading_path": list(scope_heading_paths[cohort_id]),
            "source_items": scopes[cohort_id],
        }
        for cohort_id in scopes
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


HeadingCohortSignature = tuple[str, tuple[str, ...]]


def heading_cohort_signature(item: PreparedOverviewSourceItem) -> HeadingCohortSignature:
    """Temporary heading cohort identity from zone and heading path."""

    return (item.zone_id, item.heading_path)


def assign_heading_cohort_ids(
    items: tuple[PreparedOverviewSourceItem, ...],
) -> tuple[int, ...]:
    """Assign cohort ids for contiguous (zone_id, heading_path) runs in item order."""

    cohort_ids: list[int] = []
    current_signature: HeadingCohortSignature | None = None
    current_id = -1
    for item in items:
        signature = heading_cohort_signature(item)
        if signature != current_signature:
            current_id += 1
            current_signature = signature
        cohort_ids.append(current_id)
    return tuple(cohort_ids)


__all__ = [
    "HeadingCohortSignature",
    "PreparedOverviewInput",
    "PreparedOverviewSourceItem",
    "assign_heading_cohort_ids",
    "build_overview_prompt_input_json",
    "canonical_source_refs_for_item",
    "heading_cohort_signature",
    "prepare_overview_source_items",
]
