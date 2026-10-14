"""Tests for TaskRun page read projection and HTTP endpoint."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.task_run import create_task_run, create_task_run_for_flow
from artifacts.task_run import (
    FlowExecutionRef,
    build_task_run_manifest,
    save_task_run_manifest,
)
from bridge.clinical_trial_doc_qc.app import create_app
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from task.clinical_trial_doc_qc import (
    INTERNAL_DSUR_QC_TASK_ID,
    plan_installed_product_task_start,
    start_installed_product_task,
)
from task.clinical_trial_doc_qc.task_run_read import (
    TaskRunPageReadNotFoundError,
    TaskRunPageReadUnknownTaskIdError,
    load_task_run_page_context,
)
from tests.document_consistency_qc_flow_helpers import clinical_flow_invocation_kwargs

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_minimal_001.docx"
)
TASK_RUN_ID = "task_run_20260920T010203000000Z_read_api_test"


def _create_flow_test_execution_dependencies() -> dict[str, object]:
    kwargs = clinical_flow_invocation_kwargs()
    return {
        "projection_runtime_dependencies": kwargs["projection_runtime_dependencies"],
        "evidence_source_preparation_execution_dependencies": kwargs[
            "evidence_source_preparation_execution_dependencies"
        ],
    }


def _planned_product_task_start(composition, *, task_id: str, upload_slot_ids: set[str]):
    return plan_installed_product_task_start(
        composition=composition,
        task_id=task_id,
        upload_slot_ids=upload_slot_ids,
    )


def test_load_task_run_page_context_from_product_start(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    composition = build_installed_document_consistency_qc_application_composition()
    with patch(
        "task.clinical_trial_doc_qc.start.allocate_task_run_id",
        return_value=TASK_RUN_ID,
    ):
        start_installed_product_task(
            composition=composition,
            planned=_planned_product_task_start(
                composition,
                task_id=INTERNAL_DSUR_QC_TASK_ID,
                upload_slot_ids={"source"},
            ),
            slot_inputs={"source": SAMPLE_DOCX},
            project_root=tmp_path,
            **_create_flow_test_execution_dependencies(),
        )

    context = load_task_run_page_context(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
    )
    assert context.task_run_id == TASK_RUN_ID
    assert context.task_id == INTERNAL_DSUR_QC_TASK_ID
    assert context.display_name == "研发期间安全性更新报告（DSUR）"
    assert len(context.flow_runs) == 1
    assert context.flow_runs[0].flow_id == "document_consistency_qc"
    assert context.state.product_phase == "flow_execution_requested"
    assert context.state.input_ready is True
    assert context.state.flow_outcome == "paused_at_candidate_scope"
    assert context.state.requires_user_action is True
    assert context.state.result_available is False


def test_load_task_run_page_context_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(TaskRunPageReadNotFoundError, match="not found"):
        load_task_run_page_context(
            project_root=tmp_path,
            task_run_id=TASK_RUN_ID,
        )


def test_load_task_run_page_context_unknown_task_id_raises(tmp_path: Path) -> None:
    manifest = build_task_run_manifest(
        task_run_id=TASK_RUN_ID,
        task_id="not_an_installed_task",
        created_at="2026-09-20T01:02:03Z",
        updated_at="2026-09-20T01:02:04Z",
        flow_runs=(
            FlowExecutionRef(
                flow_id="document_consistency_qc",
                flow_run_id="document_consistency_qc_test",
            ),
        ),
    )
    save_task_run_manifest(project_root=tmp_path, manifest=manifest)

    with pytest.raises(TaskRunPageReadUnknownTaskIdError, match="unknown installed task_id"):
        load_task_run_page_context(project_root=tmp_path, task_run_id=TASK_RUN_ID)


def test_http_get_task_run_page_with_empty_flow_runs(tmp_path: Path) -> None:
    create_task_run(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
    )
    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
    )
    client = TestClient(create_app(bridge_config=config))

    response = client.get(f"/api/clinical-trial-doc-qc/task-runs/{TASK_RUN_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["task_run_id"] == TASK_RUN_ID
    assert body["task_id"] == INTERNAL_DSUR_QC_TASK_ID
    assert body["flow_runs"] == []
    assert body["state"] == {
        "input_ready": False,
        "product_phase": "unknown",
        "product_failure": None,
        "allocated_flow": None,
        "flow_outcome": "unknown",
        "requires_user_action": None,
        "result_available": False,
    }


def test_http_get_task_run_page(tmp_path: Path) -> None:
    create_task_run_for_flow(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_test",
    )
    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
    )
    client = TestClient(create_app(bridge_config=config))

    response = client.get(f"/api/clinical-trial-doc-qc/task-runs/{TASK_RUN_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["task_run_id"] == TASK_RUN_ID
    assert body["task_id"] == INTERNAL_DSUR_QC_TASK_ID
    assert body["display_name"] == "研发期间安全性更新报告（DSUR）"
    assert "description" not in body
    assert body["flow_runs"] == [
        {
            "flow_id": "document_consistency_qc",
            "flow_run_id": "document_consistency_qc_test",
        }
    ]


def test_http_get_task_run_page_missing_returns_404(tmp_path: Path) -> None:
    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
    )
    client = TestClient(create_app(bridge_config=config))
    response = client.get(f"/api/clinical-trial-doc-qc/task-runs/{TASK_RUN_ID}")
    assert response.status_code == 404
