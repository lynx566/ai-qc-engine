"""Product Task presentation metadata (catalog-facing, Task-owned)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .definitions import PRODUCT_TASK_DEFINITION_BY_ID, ProductTaskDefinition
from .task_ids import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INTERNAL_CSR_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
    INTERNAL_IB_QC_TASK_ID,
)

PRODUCT_EXPECTED_DOCUMENT_TYPES: frozenset[str] = frozenset({"IB", "CSR", "DSUR"})

# Current product Flow display, matching launcher-presentation.ts. Display only;
# this is neither a persisted execution snapshot nor a backend function_id.
DOCUMENT_CONSISTENCY_QC_FUNCTION_DISPLAY = MappingProxyType(
    {
        "name": "Writing Accuracy & Consistency",
        "description": "撰写准确性与一致性核查",
    }
)


@dataclass(frozen=True, slots=True)
class ProductTaskInputSlotPresentationMetadata:
    """Product-owned upload/presentation metadata for one Task input slot."""

    slot_id: str
    upload_label: str
    help_text: str
    expected_document_type: str

    def __post_init__(self) -> None:
        if not isinstance(self.slot_id, str) or not self.slot_id.strip():
            raise ValueError("slot_id must be a non-empty string")
        if not isinstance(self.upload_label, str) or not self.upload_label.strip():
            raise ValueError("upload_label must be a non-empty string")
        if not isinstance(self.help_text, str) or not self.help_text.strip():
            raise ValueError("help_text must be a non-empty string")
        if self.expected_document_type not in PRODUCT_EXPECTED_DOCUMENT_TYPES:
            raise ValueError(
                f"expected_document_type must be one of "
                f"{sorted(PRODUCT_EXPECTED_DOCUMENT_TYPES)!r}, "
                f"got {self.expected_document_type!r}"
            )


@dataclass(frozen=True, slots=True)
class ProductTaskPresentationMetadata:
    """Presentation for one installed Product Task and its input slots."""

    display_name: str
    description: str
    input_slots: tuple[ProductTaskInputSlotPresentationMetadata, ...]


def validate_product_task_presentation_registry(
    *,
    product_task_definitions: Mapping[str, ProductTaskDefinition],
    presentation_by_task_id: Mapping[str, ProductTaskPresentationMetadata],
) -> None:
    """Ensure every Task definition has complete Product-owned slot metadata."""

    definition_ids = set(product_task_definitions)
    presentation_ids = set(presentation_by_task_id)
    if definition_ids != presentation_ids:
        missing = definition_ids - presentation_ids
        extra = presentation_ids - definition_ids
        if missing:
            raise ValueError(
                f"missing ProductTaskPresentationMetadata for task_id(s): "
                f"{sorted(missing)!r}"
            )
        raise ValueError(
            f"unknown ProductTaskPresentationMetadata for task_id(s): {sorted(extra)!r}"
        )

    for task_id, definition in product_task_definitions.items():
        presentation = presentation_by_task_id[task_id]
        definition_slot_ids = [slot.slot_id for slot in definition.input_slots]
        presentation_slot_ids = [slot.slot_id for slot in presentation.input_slots]
        if definition_slot_ids != presentation_slot_ids:
            raise ValueError(
                f"Product presentation slot_id order must match "
                f"ProductTaskDefinition for task_id={task_id!r}: "
                f"definition={definition_slot_ids!r}, "
                f"presentation={presentation_slot_ids!r}"
            )


_INTERNAL_DSUR_TASK_PRESENTATION = ProductTaskPresentationMetadata(
    display_name="研发期间安全性更新报告（DSUR）",
    description="单份研发期间安全性更新报告（DSUR）的质控任务。",
    input_slots=(
        ProductTaskInputSlotPresentationMetadata(
            slot_id="source",
            upload_label="点击或拖拽上传DSUR",
            help_text="请上传待核查的 DSUR Word 文档（.docx）。",
            expected_document_type="DSUR",
        ),
    ),
)
_INTERNAL_IB_TASK_PRESENTATION = ProductTaskPresentationMetadata(
    display_name="研究者手册（IB）",
    description="单份研究者手册（IB）的质控任务。",
    input_slots=(
        ProductTaskInputSlotPresentationMetadata(
            slot_id="source",
            upload_label="点击或拖拽上传IB",
            help_text="请上传待核查的 IB Word 文档（.docx）。",
            expected_document_type="IB",
        ),
    ),
)
_INTERNAL_CSR_TASK_PRESENTATION = ProductTaskPresentationMetadata(
    display_name="临床研究报告（CSR）",
    description="单份临床研究报告（CSR）的质控任务。",
    input_slots=(
        ProductTaskInputSlotPresentationMetadata(
            slot_id="source",
            upload_label="点击或拖拽上传CSR",
            help_text="请上传待核查的 CSR Word 文档（.docx）。",
            expected_document_type="CSR",
        ),
    ),
)
_DSUR_UPDATED_IB_TASK_PRESENTATION = ProductTaskPresentationMetadata(
    display_name="DSUR↔IB",
    description="面向 DSUR 与 IB 两份文件的文件间质控任务。",
    input_slots=(
        ProductTaskInputSlotPresentationMetadata(
            slot_id="source_a",
            upload_label="点击或拖拽上传DSUR",
            help_text="请上传 DSUR Word 文档（.docx）。",
            expected_document_type="DSUR",
        ),
        ProductTaskInputSlotPresentationMetadata(
            slot_id="source_b",
            upload_label="点击或拖拽上传IB",
            help_text="请上传更新版 IB Word 文档（.docx）。",
            expected_document_type="IB",
        ),
    ),
)

_PRODUCT_TASK_PRESENTATION: dict[str, ProductTaskPresentationMetadata] = {
    INTERNAL_DSUR_QC_TASK_ID: _INTERNAL_DSUR_TASK_PRESENTATION,
    INTERNAL_IB_QC_TASK_ID: _INTERNAL_IB_TASK_PRESENTATION,
    INTERNAL_CSR_QC_TASK_ID: _INTERNAL_CSR_TASK_PRESENTATION,
    DSUR_UPDATED_IB_QC_TASK_ID: _DSUR_UPDATED_IB_TASK_PRESENTATION,
}

validate_product_task_presentation_registry(
    product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
    presentation_by_task_id=_PRODUCT_TASK_PRESENTATION,
)

PRODUCT_TASK_PRESENTATION_BY_ID: Mapping[str, ProductTaskPresentationMetadata] = (
    MappingProxyType(_PRODUCT_TASK_PRESENTATION)
)


def presentation_slot_metadata_by_id(
    presentation: ProductTaskPresentationMetadata,
) -> Mapping[str, ProductTaskInputSlotPresentationMetadata]:
    """Index Product slot presentation by slot_id (must be unique)."""

    return {slot.slot_id: slot for slot in presentation.input_slots}


def validate_presentation_slot_metadata_sequence(
    *,
    definition: ProductTaskDefinition,
    presentation: ProductTaskPresentationMetadata,
) -> None:
    """Validate one Task definition/presentation pair (for isolated catalog fixtures)."""

    validate_product_task_presentation_registry(
        product_task_definitions={definition.task_id: definition},
        presentation_by_task_id={definition.task_id: presentation},
    )


__all__ = [
    "DOCUMENT_CONSISTENCY_QC_FUNCTION_DISPLAY",
    "PRODUCT_EXPECTED_DOCUMENT_TYPES",
    "PRODUCT_TASK_PRESENTATION_BY_ID",
    "ProductTaskInputSlotPresentationMetadata",
    "ProductTaskPresentationMetadata",
    "presentation_slot_metadata_by_id",
    "validate_presentation_slot_metadata_sequence",
    "validate_product_task_presentation_registry",
]
