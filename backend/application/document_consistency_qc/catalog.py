"""Build capability catalog read models from installed application metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from execution_flow.document_consistency_qc import (
    DocumentConsistencyQcParticipantSlot,
)

from application.document_consistency_qc.catalog_read_model import (
    CapabilityCatalogEntry,
    CapabilitySlotCatalogEntry,
)
from application.document_consistency_qc.composition import (
    DocumentConsistencyQcApplicationComposition,
)


@dataclass(frozen=True, slots=True)
class DocumentConsistencyQcCapabilityPresentationMetadata:
    """Presentation metadata for one DCQC Flow capability (participant topology)."""

    display_name: str
    description: str
    slot_upload_labels: Mapping[str, str]
    slot_help_texts: Mapping[str, str]


def build_capability_catalog(
    *,
    composition: DocumentConsistencyQcApplicationComposition,
    presentation_by_capability_id: Mapping[str, DocumentConsistencyQcCapabilityPresentationMetadata],
) -> tuple[CapabilityCatalogEntry, ...]:
    """Project installed capabilities into catalog read entries."""

    entries: list[CapabilityCatalogEntry] = []
    for capability_id in sorted(composition.capabilities):
        capability_config = composition.capabilities[capability_id]
        try:
            presentation = presentation_by_capability_id[capability_id]
        except KeyError as exc:
            raise ValueError(
                f"missing presentation metadata for capability_id={capability_id!r}"
            ) from exc
        entries.append(
            build_capability_catalog_entry(
                capability_id=capability_config.capability_id,
                slots=capability_config.slots,
                presentation=presentation,
                expected_document_type_bindings=composition.expected_document_type_bindings,
            )
        )
    return tuple(entries)


def build_capability_catalog_entry(
    *,
    capability_id: str,
    slots: tuple[DocumentConsistencyQcParticipantSlot, ...],
    presentation: DocumentConsistencyQcCapabilityPresentationMetadata,
    expected_document_type_bindings: Mapping[tuple[str, str], str],
) -> CapabilityCatalogEntry:
    """Project one capability slot topology and presentation into a catalog entry."""

    slot_entries: list[CapabilitySlotCatalogEntry] = []
    for slot in slots:
        binding_key = (capability_id, slot.slot_id)
        expected_document_type = expected_document_type_bindings.get(binding_key)
        try:
            upload_label = presentation.slot_upload_labels[slot.slot_id]
        except KeyError as exc:
            raise ValueError(
                f"missing upload label for capability slot "
                f"({capability_id!r}, {slot.slot_id!r})"
            ) from exc
        try:
            help_text = presentation.slot_help_texts[slot.slot_id]
        except KeyError as exc:
            raise ValueError(
                f"missing help text for capability slot "
                f"({capability_id!r}, {slot.slot_id!r})"
            ) from exc
        slot_entries.append(
            CapabilitySlotCatalogEntry(
                slot_id=slot.slot_id,
                expected_document_type=expected_document_type,
                upload_label=upload_label,
                help_text=help_text,
            )
        )
    return CapabilityCatalogEntry(
        capability_id=capability_id,
        display_name=presentation.display_name,
        description=presentation.description,
        slots=tuple(slot_entries),
    )


def catalog_entry_to_mapping(entry: CapabilityCatalogEntry) -> dict[str, object]:
    """Serialize one catalog entry for transport layers."""

    return {
        "capability_id": entry.capability_id,
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


def catalog_to_mapping(
    entries: Sequence[CapabilityCatalogEntry],
) -> list[dict[str, object]]:
    """Serialize catalog entries for transport layers."""

    return [catalog_entry_to_mapping(entry) for entry in entries]


__all__ = [
    "DocumentConsistencyQcCapabilityPresentationMetadata",
    "build_capability_catalog",
    "build_capability_catalog_entry",
    "catalog_entry_to_mapping",
    "catalog_to_mapping",
]
