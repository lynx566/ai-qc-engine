"""Slice A: installed Product Task bindings and validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.document_consistency_qc_flow_run_summary import (
    DOCUMENT_CONSISTENCY_QC_FLOW_ID,
)
from capability.clinical_trial_doc_consistency_qc import (
    DSUR_UPDATED_IB_CONSISTENCY_QC,
    INTERNAL_DSUR_CONSISTENCY_QC,
)
from execution_flow.document_consistency_qc import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
)
from task.clinical_trial_doc_qc.definitions import PRODUCT_TASK_DEFINITION_BY_ID
from task.clinical_trial_doc_qc.installation import (
    INSTALLED_PRODUCT_TASK_BY_ID,
    INSTALLED_PRODUCT_TASKS,
    InstalledChildFlowBinding,
    InstalledProductTask,
    TaskInputToFlowParticipantBinding,
    validate_installed_product_task_installation,
    validate_installed_product_task_installations,
)
from task.clinical_trial_doc_qc.presentation import PRODUCT_TASK_PRESENTATION_BY_ID
from task.clinical_trial_doc_qc.task_ids import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
)

_DCQC_CAPABILITIES = {
    INTERNAL_DSUR_CONSISTENCY_QC.capability_id: INTERNAL_DSUR_CONSISTENCY_QC,
}


def test_internal_dsur_single_document_binding() -> None:
    task = INSTALLED_PRODUCT_TASK_BY_ID[INTERNAL_DSUR_QC_TASK_ID]
    assert task.child_flow.flow_id == DOCUMENT_CONSISTENCY_QC_FLOW_ID
    assert task.child_flow.capability_id == "internal_dsur"
    binding = task.child_flow.input_bindings[0]
    assert binding.task_slot_id == "source"
    assert binding.participant_slot_id == "source"


def test_dsur_updated_ib_cross_document_bindings() -> None:
    task = INSTALLED_PRODUCT_TASK_BY_ID[DSUR_UPDATED_IB_QC_TASK_ID]
    assert task.child_flow.capability_id == "dsur_updated_ib"
    bindings = {
        (b.task_slot_id, b.participant_slot_id) for b in task.child_flow.input_bindings
    }
    assert bindings == {("source_a", "source_a"), ("source_b", "source_b")}


def test_presentation_keyed_by_task_slot_identity() -> None:
    presentation = PRODUCT_TASK_PRESENTATION_BY_ID[DSUR_UPDATED_IB_QC_TASK_ID]
    slot_by_id = {slot.slot_id: slot for slot in presentation.input_slots}
    assert slot_by_id["source_a"].upload_label == "点击或拖拽上传DSUR"
    assert slot_by_id["source_b"].upload_label == "点击或拖拽上传IB"


def test_unknown_task_id_in_installation_rejected() -> None:
    task = InstalledProductTask(
        task_id="unknown_task_qc",
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="internal_dsur",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source",
                    participant_slot_id="source",
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="unknown task_id"):
        validate_installed_product_task_installation(
            task,
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities=_DCQC_CAPABILITIES,
        )


def test_unknown_capability_id_rejected() -> None:
    task = InstalledProductTask(
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="not_installed",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source",
                    participant_slot_id="source",
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="unknown capability_id"):
        validate_installed_product_task_installation(
            task,
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities=_DCQC_CAPABILITIES,
        )


def test_unknown_child_flow_id_rejected_during_installation_validation() -> None:
    task = InstalledProductTask(
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id="typo_flow",
            capability_id="internal_dsur",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source",
                    participant_slot_id="source",
                ),
            ),
        ),
    )

    with pytest.raises(ValueError, match="unsupported child flow_id"):
        validate_installed_product_task_installation(
            task,
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities=_DCQC_CAPABILITIES,
        )


def test_document_consistency_child_flow_id_accepted_during_installation_validation() -> (
    None
):
    validate_installed_product_task_installation(
        INSTALLED_PRODUCT_TASK_BY_ID[INTERNAL_DSUR_QC_TASK_ID],
        product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
        installed_dcqc_capabilities=_DCQC_CAPABILITIES,
    )


def test_unknown_task_slot_in_binding_rejected() -> None:
    task = InstalledProductTask(
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="internal_dsur",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="missing_slot",
                    participant_slot_id="source",
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="unknown task_slot_id"):
        validate_installed_product_task_installation(
            task,
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities=_DCQC_CAPABILITIES,
        )


def test_unknown_participant_slot_rejected() -> None:
    task = InstalledProductTask(
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="internal_dsur",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source",
                    participant_slot_id="missing_participant",
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="unknown participant_slot_id"):
        validate_installed_product_task_installation(
            task,
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities=_DCQC_CAPABILITIES,
        )


def test_duplicate_task_slot_binding_rejected() -> None:
    task = InstalledProductTask(
        task_id=DSUR_UPDATED_IB_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="dsur_updated_ib",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source_a",
                    participant_slot_id="source_a",
                ),
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source_a",
                    participant_slot_id="source_b",
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="duplicate task_slot_id"):
        validate_installed_product_task_installations(
            installed_tasks=(task,),
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities={
                DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id: (
                    DSUR_UPDATED_IB_CONSISTENCY_QC
                ),
            },
        )


def test_duplicate_participant_target_rejected() -> None:
    task = InstalledProductTask(
        task_id=DSUR_UPDATED_IB_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="dsur_updated_ib",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source_a",
                    participant_slot_id="source_a",
                ),
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source_b",
                    participant_slot_id="source_a",
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="duplicate participant_slot_id"):
        validate_installed_product_task_installations(
            installed_tasks=(task,),
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities={
                DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id: (
                    DSUR_UPDATED_IB_CONSISTENCY_QC
                ),
            },
        )


def test_missing_task_slot_coverage_rejected() -> None:
    task = InstalledProductTask(
        task_id=DSUR_UPDATED_IB_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="dsur_updated_ib",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source_a",
                    participant_slot_id="source_a",
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="missing bindings for.*task input"):
        validate_installed_product_task_installations(
            installed_tasks=(task,),
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities={
                DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id: (
                    DSUR_UPDATED_IB_CONSISTENCY_QC
                ),
            },
        )


def test_missing_participant_coverage_rejected() -> None:
    extra_participant_capability = DocumentConsistencyQcCapabilityConfig(
        capability_id="internal_dsur",
        slots=(
            DocumentConsistencyQcParticipantSlot(slot_id="source"),
            DocumentConsistencyQcParticipantSlot(slot_id="extra_participant"),
        ),
    )
    task = InstalledProductTask(
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id="internal_dsur",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source",
                    participant_slot_id="source",
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="missing bindings for.*DCQC participant"):
        validate_installed_product_task_installation(
            task,
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities={
                extra_participant_capability.capability_id: extra_participant_capability,
            },
        )


def test_duplicate_installed_product_task_id_rejected() -> None:
    duplicate = INSTALLED_PRODUCT_TASKS[0]
    with pytest.raises(ValueError, match="task_id values must be unique"):
        validate_installed_product_task_installations(
            installed_tasks=(duplicate, duplicate),
            product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
            installed_dcqc_capabilities=_DCQC_CAPABILITIES,
        )


def test_canonical_registry_has_four_tasks() -> None:
    assert len(INSTALLED_PRODUCT_TASKS) == 4
