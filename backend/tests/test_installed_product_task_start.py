"""Focused tests for Product Task Start plan/start application boundary."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.document_consistency_qc.create_flow_result import (
    DocumentConsistencyQcCreateFlowResult,
)
from application.task_run import attach_flow_run, create_task_run
from artifacts.task_lifecycle import load_task_lifecycle_manifest
from artifacts.task_run import load_task_run_manifest, task_run_manifest_path
from task.clinical_trial_doc_qc import (
    INTERNAL_DSUR_QC_TASK_ID,
    plan_installed_product_task_start,
    product_task_start_result_to_mapping,
    resolve_installed_task_start,
    start_installed_product_task,
)
from task.clinical_trial_doc_qc.product_source_admission import (
    ProductSourceAdmissionError,
    admit_product_task_sources,
)
from task.clinical_trial_doc_qc.start import StartInstalledProductTaskResult
from task.clinical_trial_doc_qc.task_input import load_task_input_bindings

BRIDGE_PRODUCT_TASK_START_SERVICE = (
    BACKEND_ROOT
    / "bridge"
    / "document_consistency_qc"
    / "product_task_start_service.py"
)
START_TASK_PATH = BACKEND_ROOT / "task" / "clinical_trial_doc_qc" / "start.py"


def test_product_task_start_http_projection_exposes_only_task_run_id(
    tmp_path: Path,
) -> None:
    mapping = product_task_start_result_to_mapping(
        StartInstalledProductTaskResult(
            task_run_id="task_run_projection_test",
            child_flow=DocumentConsistencyQcCreateFlowResult(
                flow_id="document_consistency_qc",
                flow_run_id="document_consistency_qc_test",
                flow_status="paused_at_candidate_scope",
                paused_at_candidate_scope=True,
                paused_slot_ids=("source",),
                paused_slot_id="source",
                completed=False,
                flow_run_summary_path=tmp_path / "flow_run_summary.json",
            ),
        )
    )
    assert mapping == {"task_run_id": "task_run_projection_test"}


def test_plan_returns_resolved_task_and_allocates_task_run_id() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )

    assert planned.task_id == INTERNAL_DSUR_QC_TASK_ID
    assert planned.task_run_id.startswith("task_run_")
    assert planned.resolved.child_flow.capability_id == "internal_dsur"
    assert planned.resolved.task_definition.task_id == INTERNAL_DSUR_QC_TASK_ID
    assert planned.slot_ids == ("source",)
    assert planned.slot_ids == tuple(
        slot.slot_id for slot in planned.resolved.task_definition.input_slots
    )


def test_invalid_intent_does_not_allocate_task_run_id() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    with (
        patch(
            "task.clinical_trial_doc_qc.start.allocate_task_run_id",
            side_effect=AssertionError("allocator must not run"),
        ),
        pytest.raises(ValueError, match="unsupported task_id"),
    ):
        plan_installed_product_task_start(
            composition=composition,
            task_id="not_a_task",
            upload_slot_ids={"source"},
        )


def test_accepted_start_path_resolves_installed_task_once(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    source = tmp_path / "sample.docx"
    source.write_bytes(b"x")

    def _stop_after_request(*, request, **kwargs):
        raise RuntimeError("stop after start orchestration")

    with (
        patch(
            "task.clinical_trial_doc_qc.start.resolve_installed_task_start",
            wraps=resolve_installed_task_start,
        ) as resolve_mock,
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=_stop_after_request,
        ),
        pytest.raises(RuntimeError, match="stop after start orchestration"),
    ):
        planned = plan_installed_product_task_start(
            composition=composition,
            task_id=INTERNAL_DSUR_QC_TASK_ID,
            upload_slot_ids={"source"},
        )
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source": source},
            project_root=tmp_path,
        )

    assert resolve_mock.call_count == 1


def test_start_rejects_inputs_that_drift_from_accepted_plan(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )

    with (
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=AssertionError("execution must not start"),
        ),
        pytest.raises(ValueError, match="slot_inputs do not match accepted plan"),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={},
            project_root=tmp_path,
        )


def test_bridge_product_task_start_service_does_not_allocate_task_run_id() -> None:
    tree = ast.parse(BRIDGE_PRODUCT_TASK_START_SERVICE.read_text(encoding="utf-8"))
    source = BRIDGE_PRODUCT_TASK_START_SERVICE.read_text(encoding="utf-8")
    assert "allocate_task_run_id" not in source
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported_names.add(alias.name)
    assert "allocate_task_run_id" not in imported_names


def test_plan_slot_ids_match_product_catalog_slots() -> None:
    from task.clinical_trial_doc_qc.catalog import build_product_task_catalog
    from task.clinical_trial_doc_qc.definitions import PRODUCT_TASK_DEFINITION_BY_ID

    composition = build_installed_document_consistency_qc_application_composition()
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    catalog_entry = next(
        entry
        for entry in build_product_task_catalog()
        if entry.task_id == INTERNAL_DSUR_QC_TASK_ID
    )
    definition = PRODUCT_TASK_DEFINITION_BY_ID[INTERNAL_DSUR_QC_TASK_ID]
    assert planned.slot_ids == tuple(slot.slot_id for slot in definition.input_slots)
    assert planned.slot_ids == tuple(slot.slot_id for slot in catalog_entry.slots)


def test_start_task_module_owns_task_run_allocator_import() -> None:
    source = START_TASK_PATH.read_text(encoding="utf-8")
    assert "allocate_task_run_id" in source
    assert "plan_installed_product_task_start" in source
    assert "start_installed_product_task" in source
    assert "create_task_run" in source
    assert "attach_flow_run" in source
    assert "create_task_run_for_flow" not in source


def test_product_start_persists_empty_task_run_before_flow_attach(
    tmp_path: Path,
) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    source = tmp_path / "sample.docx"
    source.write_bytes(b"x")
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    events: list[str] = []

    def _tracking_create(**kwargs: object) -> object:
        events.append("create_task_run")
        return create_task_run(**kwargs)

    def _tracking_attach(**kwargs: object) -> object:
        events.append("attach_flow_run")
        return attach_flow_run(**kwargs)

    prepared = SimpleNamespace(
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_test_run",
    )

    def _allocate(**kwargs: object) -> object:
        events.append("allocate_flow_run")
        manifest = load_task_run_manifest(
            project_root=tmp_path,
            task_run_id=planned.task_run_id,
        )
        assert manifest["flow_runs"] == []
        return prepared

    def _execute(actual: object) -> None:
        events.append("dcqc_execute")
        assert actual is prepared
        manifest = load_task_run_manifest(
            project_root=tmp_path,
            task_run_id=planned.task_run_id,
        )
        assert manifest["flow_runs"] == [
            {
                "flow_id": "document_consistency_qc",
                "flow_run_id": "document_consistency_qc_test_run",
            }
        ]
        raise RuntimeError("stop after membership attach")

    with (
        patch(
            "task.clinical_trial_doc_qc.start.create_task_run",
            side_effect=_tracking_create,
        ),
        patch(
            "task.clinical_trial_doc_qc.start.attach_flow_run",
            side_effect=_tracking_attach,
        ),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=_allocate,
        ),
        patch(
            "task.clinical_trial_doc_qc.start.execute_prepared_installed_clinical_trial_document_consistency_qc",
            side_effect=_execute,
        ),
        pytest.raises(RuntimeError, match="stop after membership attach"),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source": source},
            project_root=tmp_path,
        )

    assert events == [
        "create_task_run",
        "allocate_flow_run",
        "attach_flow_run",
        "dcqc_execute",
    ]
    assert [item["event_type"] for item in load_task_lifecycle_manifest(
        project_root=tmp_path, task_run_id=planned.task_run_id,
    )["events"]] == [
        "input_admission_started", "flow_allocation_started",
        "flow_allocated", "flow_execution_requested",
    ]


def test_product_start_admits_task_sources_before_dcqc_execution(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    source = tmp_path / "sample.docx"
    source.write_bytes(b"x")
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    events: list[str] = []

    def _tracking_admission(**kwargs):
        events.append("admit_task_sources")
        return admit_product_task_sources(**kwargs)

    def _capture_allocate(*, request, **kwargs):
        events.append("dcqc_allocate")
        persisted = load_task_input_bindings(
            project_root=tmp_path,
            task_run_id=planned.task_run_id,
        )
        assert dict(request.participant_inputs) == persisted
        raise RuntimeError("stop after request")

    with (
        patch(
            "task.clinical_trial_doc_qc.start.admit_product_task_sources",
            side_effect=_tracking_admission,
        ),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=_capture_allocate,
        ),
        pytest.raises(RuntimeError, match="stop after request"),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source": source},
            project_root=tmp_path,
        )

    assert events == ["admit_task_sources", "dcqc_allocate"]


def test_create_task_run_failure_does_not_start_dcqc(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    source = tmp_path / "sample.docx"
    source.write_bytes(b"x")
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )

    with (
        patch(
            "task.clinical_trial_doc_qc.start.create_task_run",
            side_effect=OSError("task_run write failed"),
        ),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=AssertionError("dcqc must not start"),
        ),
        pytest.raises(OSError, match="task_run write failed"),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source": source},
            project_root=tmp_path,
        )

    assert not task_run_manifest_path(
        project_root=tmp_path,
        task_run_id=planned.task_run_id,
    ).exists()


def test_flow_allocation_failure_does_not_attach_or_execute(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    source = tmp_path / "sample.docx"
    source.write_bytes(b"x")
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )

    with (
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=OSError("flow allocation failed"),
        ),
        patch("task.clinical_trial_doc_qc.start.attach_flow_run") as attach,
        patch(
            "task.clinical_trial_doc_qc.start.execute_prepared_installed_clinical_trial_document_consistency_qc"
        ) as execute,
        pytest.raises(OSError, match="flow allocation failed"),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source": source},
            project_root=tmp_path,
        )

    attach.assert_not_called()
    execute.assert_not_called()
    assert load_task_run_manifest(
        project_root=tmp_path,
        task_run_id=planned.task_run_id,
    )["flow_runs"] == []
    assert load_task_lifecycle_manifest(
        project_root=tmp_path, task_run_id=planned.task_run_id,
    )["events"][-1]["failure_boundary"] == "flow_prepare_or_allocation"


def test_repeat_start_does_not_replace_task_or_journal(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    source = tmp_path / "sample.docx"
    source.write_bytes(b"x")
    planned = plan_installed_product_task_start(
        composition=composition, task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    with (
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=OSError("allocate failed"),
        ),
        pytest.raises(OSError),
    ):
        start_installed_product_task(
            composition=composition, planned=planned,
            slot_inputs={"source": source}, project_root=tmp_path,
        )
    task_path = task_run_manifest_path(project_root=tmp_path,
                                       task_run_id=planned.task_run_id)
    journal_path = task_path.with_name("task_lifecycle.json")
    before = (task_path.read_bytes(), journal_path.read_bytes())
    with pytest.raises(FileExistsError):
        start_installed_product_task(
            composition=composition, planned=planned,
            slot_inputs={"source": source}, project_root=tmp_path,
        )
    assert (task_path.read_bytes(), journal_path.read_bytes()) == before


def test_admission_failure_is_recorded_without_flow_allocation(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    source = tmp_path / "sample.docx"
    source.write_bytes(b"x")
    planned = plan_installed_product_task_start(
        composition=composition, task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    with (
        patch(
            "task.clinical_trial_doc_qc.start.admit_product_task_sources",
            side_effect=ProductSourceAdmissionError(
                "input_intake", "Input intake failed"
            ),
        ),
        pytest.raises(ProductSourceAdmissionError),
    ):
        start_installed_product_task(
            composition=composition, planned=planned,
            slot_inputs={"source": source}, project_root=tmp_path,
        )
    events = load_task_lifecycle_manifest(
        project_root=tmp_path, task_run_id=planned.task_run_id,
    )["events"]
    assert [item["event_type"] for item in events] == [
        "input_admission_started", "product_start_failed",
    ]
    assert events[-1]["failure_boundary"] == "input_intake"
    assert load_task_run_manifest(
        project_root=tmp_path, task_run_id=planned.task_run_id,
    )["flow_runs"] == []


def test_attach_failure_keeps_allocated_identity_outside_membership(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    source = tmp_path / "sample.docx"
    source.write_bytes(b"x")
    planned = plan_installed_product_task_start(
        composition=composition, task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    prepared = SimpleNamespace(
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_test_attach",
    )
    with (
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            return_value=prepared,
        ),
        patch(
            "task.clinical_trial_doc_qc.start.attach_flow_run",
            side_effect=OSError("attach failed"),
        ),
        pytest.raises(OSError, match="attach failed"),
    ):
        start_installed_product_task(
            composition=composition, planned=planned,
            slot_inputs={"source": source}, project_root=tmp_path,
        )
    journal = load_task_lifecycle_manifest(
        project_root=tmp_path, task_run_id=planned.task_run_id,
    )
    assert [item["event_type"] for item in journal["events"]] == [
        "input_admission_started", "flow_allocation_started",
        "flow_allocated", "product_start_failed",
    ]
    assert journal["events"][-1]["failure_boundary"] == "membership_attach"
    assert journal["events"][-1]["flow_run_id"] == prepared.flow_run_id
    assert load_task_run_manifest(
        project_root=tmp_path, task_run_id=planned.task_run_id,
    )["flow_runs"] == []


def test_privacy_binding_failure_records_flow_allocation_boundary(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    source = tmp_path / "sample.docx"
    source.write_bytes(b"x")
    planned = plan_installed_product_task_start(
        composition=composition, task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    with (
        patch(
            "task.clinical_trial_doc_qc.start.bind_task_slot_values_to_flow_participants",
            side_effect=ValueError("privacy binding failed"),
        ),
        pytest.raises(ValueError, match="privacy binding failed"),
    ):
        start_installed_product_task(
            composition=composition, planned=planned,
            slot_inputs={"source": source},
            participant_privacy_paths={"source": None}, project_root=tmp_path,
        )
    journal = load_task_lifecycle_manifest(
        project_root=tmp_path, task_run_id=planned.task_run_id,
    )
    assert [item["event_type"] for item in journal["events"]] == [
        "input_admission_started", "flow_allocation_started", "product_start_failed",
    ]
    assert journal["events"][-1]["failure_boundary"] == "flow_prepare_or_allocation"
