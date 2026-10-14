"""Targeted tests for installed Product Task identity and public task catalog."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.capabilities import (
    INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
)
from application.clinical_trial_doc_consistency_qc.presentation_metadata import (
    INSTALLED_DCQC_CAPABILITY_PRESENTATION,
    presentation_for_dcqc_capability_id,
)
from bridge.document_consistency_qc.catalog_service import load_task_catalog
from task.clinical_trial_doc_qc import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INSTALLED_PRODUCT_TASKS,
    INTERNAL_CSR_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
    INTERNAL_IB_QC_TASK_ID,
    PRODUCT_TASK_PRESENTATION_BY_ID,
    build_product_task_catalog,
)
from task.clinical_trial_doc_qc.definitions import PRODUCT_TASK_DEFINITIONS
from task.clinical_trial_doc_qc.task_ids import (
    DSUR_UPDATED_IB_QC_TASK_ID as TASK_ID_DSUR_UPDATED_IB,
)


def test_installed_task_ids_are_unique_and_distinct_from_child_capability_ids() -> None:
    task_ids = [task.task_id for task in INSTALLED_PRODUCT_TASKS]
    assert len(set(task_ids)) == len(task_ids)
    for task in INSTALLED_PRODUCT_TASKS:
        assert task.task_id != task.child_flow.capability_id
        assert (
            task.child_flow.capability_id
            in INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
        )


def test_installed_task_set_matches_expected_ids() -> None:
    assert {task.task_id for task in INSTALLED_PRODUCT_TASKS} == {
        INTERNAL_DSUR_QC_TASK_ID,
        INTERNAL_IB_QC_TASK_ID,
        INTERNAL_CSR_QC_TASK_ID,
        DSUR_UPDATED_IB_QC_TASK_ID,
    }


def test_product_task_catalog_covers_installed_tasks_only() -> None:
    task_catalog = build_product_task_catalog()

    assert tuple(entry.task_id for entry in task_catalog) == tuple(
        task.task_id for task in INSTALLED_PRODUCT_TASKS
    )
    assert len(task_catalog) == len(INSTALLED_PRODUCT_TASKS)


def test_product_task_catalog_slots_match_product_task_definitions() -> None:
    task_catalog = build_product_task_catalog()

    for definition in PRODUCT_TASK_DEFINITIONS:
        entry = next(
            item for item in task_catalog if item.task_id == definition.task_id
        )
        assert [slot.slot_id for slot in entry.slots] == [
            slot.slot_id for slot in definition.input_slots
        ]
        for slot_entry in entry.slots:
            assert slot_entry.expected_document_type is not None
            assert slot_entry.upload_label
            assert slot_entry.help_text


def test_public_task_catalog_wire_uses_task_id_not_capability_id() -> None:
    task_catalog = build_product_task_catalog()
    wire_catalog = load_task_catalog()

    assert len(wire_catalog) == len(INSTALLED_PRODUCT_TASKS)
    assert [entry["task_id"] for entry in wire_catalog] == [
        task.task_id for task in INSTALLED_PRODUCT_TASKS
    ]
    for task_entry, wire_entry in zip(task_catalog, wire_catalog, strict=True):
        task = next(
            t for t in INSTALLED_PRODUCT_TASKS if t.task_id == task_entry.task_id
        )
        assert wire_entry["task_id"] == task.task_id
        assert wire_entry["task_id"] != task.child_flow.capability_id
        assert "capability_id" not in wire_entry


@pytest.mark.parametrize(
    "task_id,capability_id,name,description",
    [
        (
            "internal_dsur_qc",
            "internal_dsur",
            "研发期间安全性更新报告（DSUR）",
            "单份研发期间安全性更新报告（DSUR）的质控任务。",
        ),
        (
            "internal_ib_qc",
            "internal_ib",
            "研究者手册（IB）",
            "单份研究者手册（IB）的质控任务。",
        ),
        (
            "internal_csr_qc",
            "internal_csr",
            "临床研究报告（CSR）",
            "单份临床研究报告（CSR）的质控任务。",
        ),
        (
            "dsur_updated_ib_qc",
            "dsur_updated_ib",
            "DSUR↔IB",
            "面向 DSUR 与 IB 两份文件的文件间质控任务。",
        ),
    ],
)
def test_catalog_and_capability_use_shared_scenario_vocabulary(
    task_id, capability_id, name, description
) -> None:
    entry = next(row for row in build_product_task_catalog() if row.task_id == task_id)
    wire = next(row for row in load_task_catalog() if row["task_id"] == task_id)
    assert PRODUCT_TASK_PRESENTATION_BY_ID[task_id].display_name == name
    assert entry.display_name == wire["display_name"] == name
    assert entry.description == wire["description"] == description
    capability = presentation_for_dcqc_capability_id(capability_id)
    assert capability.display_name == name
    assert capability.description == description


def test_dsur_updated_ib_task_slot_topology() -> None:
    entry = next(
        item
        for item in build_product_task_catalog()
        if item.task_id == TASK_ID_DSUR_UPDATED_IB
    )
    assert [slot.slot_id for slot in entry.slots] == ["source_a", "source_b"]


def test_flow_presentation_uses_capability_id_not_task_id() -> None:
    task = INSTALLED_PRODUCT_TASKS[0]
    capability_id = task.child_flow.capability_id
    flow_presentation = presentation_for_dcqc_capability_id(capability_id)
    assert flow_presentation is not None
    assert flow_presentation.display_name == "研发期间安全性更新报告（DSUR）"
    assert presentation_for_dcqc_capability_id(task.task_id) is None
    assert INSTALLED_DCQC_CAPABILITY_PRESENTATION[capability_id] is flow_presentation
    task_presentation = PRODUCT_TASK_PRESENTATION_BY_ID[task.task_id]
    assert task_presentation.display_name == flow_presentation.display_name
    assert task.task_id != capability_id


def test_task_and_dcqc_presentation_are_independent_identity_maps() -> None:
    assert set(PRODUCT_TASK_PRESENTATION_BY_ID) == {
        "internal_dsur_qc",
        "internal_ib_qc",
        "internal_csr_qc",
        "dsur_updated_ib_qc",
    }
    assert set(INSTALLED_DCQC_CAPABILITY_PRESENTATION) == {
        "internal_dsur",
        "internal_ib",
        "internal_csr",
        "dsur_updated_ib",
    }
    for task in INSTALLED_PRODUCT_TASKS:
        assert (
            PRODUCT_TASK_PRESENTATION_BY_ID[task.task_id]
            is not INSTALLED_DCQC_CAPABILITY_PRESENTATION[task.child_flow.capability_id]
        )
