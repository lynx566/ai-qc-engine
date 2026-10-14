"""Application-level capability catalog read model for Document Consistency QC."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilitySlotCatalogEntry:
    """One catalog slot combining execution facts and presentation metadata."""

    slot_id: str
    expected_document_type: str | None
    upload_label: str
    help_text: str


@dataclass(frozen=True, slots=True)
class CapabilityCatalogEntry:
    """One installed capability projected for product catalog consumption."""

    capability_id: str
    display_name: str
    description: str
    slots: tuple[CapabilitySlotCatalogEntry, ...]


__all__ = [
    "CapabilityCatalogEntry",
    "CapabilitySlotCatalogEntry",
]
