"""Build Product Task catalog from Task definitions and Product-owned metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .catalog_read_model import (
    ProductTaskCatalogEntry,
    ProductTaskInputSlotCatalogEntry,
)
from .definitions import PRODUCT_TASK_DEFINITIONS, ProductTaskDefinition
from .installation import INSTALLED_PRODUCT_TASK_BY_ID
from .presentation import (
    PRODUCT_TASK_PRESENTATION_BY_ID,
    ProductTaskPresentationMetadata,
    presentation_slot_metadata_by_id,
    validate_product_task_presentation_registry,
)


def _validate_installed_product_task_coverage(
    *,
    product_task_definitions: Sequence[ProductTaskDefinition],
    installed_task_ids: frozenset[str],
) -> None:
    definition_ids = {definition.task_id for definition in product_task_definitions}
    if definition_ids != installed_task_ids:
        missing = definition_ids - installed_task_ids
        extra = installed_task_ids - definition_ids
        if missing:
            raise ValueError(
                f"installed Product Task registry missing task_id(s): "
                f"{sorted(missing)!r}"
            )
        raise ValueError(
            f"installed Product Task registry has undeclared task_id(s): "
            f"{sorted(extra)!r}"
        )


def build_product_task_catalog(
    *,
    product_task_definitions: Sequence[
        ProductTaskDefinition
    ] = PRODUCT_TASK_DEFINITIONS,
    presentation_by_task_id: Mapping[str, ProductTaskPresentationMetadata] = (
        PRODUCT_TASK_PRESENTATION_BY_ID
    ),
    installed_task_ids: frozenset[str] | None = None,
) -> tuple[ProductTaskCatalogEntry, ...]:
    """Project Product Task definitions into catalog entries.

    Slot topology and upload metadata come only from the Product Task domain.
    Does not use DCQC capability composition or participant slot topology.
    """

    definition_by_id = {
        definition.task_id: definition for definition in product_task_definitions
    }
    validate_product_task_presentation_registry(
        product_task_definitions=definition_by_id,
        presentation_by_task_id=presentation_by_task_id,
    )
    if installed_task_ids is not None:
        _validate_installed_product_task_coverage(
            product_task_definitions=product_task_definitions,
            installed_task_ids=installed_task_ids,
        )
    else:
        _validate_installed_product_task_coverage(
            product_task_definitions=product_task_definitions,
            installed_task_ids=frozenset(INSTALLED_PRODUCT_TASK_BY_ID),
        )

    entries: list[ProductTaskCatalogEntry] = []
    for definition in product_task_definitions:
        presentation = presentation_by_task_id[definition.task_id]
        slot_metadata = presentation_slot_metadata_by_id(presentation)
        slot_entries: list[ProductTaskInputSlotCatalogEntry] = []
        for slot in definition.input_slots:
            try:
                metadata = slot_metadata[slot.slot_id]
            except KeyError as exc:
                raise ValueError(
                    f"missing Product input metadata for task_id="
                    f"{definition.task_id!r}, slot_id={slot.slot_id!r}"
                ) from exc
            slot_entries.append(
                ProductTaskInputSlotCatalogEntry(
                    slot_id=slot.slot_id,
                    expected_document_type=metadata.expected_document_type,
                    upload_label=metadata.upload_label,
                    help_text=metadata.help_text,
                )
            )
        entries.append(
            ProductTaskCatalogEntry(
                task_id=definition.task_id,
                display_name=presentation.display_name,
                description=presentation.description,
                slots=tuple(slot_entries),
            )
        )
    return tuple(entries)


def product_task_catalog_entry_to_mapping(
    entry: ProductTaskCatalogEntry,
) -> dict[str, object]:
    """Serialize one Product Task catalog entry for HTTP transport."""

    return {
        "task_id": entry.task_id,
        "display_name": entry.display_name,
        "description": entry.description,
        "slots": [
            {
                "slot_id": slot.slot_id,
                "expected_document_type": slot.expected_document_type,
                "upload_label": slot.upload_label,
                "help_text": slot.help_text,
            }
            for slot in entry.slots
        ],
    }


def product_task_catalog_to_mapping(
    entries: Sequence[ProductTaskCatalogEntry],
) -> list[dict[str, object]]:
    """Serialize Product Task catalog entries for HTTP transport."""

    return [product_task_catalog_entry_to_mapping(entry) for entry in entries]


__all__ = [
    "build_product_task_catalog",
    "product_task_catalog_entry_to_mapping",
    "product_task_catalog_to_mapping",
]
