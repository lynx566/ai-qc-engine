"""Slice C: Task-keyed → Flow-participant-keyed binding at Product Start boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from task.clinical_trial_doc_qc.start import (
    PlannedProductTaskStart,
    start_installed_product_task,
    validate_installed_task_start_intent,
)
from task.clinical_trial_doc_qc.task_input_binding import (
    bind_task_inputs_to_child_flow_participants,
)
from task.clinical_trial_doc_qc.start_resolution import (
    ResolvedInstalledChildFlow,
    ResolvedInstalledTaskStart,
    resolve_installed_task_start,
)
from artifacts.document_consistency_qc_flow_run_summary import (
    DOCUMENT_CONSISTENCY_QC_FLOW_ID,
)
from execution_flow.document_consistency_qc import (
    DocumentConsistencyQcCapabilityConfig,
    DocumentConsistencyQcParticipantSlot,
)
from task.clinical_trial_doc_qc.definitions import (
    ProductTaskDefinition,
    ProductTaskInputSlot,
)
from task.clinical_trial_doc_qc.installation import TaskInputToFlowParticipantBinding


def test_bind_task_inputs_maps_non_identity_slots() -> None:
    source = Path("/tmp/task_source.docx")
    bindings = (
        TaskInputToFlowParticipantBinding(
            task_slot_id="task_source",
            participant_slot_id="primary_document",
        ),
    )
    participant_uploads = bind_task_inputs_to_child_flow_participants(
        task_slot_inputs={"task_source": source},
        input_bindings=bindings,
    )
    assert participant_uploads == {"primary_document": source}
    assert "task_source" not in participant_uploads


def test_product_plan_accepts_task_slot_not_participant_slot_id() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    task_definition = ProductTaskDefinition(
        task_id="ownership_fixture_qc",
        input_slots=(ProductTaskInputSlot(slot_id="task_source"),),
    )
    capability_config = DocumentConsistencyQcCapabilityConfig(
        capability_id="fixture_participant_cap",
        slots=(DocumentConsistencyQcParticipantSlot(slot_id="participant_source"),),
    )
    resolved = ResolvedInstalledTaskStart(
        task_definition=task_definition,
        child_flow=ResolvedInstalledChildFlow(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id=capability_config.capability_id,
            capability_config=capability_config,
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="task_source",
                    participant_slot_id="participant_source",
                ),
            ),
        ),
    )
    with patch(
        "task.clinical_trial_doc_qc.start.resolve_installed_task_start",
        return_value=resolved,
    ):
        validate_installed_task_start_intent(
            composition=composition,
            task_id="ownership_fixture_qc",
            upload_slot_ids={"task_source"},
        )
        with pytest.raises(ValueError, match="task_source"):
            validate_installed_task_start_intent(
                composition=composition,
                task_id="ownership_fixture_qc",
                upload_slot_ids={"participant_source"},
            )


def test_start_maps_task_inputs_to_participant_request_uploads(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    task_path = tmp_path / "task_source.docx"
    task_path.write_bytes(b"x")
    task_definition = ProductTaskDefinition(
        task_id="mapping_fixture_qc",
        input_slots=(ProductTaskInputSlot(slot_id="task_source"),),
    )
    capability_config = DocumentConsistencyQcCapabilityConfig(
        capability_id="fixture_mapping_cap",
        slots=(DocumentConsistencyQcParticipantSlot(slot_id="primary_document"),),
    )
    resolved = ResolvedInstalledTaskStart(
        task_definition=task_definition,
        child_flow=ResolvedInstalledChildFlow(
            flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
            capability_id=capability_config.capability_id,
            capability_config=capability_config,
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="task_source",
                    participant_slot_id="primary_document",
                ),
            ),
        ),
    )
    planned = PlannedProductTaskStart(
        task_run_id="task_run_slice_c_non_identity",
        task_id="mapping_fixture_qc",
        resolved=resolved,
    )
    captured: dict[str, object] = {}

    def _capture_execute(*, request, **kwargs):
        captured["uploads"] = dict(request.participant_inputs)
        captured["capability_id"] = request.capability_id
        raise RuntimeError("stop after request build")

    with (
        pytest.raises(RuntimeError, match="stop after request build"),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=_capture_execute,
        ),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"task_source": task_path},
            project_root=tmp_path,
        )

    from runtime.document_source_binding import DocumentIntakeSourceBinding

    uploads = captured["uploads"]
    assert set(uploads) == {"primary_document"}
    binding = uploads["primary_document"]
    assert isinstance(binding, DocumentIntakeSourceBinding)
    assert binding.source_path.is_file()
    assert captured["capability_id"] == "fixture_mapping_cap"


def test_resolved_start_exposes_task_definition_and_child_flow() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    resolved = resolve_installed_task_start("internal_dsur_qc", composition=composition)
    assert resolved.task_definition.task_id == "internal_dsur_qc"
    assert [s.slot_id for s in resolved.task_definition.input_slots] == ["source"]
    assert resolved.child_flow.capability_id == "internal_dsur"
    assert resolved.child_flow.flow_id == DOCUMENT_CONSISTENCY_QC_FLOW_ID
    assert resolved.child_flow.input_bindings[0].task_slot_id == "source"
    assert resolved.child_flow.input_bindings[0].participant_slot_id == "source"
