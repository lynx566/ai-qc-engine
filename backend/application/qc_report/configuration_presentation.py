"""Configuration display only; persisted projections are the sole scope source."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from application.qc_report.presentation_model import (
    ConfigurationMode,
    ConfigurationSelectionMetadata,
    ConfigurationSelectionPresentation,
    ConfigurationSummary,
    DocumentPresentation,
    ScopeItemMetadata,
    ScopeItemPresentation,
)

CONFIGURATION_DISPLAYS = {
    "default": "使用默认范围",
    "adjusted": "在默认范围基础上调整",
    "unavailable": "最终核查范围不可用",
}
SCOPE_KINDS = ("automatic", "effective", "added", "removed")


def validate_configuration_scope_orders(
    configurations: Sequence[Mapping[str, Any]],
) -> None:
    """Reject contradictory canonical orders before any display dedup.

    All scope kinds and contributions participate, including removed headings.
    Shapes/nonnegative orders have already passed the report contract validator.
    """
    orders: dict[tuple[str, tuple[str, ...]], int] = {}
    for configuration in configurations:
        for selection in configuration["selections"]:
            for kind in SCOPE_KINDS:
                for item in selection[f"{kind}_scope_items"]:
                    identity = (selection["document_ref"], tuple(item["heading_path"]))
                    order = item["doc_order_index"]
                    if identity in orders and orders[identity] != order:
                        raise ValueError(
                            "conflicting doc_order_index for document heading_path"
                        )
                    orders[identity] = order


def project_configuration(
    configuration: Mapping[str, Any], documents: Sequence[DocumentPresentation]
) -> tuple[ConfigurationSummary, tuple[ConfigurationSelectionPresentation, ...]]:
    by_ref = {document.metadata.document_ref: document for document in documents}
    selections = []
    for selection in configuration["selections"]:
        document = by_ref[selection["document_ref"]]
        mode: ConfigurationMode = (
            "default"
            if selection["automatic_anchor_block_ids"]
            == selection["effective_anchor_block_ids"]
            and not selection["added_anchor_block_ids"]
            and not selection["removed_anchor_block_ids"]
            else "adjusted"
        )
        scopes = {
            kind: tuple(
                ScopeItemPresentation(
                    document,
                    tuple(item["heading_path"]),
                    " > ".join(item["heading_path"]),
                    ScopeItemMetadata(item["anchor_block_id"], item["doc_order_index"]),
                )
                for item in selection[f"{kind}_scope_items"]
            )
            for kind in SCOPE_KINDS
        }
        selections.append(
            ConfigurationSelectionPresentation(
                document,
                mode,
                CONFIGURATION_DISPLAYS[mode],
                *(scopes[kind] for kind in SCOPE_KINDS),
                ConfigurationSelectionMetadata(
                    selection["document_ref"],
                    selection["slot_id"],
                    selection["filter_job_id"],
                ),
            )
        )
    mode = (
        "unavailable"
        if configuration["availability"] == "unavailable"
        else "adjusted"
        if any(selection.mode == "adjusted" for selection in selections)
        else "default"
    )
    aggregated = {}
    document_order = {
        document.metadata.document_ref: index
        for index, document in enumerate(documents)
    }
    for kind in SCOPE_KINDS:
        items, seen = [], set()
        # Keep original selections above; only the aggregated display list is
        # sorted by canonical document position. Equal-position ties are stable.
        for document in documents:
            for selection in selections:
                if (
                    selection.document.metadata.document_ref
                    != document.metadata.document_ref
                ):
                    continue
                for item in getattr(selection, f"{kind}_scope_items"):
                    identity = (document.metadata.document_ref, item.heading_path)
                    if identity not in seen:
                        seen.add(identity)
                        items.append(item)
        aggregated[kind] = tuple(
            sorted(
                items,
                key=lambda item: (
                    document_order[item.document.metadata.document_ref],
                    item.metadata.doc_order_index,
                ),
            )
        )
    return (
        ConfigurationSummary(
            mode,
            CONFIGURATION_DISPLAYS[mode],
            *(aggregated[kind] for kind in SCOPE_KINDS),
        ),
        tuple(selections),
    )
