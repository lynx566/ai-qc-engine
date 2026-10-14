"""Tests for Document Consistency QC catalog read boundary, product create-flow facade, and HTTP bridge transport."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.document_consistency_qc import (
    DocumentConsistencyQcExecutionRequest,
    resolve_installed_project_root,
)
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
    SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
)
from artifacts.task_run import task_run_manifest_path
from bridge.clinical_trial_doc_qc.app import create_app
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.upload_materialization import (
    materialize_slot_uploads,
)
from bridge.document_consistency_qc.upload_staging_session import UploadStagingSession
from capability import INTERNAL_DSUR_CONSISTENCY_QC
from execution_flow.document_consistency_qc import CandidateScopeDecisionMode
from runtime.io import load_json
from task.clinical_trial_doc_qc import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INTERNAL_CSR_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
    INTERNAL_IB_QC_TASK_ID,
    PlannedProductTaskStart,
    build_product_task_catalog,
    start_installed_product_task,
    validate_installed_task_start_intent,
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
SECOND_SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)

BRIDGE_APP_PATH = BACKEND_ROOT / "bridge" / "clinical_trial_doc_qc" / "app.py"
CAPABILITY_CONFIG_PATH = (
    BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "contracts.py"
)
EXECUTION_REQUEST_PATH = (
    BACKEND_ROOT
    / "application"
    / "document_consistency_qc"
    / "execution_request.py"
)
TASK_RUN_ID = "task_run_20260920T010203000000Z_create_test"


def _planned_product_task_start(
    composition,
    *,
    task_id: str,
    upload_slot_ids: set[str],
    task_run_id: str = TASK_RUN_ID,
) -> PlannedProductTaskStart:
    resolved = validate_installed_task_start_intent(
        composition=composition,
        task_id=task_id,
        upload_slot_ids=upload_slot_ids,
    )
    return PlannedProductTaskStart(
        task_run_id=task_run_id,
        task_id=resolved.task_definition.task_id,
        resolved=resolved,
    )


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_product_task_catalog_derives_slots_from_product_task_definitions() -> None:
    from task.clinical_trial_doc_qc.definitions import PRODUCT_TASK_DEFINITION_BY_ID

    catalog = build_product_task_catalog()

    assert {entry.task_id for entry in catalog} == {
        INTERNAL_DSUR_QC_TASK_ID,
        INTERNAL_IB_QC_TASK_ID,
        INTERNAL_CSR_QC_TASK_ID,
        DSUR_UPDATED_IB_QC_TASK_ID,
    }
    for entry in catalog:
        definition = PRODUCT_TASK_DEFINITION_BY_ID[entry.task_id]
        assert tuple(slot.slot_id for slot in entry.slots) == tuple(
            slot.slot_id for slot in definition.input_slots
        )


def test_all_installed_tasks_exposed_with_matching_slots() -> None:
    from task.clinical_trial_doc_qc.definitions import PRODUCT_TASK_DEFINITION_BY_ID

    catalog = build_product_task_catalog()

    assert len(catalog) == 4
    from task.clinical_trial_doc_qc.installation import (
        INSTALLED_PRODUCT_TASKS,
    )

    for task in INSTALLED_PRODUCT_TASKS:
        entry = next(item for item in catalog if item.task_id == task.task_id)
        definition = PRODUCT_TASK_DEFINITION_BY_ID[task.task_id]
        assert [slot.slot_id for slot in entry.slots] == [
            slot.slot_id for slot in definition.input_slots
        ]
        for slot_entry in entry.slots:
            assert slot_entry.expected_document_type is not None
            assert slot_entry.upload_label
            assert slot_entry.help_text


def test_presentation_metadata_not_in_canonical_capability_config() -> None:
    tree = ast.parse(CAPABILITY_CONFIG_PATH.read_text(encoding="utf-8"))
    source = CAPABILITY_CONFIG_PATH.read_text(encoding="utf-8")
    assert "display_name" not in source
    assert "upload_label" not in source
    class_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    assert "DocumentConsistencyQcCapabilityConfig" in class_names
    assert "DocumentConsistencyQcParticipantSlot" in class_names


def test_create_facade_builds_execution_request_with_real_slot_ids(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    composition = build_installed_document_consistency_qc_application_composition()
    captured: dict[str, DocumentConsistencyQcExecutionRequest] = {}

    def _capture_execute(*, composition, request, **kwargs):
        captured["request"] = request
        raise RuntimeError("stop after capture")

    with (
        pytest.raises(RuntimeError, match="stop after capture"),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=_capture_execute,
        ),
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
        )

    request = captured["request"]
    assert request.capability_id == INTERNAL_DSUR_CONSISTENCY_QC.capability_id
    assert not hasattr(request, "task_run_id")
    assert set(request.participant_inputs) == {"source"}
    from runtime.document_source_binding import DocumentIntakeSourceBinding

    binding = request.participant_inputs["source"]
    assert isinstance(binding, DocumentIntakeSourceBinding)
    assert binding.source_path.is_file()
    assert "/inputs/source/" in binding.source_path.as_posix()


def test_execution_request_default_remains_automatic_continue() -> None:
    source = EXECUTION_REQUEST_PATH.read_text(encoding="utf-8")
    assert "AUTOMATIC_CONTINUE" in source
    from runtime.document_source_binding import DocumentIntakeSourceBinding

    request = DocumentConsistencyQcExecutionRequest(
        capability_id="internal_dsur",
        project_root=Path("."),
        participant_inputs={
            "source": DocumentIntakeSourceBinding(
                file_hash="sha256:" + "a" * 64,
                original_file_name="sample.docx",
                source_path=Path("sample.docx"),
            )
        },
        participant_privacy_paths={"source": None},
        source_language="zh",
    )
    assert (
        request.candidate_scope_decision_mode
        is CandidateScopeDecisionMode.AUTOMATIC_CONTINUE
    )


def test_create_facade_explicitly_uses_pause_at_candidate_scope(
    tmp_path: Path,
) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    captured: dict[str, DocumentConsistencyQcExecutionRequest] = {}

    def _capture_execute(*, composition, request, **kwargs):
        captured["request"] = request
        raise RuntimeError("stop after capture")

    with (
        pytest.raises(RuntimeError, match="stop after capture"),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=_capture_execute,
        ),
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
        )

    assert (
        captured["request"].candidate_scope_decision_mode
        is CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE
    )


def test_project_root_injected_by_application_not_http(tmp_path: Path) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    captured: dict[str, DocumentConsistencyQcExecutionRequest] = {}

    def _capture_execute(*, composition, request, **kwargs):
        captured["request"] = request
        raise RuntimeError("stop after capture")

    with (
        pytest.raises(RuntimeError, match="stop after capture"),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            side_effect=_capture_execute,
        ),
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
        )

    assert captured["request"].project_root == tmp_path

    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
        upload_staging_root=tmp_path / "upload_staging",
    )
    client = TestClient(create_app(bridge_config=config))
    bridge_captured: dict[str, object] = {}

    def _capture_bridge_create(**kwargs):
        bridge_captured.update(kwargs)
        from application.document_consistency_qc.create_flow_result import (
            DocumentConsistencyQcCreateFlowResult,
        )
        from task.clinical_trial_doc_qc.start import (
            StartInstalledProductTaskResult,
        )

        return StartInstalledProductTaskResult(
            task_run_id="task_run_bridge_test",
            child_flow=DocumentConsistencyQcCreateFlowResult(
                flow_id="document_consistency_qc",
                flow_run_id="bridge_test",
                flow_status=FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE,
                paused_at_candidate_scope=True,
                paused_slot_ids=("source",),
                paused_slot_id="source",
                completed=False,
                flow_run_summary_path=tmp_path / "flow_run_summary.json",
            ),
        )

    with patch(
        "bridge.document_consistency_qc.product_task_start_service.start_installed_product_task",
        side_effect=_capture_bridge_create,
    ):
        response = client.post(
            "/api/clinical-trial-doc-qc/task-runs",
            data={"task_id": INTERNAL_DSUR_QC_TASK_ID},
            files={
                "source": (
                    "sample.docx",
                    SAMPLE_DOCX.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body == {"task_run_id": "task_run_bridge_test"}
    assert bridge_captured["planned"].task_id == INTERNAL_DSUR_QC_TASK_ID
    assert bridge_captured["project_root"] == tmp_path
    assert isinstance(bridge_captured["slot_inputs"], dict)
    assert bridge_captured["slot_inputs"]["source"].is_file()


def _create_flow_test_execution_dependencies() -> dict[str, object]:
    kwargs = clinical_flow_invocation_kwargs()
    return {
        "projection_runtime_dependencies": kwargs["projection_runtime_dependencies"],
        "evidence_source_preparation_execution_dependencies": kwargs[
            "evidence_source_preparation_execution_dependencies"
        ],
    }


def test_single_slot_create_flow_pauses_at_candidate_scope(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()

    composition = build_installed_document_consistency_qc_application_composition()
    result = start_installed_product_task(
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

    assert result.task_run_id == TASK_RUN_ID
    child = result.child_flow
    assert child.flow_run_id.startswith("document_consistency_qc_")
    assert child.paused_at_candidate_scope is True
    assert child.paused_slot_ids == ("source",)
    assert child.paused_slot_id == "source"
    assert child.flow_status == FLOW_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    assert child.completed is False

    summary = load_json(child.flow_run_summary_path)
    assert summary["flow_run_id"] == child.flow_run_id
    assert "task_run_id" not in summary
    assert summary["slots"][0]["status"] == SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    task_run = load_json(
        task_run_manifest_path(project_root=tmp_path, task_run_id=TASK_RUN_ID)
    )
    assert task_run["task_id"] == INTERNAL_DSUR_QC_TASK_ID
    assert "capability_id" not in task_run
    assert task_run["flow_runs"] == [
        {"flow_id": "document_consistency_qc", "flow_run_id": child.flow_run_id}
    ]


def test_multi_slot_flow_level_pause_keeps_all_slots_at_checkpoint(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()

    composition = build_installed_document_consistency_qc_application_composition()
    result = start_installed_product_task(
        composition=composition,
        planned=_planned_product_task_start(
            composition,
            task_id=DSUR_UPDATED_IB_QC_TASK_ID,
            upload_slot_ids={"source_a", "source_b"},
        ),
        slot_inputs={
            "source_a": SAMPLE_DOCX,
            "source_b": SECOND_SAMPLE_DOCX,
        },
        project_root=tmp_path,
        **_create_flow_test_execution_dependencies(),
    )

    child = result.child_flow
    assert child.paused_slot_ids == ("source_a", "source_b")
    assert child.paused_slot_id is None
    summary = load_json(child.flow_run_summary_path)
    slot_statuses = {slot["slot_id"]: slot["status"] for slot in summary["slots"]}
    assert slot_statuses["source_a"] == SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE
    assert slot_statuses["source_b"] == SLOT_STATUS_PAUSED_AT_CANDIDATE_SCOPE


def test_multipart_materialization_produces_slot_keyed_paths(tmp_path: Path) -> None:
    content = b"docx-bytes"
    staging_session = UploadStagingSession(
        session_dir=tmp_path / "staging" / "session-1",
        upload_staging_session_id="session-1",
        task_run_id="task_run_20260920T010203000000Z_staging_test",
        task_id=INTERNAL_DSUR_QC_TASK_ID,
    )
    uploads = materialize_slot_uploads(
        uploads={"source": ("sample.docx", content)},
        staging_root=tmp_path / "staging",
        upload_staging_session_id="session-1",
        staging_session=staging_session,
    )

    assert set(uploads) == {"source"}
    assert uploads["source"].is_file()
    assert uploads["source"].read_bytes() == content


def test_bridge_does_not_import_intake_or_flow_orchestration() -> None:
    imported = _imported_module_names(BRIDGE_APP_PATH)
    forbidden_prefixes = (
        "runtime.request_file_intake",
        "execution_flow.document_consistency_qc.flow",
        "execution_flow.document_processing_sequence",
    )
    for module in imported:
        for prefix in forbidden_prefixes:
            assert not module.startswith(prefix)


def test_bridge_catalog_endpoint_uses_application_catalog() -> None:
    client = TestClient(create_app())
    with patch(
        "bridge.clinical_trial_doc_qc.app.load_task_catalog",
        return_value=[{"task_id": "internal_dsur_qc"}],
    ) as loader:
        response = client.get("/api/clinical-trial-doc-qc/tasks")
    assert response.status_code == 200
    assert response.json()["tasks"] == [{"task_id": "internal_dsur_qc"}]
    loader.assert_called_once()


def test_old_product_read_routes_are_not_registered() -> None:
    client = TestClient(create_app())

    catalog_response = client.get("/api/document-consistency-qc/tasks")
    task_run_response = client.get(
        f"/api/document-consistency-qc/task-runs/{TASK_RUN_ID}"
    )

    assert catalog_response.status_code == 404
    assert task_run_response.status_code == 404


def test_invalid_slot_rejected_by_application_validation_not_bridge_rules(
    tmp_path: Path,
) -> None:
    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
        upload_staging_root=tmp_path / "upload_staging",
        **_create_flow_test_execution_dependencies(),
    )
    client = TestClient(create_app(bridge_config=config))

    with patch(
        "task.clinical_trial_doc_qc.start.allocate_task_run_id",
        side_effect=AssertionError("invalid intent must not allocate TaskRun identity"),
    ):
        response = client.post(
            "/api/clinical-trial-doc-qc/task-runs",
            data={"task_id": INTERNAL_DSUR_QC_TASK_ID},
            files={
                "unexpected_slot": (
                    "sample.docx",
                    SAMPLE_DOCX.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert response.status_code == 400
    assert "task_run_id" not in response.json()
    assert response.json()["message"] in {
        "missing upload for configured slot(s): source",
        "unexpected upload slot id(s): unexpected_slot",
    }

    response = client.post(
        "/api/clinical-trial-doc-qc/task-runs",
        data={"task_id": INTERNAL_DSUR_QC_TASK_ID},
        files={
            "source": (
                "sample.docx",
                SAMPLE_DOCX.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            "unexpected_slot": (
                "extra.docx",
                SAMPLE_DOCX.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert response.status_code == 400
    assert "unexpected upload slot id(s): unexpected_slot" in response.json()["message"]

    response = client.post(
        "/api/clinical-trial-doc-qc/task-runs",
        data={"task_id": "not_installed_qc"},
        files={
            "source": (
                "sample.docx",
                SAMPLE_DOCX.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400
    assert "task_run_id" not in response.json()
    assert response.json()["message"] == "unsupported task_id: not_installed_qc"

    response = client.post(
        "/api/clinical-trial-doc-qc/task-runs",
        data={"task_id": INTERNAL_DSUR_QC_TASK_ID},
        files={},
    )
    assert response.status_code == 400
    assert not (tmp_path / "upload_staging").exists()
    assert not (tmp_path / "runs" / "task_runs").exists()


def test_bridge_rejects_dcqc_capability_id_as_task_id(tmp_path: Path) -> None:
    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
        upload_staging_root=tmp_path / "upload_staging",
        **_create_flow_test_execution_dependencies(),
    )
    client = TestClient(create_app(bridge_config=config))
    response = client.post(
        "/api/clinical-trial-doc-qc/task-runs",
        data={"task_id": INTERNAL_DSUR_CONSISTENCY_QC.capability_id},
        files={
            "source": (
                "sample.docx",
                SAMPLE_DOCX.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 400
    assert response.json()["message"] == "unsupported task_id: internal_dsur"


def test_default_project_root_resolves_to_backend_root() -> None:
    assert resolve_installed_project_root() == BACKEND_ROOT


def test_start_task_module_does_not_define_capability_configs() -> None:
    path = BACKEND_ROOT / "task" / "clinical_trial_doc_qc" / "start.py"
    source = path.read_text(encoding="utf-8")
    assert "DocumentConsistencyQcCapabilityConfig(" not in source
    assert "INTERNAL_DSUR_CONSISTENCY_QC" not in source
