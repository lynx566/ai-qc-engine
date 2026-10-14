"""Product Task catalog read model (Task-owned, not Flow participant)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductTaskInputSlotCatalogEntry:
    """One Product Task input slot projected for catalog consumption."""

    slot_id: str
    expected_document_type: str | None
    upload_label: str
    help_text: str | None


@dataclass(frozen=True, slots=True)
class ProductTaskCatalogEntry:
    """One installed Product Task projected for catalog consumption."""

    task_id: str
    display_name: str
    description: str
    slots: tuple[ProductTaskInputSlotCatalogEntry, ...]


__all__ = [
    "ProductTaskCatalogEntry",
    "ProductTaskInputSlotCatalogEntry",
]
