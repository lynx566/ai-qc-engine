"""Product Task definitions: what the user must provide when starting a Task."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .task_ids import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INTERNAL_CSR_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
    INTERNAL_IB_QC_TASK_ID,
)


@dataclass(frozen=True, slots=True)
class ProductTaskInputSlot:
    """One Product-side input slot (user-facing upload identity)."""

    slot_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.slot_id, str) or not self.slot_id.strip():
            raise ValueError("slot_id must be a non-empty string")


@dataclass(frozen=True, slots=True)
class ProductTaskDefinition:
    """Canonical Product Task input topology (no Flow or capability coupling)."""

    task_id: str
    input_slots: tuple[ProductTaskInputSlot, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        slot_ids = [slot.slot_id for slot in self.input_slots]
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError(
                f"duplicate input slot_id values in Product Task {self.task_id!r}"
            )


def _validate_product_task_definition_tuple(
    definitions: Sequence[ProductTaskDefinition],
) -> None:
    task_ids = [definition.task_id for definition in definitions]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("Product Task definition task_id values must be unique")


_PRODUCT_TASK_DEFINITIONS: tuple[ProductTaskDefinition, ...] = (
    ProductTaskDefinition(
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        input_slots=(ProductTaskInputSlot(slot_id="source"),),
    ),
    ProductTaskDefinition(
        task_id=INTERNAL_IB_QC_TASK_ID,
        input_slots=(ProductTaskInputSlot(slot_id="source"),),
    ),
    ProductTaskDefinition(
        task_id=INTERNAL_CSR_QC_TASK_ID,
        input_slots=(ProductTaskInputSlot(slot_id="source"),),
    ),
    ProductTaskDefinition(
        task_id=DSUR_UPDATED_IB_QC_TASK_ID,
        input_slots=(
            ProductTaskInputSlot(slot_id="source_a"),
            ProductTaskInputSlot(slot_id="source_b"),
        ),
    ),
)

_validate_product_task_definition_tuple(_PRODUCT_TASK_DEFINITIONS)

PRODUCT_TASK_DEFINITIONS: tuple[ProductTaskDefinition, ...] = _PRODUCT_TASK_DEFINITIONS

PRODUCT_TASK_DEFINITION_BY_ID: Mapping[str, ProductTaskDefinition] = MappingProxyType(
    {definition.task_id: definition for definition in PRODUCT_TASK_DEFINITIONS}
)

__all__ = [
    "PRODUCT_TASK_DEFINITIONS",
    "PRODUCT_TASK_DEFINITION_BY_ID",
    "ProductTaskDefinition",
    "ProductTaskInputSlot",
]
