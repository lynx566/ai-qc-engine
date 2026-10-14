"""Slice A: Product Task definition foundation (task.clinical_trial_doc_qc.definitions)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from task.clinical_trial_doc_qc.definitions import (
    PRODUCT_TASK_DEFINITION_BY_ID,
    PRODUCT_TASK_DEFINITIONS,
    ProductTaskDefinition,
    ProductTaskInputSlot,
)
from task.clinical_trial_doc_qc.task_ids import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INTERNAL_CSR_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
    INTERNAL_IB_QC_TASK_ID,
)


def test_product_task_definition_ids_are_unique_in_registry() -> None:
    task_ids = [definition.task_id for definition in PRODUCT_TASK_DEFINITIONS]
    assert len(task_ids) == len(set(task_ids))


def test_product_task_definitions_cover_expected_tasks() -> None:
    assert {d.task_id for d in PRODUCT_TASK_DEFINITIONS} == {
        INTERNAL_DSUR_QC_TASK_ID,
        INTERNAL_IB_QC_TASK_ID,
        INTERNAL_CSR_QC_TASK_ID,
        DSUR_UPDATED_IB_QC_TASK_ID,
    }


def test_single_document_tasks_expose_source_slot_only() -> None:
    for task_id in (
        INTERNAL_DSUR_QC_TASK_ID,
        INTERNAL_IB_QC_TASK_ID,
        INTERNAL_CSR_QC_TASK_ID,
    ):
        definition = PRODUCT_TASK_DEFINITION_BY_ID[task_id]
        assert [slot.slot_id for slot in definition.input_slots] == ["source"]


def test_dsur_updated_ib_task_exposes_two_product_input_slots() -> None:
    definition = PRODUCT_TASK_DEFINITION_BY_ID[DSUR_UPDATED_IB_QC_TASK_ID]
    assert [slot.slot_id for slot in definition.input_slots] == [
        "source_a",
        "source_b",
    ]


def test_product_task_input_slot_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="slot_id"):
        ProductTaskInputSlot(slot_id="")


def test_product_task_definition_rejects_duplicate_input_slots() -> None:
    with pytest.raises(ValueError, match="duplicate input slot_id"):
        ProductTaskDefinition(
            task_id="broken_task",
            input_slots=(
                ProductTaskInputSlot(slot_id="source"),
                ProductTaskInputSlot(slot_id="source"),
            ),
        )


def test_definitions_module_has_no_dcqc_capability_imports() -> None:
    definitions_path = (
        BACKEND_ROOT / "task" / "clinical_trial_doc_qc" / "definitions.py"
    )
    source = definitions_path.read_text(encoding="utf-8")
    assert "clinical_trial_doc_consistency_qc" not in source
    assert "DocumentConsistencyQc" not in source
    assert "execution_flow" not in source
