"""Tests for post-allocation Document Consistency QC flow failure propagation."""

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
from application.document_consistency_qc.composition import (
    DocumentConsistencyQcApplicationComposition,
)
from application.task_run import create_task_run
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_FILENAME,
)
from artifacts.task_run import load_task_run_manifest, task_run_manifest_path
from bridge.clinical_trial_doc_qc.app import create_app
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.errors import (
    DocumentConsistencyQcBridgeRuntimeError,
)
from bridge.document_consistency_qc.product_task_start_service import (
    run_product_task_start_request,
)
from capability import INTERNAL_DSUR_CONSISTENCY_QC
from execution_flow.document_consistency_qc.contracts import (
    DocumentConsistencyQcParticipantRunInput,
)
from execution_flow.document_consistency_qc.errors import (
    DocumentConsistencyQcFlowExecutionError,
)
from execution_flow.document_consistency_qc.flow import run_document_consistency_qc_flow
from operations.prepare_analysis import PrepareAnalysisRequestOptions
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from plugins.clinical_trial_doc.prepare_analysis.config import (
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    ClinicalPreparePrivacyConfig,
)
from runtime.io import load_json
from task.clinical_trial_doc_qc import (
    INTERNAL_DSUR_QC_TASK_ID,
    PlannedProductTaskStart,
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
TASK_RUN_ID = "task_run_20260920T010203000000Z_failure_test"


def _planned_for_failure_test(composition) -> PlannedProductTaskStart:
    resolved = validate_installed_task_start_intent(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    return PlannedProductTaskStart(
        task_run_id=TASK_RUN_ID,
        task_id=resolved.task_definition.task_id,
        resolved=resolved,
    )


def _create_flow_test_execution_dependencies() -> dict[str, object]:
    kwargs = clinical_flow_invocation_kwargs()
    return {
        "projection_runtime_dependencies": kwargs["projection_runtime_dependencies"],
        "evidence_source_preparation_execution_dependencies": kwargs[
            "evidence_source_preparation_execution_dependencies"
        ],
    }


def test_pause_path_post_allocation_failure_carries_flow_identity(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()

    task_run_path = task_run_manifest_path(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
    )

    def _fail_after_asserting_membership(**_kwargs):
        assert task_run_path.is_file()
        raise RuntimeError("checkpoint failed")

    with (
        patch(
            "execution_flow.document_consistency_qc.flow._run_canonical_slot_through_candidate_scope_checkpoint",
            side_effect=_fail_after_asserting_membership,
        ),
        pytest.raises(DocumentConsistencyQcFlowExecutionError) as exc_info,
    ):
        composition = build_installed_document_consistency_qc_application_composition()
        start_installed_product_task(
            composition=composition,
            planned=_planned_for_failure_test(composition),
            slot_inputs={"source": SAMPLE_DOCX},
            project_root=tmp_path,
            **_create_flow_test_execution_dependencies(),
        )

    err = exc_info.value
    assert err.flow_run_id.startswith("document_consistency_qc_")
    assert err.flow_run_summary_path.name == "flow_run_summary.json"
    assert err.flow_run_summary_path.parent.is_dir()
    assert isinstance(err.__cause__, RuntimeError)
    assert str(err.__cause__) == "checkpoint failed"


def test_pause_path_post_allocation_failure_still_persists_best_effort_summary(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()

    with (
        patch(
            "execution_flow.document_consistency_qc.flow._run_canonical_slot_through_candidate_scope_checkpoint",
            side_effect=RuntimeError("checkpoint failed"),
        ),
        patch(
            "execution_flow.document_consistency_qc.errors.persist_flow_run_summary_best_effort",
        ) as best_effort,
        pytest.raises(DocumentConsistencyQcFlowExecutionError),
    ):
        composition = build_installed_document_consistency_qc_application_composition()
        start_installed_product_task(
            composition=composition,
            planned=_planned_for_failure_test(composition),
            slot_inputs={"source": SAMPLE_DOCX},
            project_root=tmp_path,
            **_create_flow_test_execution_dependencies(),
        )

    best_effort.assert_called_once()


def test_membership_attach_failure_stops_before_stages_without_flow_summary(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()

    class ParentLineageEstablishmentError(RuntimeError):
        pass

    def _stage_must_not_start(**_kwargs):
        raise AssertionError("child stage started after membership callback failure")

    with (
        patch(
            "task.clinical_trial_doc_qc.start.attach_flow_run",
            side_effect=ParentLineageEstablishmentError("task membership write failed"),
        ),
        patch(
            "execution_flow.document_consistency_qc.flow._run_canonical_slot_through_candidate_scope_checkpoint",
            side_effect=_stage_must_not_start,
        ),
        pytest.raises(
            ParentLineageEstablishmentError,
            match="task membership write failed",
        ),
    ):
        composition = build_installed_document_consistency_qc_application_composition()
        start_installed_product_task(
            composition=composition,
            planned=_planned_for_failure_test(composition),
            slot_inputs={"source": SAMPLE_DOCX},
            project_root=tmp_path,
            **_create_flow_test_execution_dependencies(),
        )

    flow_dirs = list((tmp_path / "runs" / "document_consistency_qc").iterdir())
    assert len(flow_dirs) == 1
    assert not (flow_dirs[0] / FLOW_RUN_SUMMARY_FILENAME).exists()
    task_run_path = task_run_manifest_path(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
    )
    assert task_run_path.is_file()
    task_run = load_task_run_manifest(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
    )
    assert task_run["flow_runs"] == []


def test_pre_allocation_validation_failure_has_no_flow_identity(
    tmp_path: Path,
) -> None:
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)

    with pytest.raises(ValueError, match="missing upload"):
        run_document_consistency_qc_flow(
            project_root=tmp_path,
            capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
            uploads={},
            participant_inputs={
                "source": DocumentConsistencyQcParticipantRunInput(
                    prepare_analysis_request_options=PrepareAnalysisRequestOptions(
                        ClinicalPreparePrivacyConfig.identity()
                    ),
                ),
            },
            prepare_analysis_config_registry=registry,
            **clinical_flow_invocation_kwargs(),
        )


def test_product_start_bridge_post_flow_allocation_failure_preserves_flow_identity(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    flow_summary_path = (
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / "20260912_000000_000000Z"
        / "flow_run_summary.json"
    )
    flow_run_id = "document_consistency_qc_20260912_000000_000000Z"

    def _raise_flow_execution_error(
        *,
        composition: DocumentConsistencyQcApplicationComposition,
        planned: object,
        slot_inputs: object,
        **kwargs: object,
    ) -> object:
        raise DocumentConsistencyQcFlowExecutionError(
            "checkpoint failed",
            flow_run_id=flow_run_id,
            flow_run_summary_path=flow_summary_path,
        )

    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
        upload_staging_root=tmp_path / "upload_staging",
    )
    with (
        patch(
            "bridge.document_consistency_qc.product_task_start_service.start_installed_product_task",
            side_effect=_raise_flow_execution_error,
        ),
        pytest.raises(DocumentConsistencyQcBridgeRuntimeError) as exc_info,
    ):
        run_product_task_start_request(
            config=config,
            task_id=INTERNAL_DSUR_QC_TASK_ID,
            uploads={"source": (SAMPLE_DOCX.name, SAMPLE_DOCX.read_bytes())},
        )

    err = exc_info.value
    assert err.flow_run_id == flow_run_id
    assert err.flow_run_summary_path == flow_summary_path
    assert isinstance(err.__cause__, DocumentConsistencyQcFlowExecutionError)


def test_http_product_start_failure_after_task_creation_retains_task_identity(
    tmp_path: Path,
) -> None:
    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
        upload_staging_root=tmp_path / "upload_staging",
        **_create_flow_test_execution_dependencies(),
    )
    client = TestClient(create_app(bridge_config=config))

    with (
        patch(
            "task.clinical_trial_doc_qc.start.allocate_task_run_id",
            return_value=TASK_RUN_ID,
        ),
        patch(
            "execution_flow.document_consistency_qc.flow._run_canonical_slot_through_candidate_scope_checkpoint",
            side_effect=RuntimeError("checkpoint failed"),
        ),
    ):
        response = client.post(
            "/api/clinical-trial-doc-qc/task-runs",
            data={"task_id": INTERNAL_DSUR_QC_TASK_ID},
            files={
                "source": (
                    SAMPLE_DOCX.name,
                    SAMPLE_DOCX.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 500
    assert response.json()["task_run_id"] == TASK_RUN_ID

    task_response = client.get(
        f"/api/clinical-trial-doc-qc/task-runs/{TASK_RUN_ID}"
    )
    assert task_response.status_code == 200
    task = task_response.json()
    assert task["flow_runs"][0]["flow_id"] == "document_consistency_qc"
    assert task["state"]["flow_outcome"] == "failed"
    assert task["state"]["result_available"] is False
    flow_run_id = task["flow_runs"][0]["flow_run_id"]
    flow_summary = load_json(
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / flow_run_id.removeprefix("document_consistency_qc_")
        / "flow_run_summary.json"
    )
    assert "task_run_id" not in flow_summary


def test_http_post_create_value_error_keeps_400_and_task_identity(
    tmp_path: Path,
) -> None:
    def _create_task_then_fail(*, planned, project_root, **_kwargs):
        create_task_run(
            project_root=project_root,
            task_run_id=planned.task_run_id,
            task_id=planned.task_id,
        )
        raise ValueError("post-create validation failed")

    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
        upload_staging_root=tmp_path / "upload_staging",
    )
    client = TestClient(create_app(bridge_config=config))
    with (
        patch(
            "task.clinical_trial_doc_qc.start.allocate_task_run_id",
            return_value=TASK_RUN_ID,
        ),
        patch(
            "bridge.document_consistency_qc.product_task_start_service.start_installed_product_task",
            side_effect=_create_task_then_fail,
        ),
    ):
        response = client.post(
            "/api/clinical-trial-doc-qc/task-runs",
            data={"task_id": INTERNAL_DSUR_QC_TASK_ID},
            files={"source": (SAMPLE_DOCX.name, SAMPLE_DOCX.read_bytes())},
        )

    assert response.status_code == 400
    assert response.json() == {
        "status": "failed",
        "message": "post-create validation failed",
        "task_run_id": TASK_RUN_ID,
    }


def test_http_task_identity_collision_is_not_attributed_to_new_start(
    tmp_path: Path,
) -> None:
    create_task_run(
        project_root=tmp_path,
        task_run_id=TASK_RUN_ID,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
    )
    config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
        upload_staging_root=tmp_path / "upload_staging",
    )
    client = TestClient(create_app(bridge_config=config))
    with patch(
        "task.clinical_trial_doc_qc.start.allocate_task_run_id",
        return_value=TASK_RUN_ID,
    ):
        response = client.post(
            "/api/clinical-trial-doc-qc/task-runs",
            data={"task_id": INTERNAL_DSUR_QC_TASK_ID},
            files={"source": (SAMPLE_DOCX.name, SAMPLE_DOCX.read_bytes())},
        )

    assert response.status_code == 500
    assert "task_run_id" not in response.json()
