"""Slice B: Product Task catalog ownership (Task definitions + Product metadata only)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from task.clinical_trial_doc_qc.catalog import build_product_task_catalog
from task.clinical_trial_doc_qc.definitions import (
    PRODUCT_TASK_DEFINITIONS,
    ProductTaskDefinition,
    ProductTaskInputSlot,
)
from task.clinical_trial_doc_qc.installation import (
    InstalledChildFlowBinding,
    InstalledProductTask,
    TaskInputToFlowParticipantBinding,
)
from task.clinical_trial_doc_qc.presentation import (
    ProductTaskInputSlotPresentationMetadata,
    ProductTaskPresentationMetadata,
    validate_presentation_slot_metadata_sequence,
)
from task.clinical_trial_doc_qc.task_ids import DSUR_UPDATED_IB_QC_TASK_ID


def test_product_catalog_module_has_no_dcqc_composition_dependency() -> None:
    catalog_path = BACKEND_ROOT / "task" / "clinical_trial_doc_qc" / "catalog.py"
    source = catalog_path.read_text(encoding="utf-8")
    assert "DocumentConsistencyQcApplicationComposition" not in source
    assert "build_capability_catalog" not in source
    assert "expected_document_type_bindings" not in source
    assert "dcqc_capability_id" not in source


def test_product_catalog_slots_follow_product_task_definitions() -> None:
    catalog = build_product_task_catalog()
    for definition in PRODUCT_TASK_DEFINITIONS:
        entry = next(item for item in catalog if item.task_id == definition.task_id)
        assert [slot.slot_id for slot in entry.slots] == [
            slot.slot_id for slot in definition.input_slots
        ]


def test_product_catalog_expected_document_types_are_product_owned() -> None:
    catalog = build_product_task_catalog()
    dsur_ib = next(
        item for item in catalog if item.task_id == DSUR_UPDATED_IB_QC_TASK_ID
    )
    by_slot = {slot.slot_id: slot for slot in dsur_ib.slots}
    assert by_slot["source_a"].expected_document_type == "DSUR"
    assert by_slot["source_b"].expected_document_type == "IB"


def test_product_catalog_order_matches_product_task_definitions() -> None:
    catalog = build_product_task_catalog()
    assert tuple(entry.task_id for entry in catalog) == tuple(
        definition.task_id for definition in PRODUCT_TASK_DEFINITIONS
    )


def test_product_catalog_ignores_non_identity_participant_binding() -> None:
    task_id = "fixture_non_identity_qc"
    definition = ProductTaskDefinition(
        task_id=task_id,
        input_slots=(ProductTaskInputSlot(slot_id="task_source"),),
    )
    presentation = ProductTaskPresentationMetadata(
        display_name="Fixture Task",
        description="Catalog uses Product slot identity only.",
        input_slots=(
            ProductTaskInputSlotPresentationMetadata(
                slot_id="task_source",
                upload_label="Upload fixture document",
                help_text="Fixture help text.",
                expected_document_type="DSUR",
            ),
        ),
    )
    validate_presentation_slot_metadata_sequence(
        definition=definition,
        presentation=presentation,
    )
    installed = InstalledProductTask(
        task_id=task_id,
        child_flow=InstalledChildFlowBinding(
            flow_id="document_consistency_qc",
            capability_id="internal_dsur",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="task_source",
                    participant_slot_id="primary_document",
                ),
            ),
        ),
    )
    _ = installed  # binding differs from catalog slot ids; catalog must not read this
    catalog = build_product_task_catalog(
        product_task_definitions=(definition,),
        presentation_by_task_id={task_id: presentation},
        installed_task_ids=frozenset({task_id}),
    )
    assert catalog[0].slots[0].slot_id == "task_source"
    assert catalog[0].slots[0].slot_id != "primary_document"


def test_product_catalog_independent_of_dcqc_participant_topology_fixture() -> None:
    task_id = "fixture_topology_qc"
    definition = ProductTaskDefinition(
        task_id=task_id,
        input_slots=(
            ProductTaskInputSlot(slot_id="source_a"),
            ProductTaskInputSlot(slot_id="source_b"),
        ),
    )
    presentation = ProductTaskPresentationMetadata(
        display_name="Fixture cross-doc",
        description="Product topology is authoritative for catalog.",
        input_slots=(
            ProductTaskInputSlotPresentationMetadata(
                slot_id="source_a",
                upload_label="Upload A",
                help_text="Help A.",
                expected_document_type="DSUR",
            ),
            ProductTaskInputSlotPresentationMetadata(
                slot_id="source_b",
                upload_label="Upload B",
                help_text="Help B.",
                expected_document_type="IB",
            ),
        ),
    )
    validate_presentation_slot_metadata_sequence(
        definition=definition,
        presentation=presentation,
    )
    catalog = build_product_task_catalog(
        product_task_definitions=(definition,),
        presentation_by_task_id={task_id: presentation},
        installed_task_ids=frozenset({task_id}),
    )
    assert [slot.slot_id for slot in catalog[0].slots] == ["source_a", "source_b"]


def test_missing_product_slot_metadata_fails_at_build() -> None:
    task_id = "broken_metadata_qc"
    definition = ProductTaskDefinition(
        task_id=task_id,
        input_slots=(ProductTaskInputSlot(slot_id="source"),),
    )
    presentation = ProductTaskPresentationMetadata(
        display_name="Broken",
        description="Missing slot metadata.",
        input_slots=(),
    )
    with pytest.raises(ValueError, match="slot_id order must match"):
        build_product_task_catalog(
            product_task_definitions=(definition,),
            presentation_by_task_id={task_id: presentation},
            installed_task_ids=frozenset({task_id}),
        )


def test_unknown_presentation_slot_fails_registry_validation() -> None:
    task_id = "extra_presentation_slot_qc"
    definition = ProductTaskDefinition(
        task_id=task_id,
        input_slots=(ProductTaskInputSlot(slot_id="source"),),
    )
    presentation = ProductTaskPresentationMetadata(
        display_name="Broken",
        description="Extra presentation slot.",
        input_slots=(
            ProductTaskInputSlotPresentationMetadata(
                slot_id="source",
                upload_label="Upload",
                help_text="Help.",
                expected_document_type="DSUR",
            ),
            ProductTaskInputSlotPresentationMetadata(
                slot_id="orphan_slot",
                upload_label="Upload orphan",
                help_text="Help orphan.",
                expected_document_type="IB",
            ),
        ),
    )
    with pytest.raises(ValueError, match="slot_id order must match"):
        validate_presentation_slot_metadata_sequence(
            definition=definition,
            presentation=presentation,
        )
