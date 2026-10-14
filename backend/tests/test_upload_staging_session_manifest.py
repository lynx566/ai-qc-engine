"""Tests for bridge-owned upload staging session manifests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.errors import (
    DocumentConsistencyQcBridgeRuntimeError,
)
from bridge.document_consistency_qc.product_task_start_service import (
    run_product_task_start_request,
)
from bridge.document_consistency_qc.upload_materialization import (
    UploadMaterializationError,
    materialize_slot_uploads,
)
from bridge.document_consistency_qc.upload_staging_session import (
    OUTCOME_FAILED,
    OUTCOME_FLOW_CREATED,
    OUTCOME_PENDING,
    UPLOAD_STAGING_SESSION_FILENAME,
    UPLOAD_STAGING_SESSION_SCHEMA_VERSION,
    UploadStagingSession,
    validate_upload_staging_session_manifest,
)
from capability import INTERNAL_DSUR_CONSISTENCY_QC
from runtime.io import load_json
from task.clinical_trial_doc_qc.task_ids import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
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


def _bridge_config(tmp_path: Path) -> DocumentConsistencyQcBridgeConfig:
    kwargs = clinical_flow_invocation_kwargs()
    return DocumentConsistencyQcBridgeConfig(
        default_workspace_root=BACKEND_ROOT,
        project_root=tmp_path,
        upload_staging_root=tmp_path / "upload_staging",
        projection_runtime_dependencies=kwargs["projection_runtime_dependencies"],
        evidence_source_preparation_execution_dependencies=kwargs[
            "evidence_source_preparation_execution_dependencies"
        ],
    )


def _staging_session_dirs(staging_root: Path) -> list[Path]:
    if not staging_root.is_dir():
        return []
    return sorted(path for path in staging_root.iterdir() if path.is_dir())


def _read_manifest(session_dir: Path) -> dict[str, object]:
    return load_json(session_dir / UPLOAD_STAGING_SESSION_FILENAME)


def test_initial_manifest_written_when_session_directory_created(
    tmp_path: Path,
) -> None:
    session = UploadStagingSession(
        session_dir=tmp_path / "upload_staging" / "session-initial",
        upload_staging_session_id="session-initial",
        task_run_id="task_run_20260920T010203000000Z_staging_initial",
        task_id=INTERNAL_DSUR_QC_TASK_ID,
    )
    session.session_dir.mkdir(parents=True)
    session.initialize()

    manifest = session.read_manifest()
    assert manifest["schema_version"] == UPLOAD_STAGING_SESSION_SCHEMA_VERSION
    assert manifest["upload_staging_session_id"] == "session-initial"
    assert manifest["created_at"]
    assert manifest["task_id"] == INTERNAL_DSUR_QC_TASK_ID
    assert manifest["task_run_id"] == "task_run_20260920T010203000000Z_staging_initial"
    assert "capability_id" not in manifest
    assert manifest["outcome"] == OUTCOME_PENDING
    assert manifest["slots"] == []
    assert manifest["flow_run_id"] is None
    assert (session.session_dir / UPLOAD_STAGING_SESSION_FILENAME).is_file()


def test_successful_single_slot_create_flow_records_manifest(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    config = _bridge_config(tmp_path)

    result = run_product_task_start_request(
        config=config,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        uploads={"source": (SAMPLE_DOCX.name, SAMPLE_DOCX.read_bytes())},
    )
    assert result["task_run_id"].startswith("task_run_")

    session_dirs = _staging_session_dirs(config.upload_staging_root)
    assert len(session_dirs) == 1
    manifest = _read_manifest(session_dirs[0])
    assert manifest["outcome"] == OUTCOME_FLOW_CREATED
    flow_run_id = manifest["flow_run_id"]
    assert isinstance(flow_run_id, str) and flow_run_id.startswith("document_consistency_qc_")
    assert manifest["flow_run_summary_path"] is not None
    assert manifest["failure_message"] is None
    assert manifest["slots"] == [
        {"slot_id": "source", "original_file_name": SAMPLE_DOCX.name}
    ]
    task_run_paths = list((tmp_path / "runs" / "task_runs").glob("*/task_run.json"))
    assert len(task_run_paths) == 1
    task_run = load_json(task_run_paths[0])
    assert task_run["task_id"] == INTERNAL_DSUR_QC_TASK_ID
    assert "capability_id" not in task_run
    assert manifest["task_id"] == task_run["task_id"]
    assert manifest["task_run_id"] == task_run["task_run_id"]
    assert result == {"task_run_id": task_run["task_run_id"]}
    summary = load_json(Path(str(manifest["flow_run_summary_path"])))
    assert summary["capability_id"] == INTERNAL_DSUR_CONSISTENCY_QC.capability_id
    assert task_run["task_id"] != summary["capability_id"]
    assert task_run["flow_runs"] == [
        {
            "flow_id": "document_consistency_qc",
            "flow_run_id": flow_run_id,
        }
    ]


def test_successful_multi_slot_create_flow_records_one_manifest(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    assert SECOND_SAMPLE_DOCX.is_file()
    config = _bridge_config(tmp_path)

    result = run_product_task_start_request(
        config=config,
        task_id=DSUR_UPDATED_IB_QC_TASK_ID,
        uploads={
            "source_a": (SAMPLE_DOCX.name, SAMPLE_DOCX.read_bytes()),
            "source_b": (SECOND_SAMPLE_DOCX.name, SECOND_SAMPLE_DOCX.read_bytes()),
        },
    )

    session_dirs = _staging_session_dirs(config.upload_staging_root)
    assert len(session_dirs) == 1
    manifest = _read_manifest(session_dirs[0])
    assert manifest["outcome"] == OUTCOME_FLOW_CREATED
    assert manifest["flow_run_id"] is not None
    assert result.keys() == {"task_run_id"}
    assert {slot["slot_id"] for slot in manifest["slots"]} == {"source_a", "source_b"}
    assert len(manifest["slots"]) == 2
    assert manifest["task_id"] == DSUR_UPDATED_IB_QC_TASK_ID
    assert "capability_id" not in manifest


def test_upload_staging_schema_0_1_0_is_rejected() -> None:
    legacy = {
        "schema_version": "0.1.0",
        "upload_staging_session_id": "legacy",
        "created_at": "2026-09-20T01:02:03Z",
        "updated_at": "2026-09-20T01:02:04Z",
        "capability_id": "internal_dsur",
        "outcome": OUTCOME_PENDING,
        "slots": [],
        "flow_run_id": None,
        "flow_run_summary_path": None,
        "failure_message": None,
    }
    with pytest.raises(ValueError, match="capability_id"):
        validate_upload_staging_session_manifest(legacy)


def test_pre_allocation_validation_failure_records_failed_manifest(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    config = _bridge_config(tmp_path)

    with (
        patch(
            "bridge.document_consistency_qc.product_task_start_service.start_installed_product_task",
            side_effect=ValueError("missing upload for configured slot(s): source"),
        ),
        pytest.raises(ValueError, match="missing upload"),
    ):
        run_product_task_start_request(
            config=config,
            task_id=INTERNAL_DSUR_QC_TASK_ID,
            uploads={"source": (SAMPLE_DOCX.name, SAMPLE_DOCX.read_bytes())},
        )

    session_dirs = _staging_session_dirs(config.upload_staging_root)
    assert len(session_dirs) == 1
    manifest = _read_manifest(session_dirs[0])
    assert manifest["outcome"] == OUTCOME_FAILED
    assert manifest["flow_run_id"] is None
    assert manifest["flow_run_summary_path"] is None
    assert (
        manifest["failure_message"] == "missing upload for configured slot(s): source"
    )
    assert manifest["task_id"] == INTERNAL_DSUR_QC_TASK_ID
    assert manifest["task_run_id"]
    assert "capability_id" not in manifest
    assert not (tmp_path / "runs" / "task_runs").exists()


def test_post_allocation_failure_records_structured_flow_identity_in_manifest(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    config = _bridge_config(tmp_path)

    def _fail_after_asserting_task_membership(**_kwargs):
        task_run_paths = list((tmp_path / "runs" / "task_runs").glob("*/task_run.json"))
        assert len(task_run_paths) == 1
        task_run = load_json(task_run_paths[0])
        assert len(task_run["flow_runs"]) == 1
        raise RuntimeError("checkpoint failed")

    with (
        patch(
            "execution_flow.document_consistency_qc.flow._run_canonical_slot_through_candidate_scope_checkpoint",
            side_effect=_fail_after_asserting_task_membership,
        ),
        pytest.raises(DocumentConsistencyQcBridgeRuntimeError) as exc_info,
    ):
        run_product_task_start_request(
            config=config,
            task_id=INTERNAL_DSUR_QC_TASK_ID,
            uploads={"source": (SAMPLE_DOCX.name, SAMPLE_DOCX.read_bytes())},
        )

    err = exc_info.value
    assert err.flow_run_id is not None
    assert err.flow_run_id.startswith("document_consistency_qc_")
    assert err.flow_run_summary_path is not None
    assert err.flow_run_summary_path.name == "flow_run_summary.json"

    session_dirs = _staging_session_dirs(config.upload_staging_root)
    assert len(session_dirs) == 1
    manifest = _read_manifest(session_dirs[0])
    assert manifest["outcome"] == OUTCOME_FAILED
    assert manifest["flow_run_id"] == err.flow_run_id
    assert manifest["flow_run_summary_path"] == err.flow_run_summary_path.as_posix()
    assert manifest["failure_message"] == "checkpoint failed"


def test_partial_materialization_failure_records_only_materialized_slots(
    tmp_path: Path,
) -> None:
    staging_root = tmp_path / "upload_staging"
    staging_session = UploadStagingSession(
        session_dir=staging_root / "session-partial",
        upload_staging_session_id="session-partial",
        task_run_id="task_run_20260920T010203000000Z_staging_partial",
        task_id=INTERNAL_DSUR_QC_TASK_ID,
    )

    with pytest.raises(UploadMaterializationError, match="must be a slot_id"):
        materialize_slot_uploads(
            uploads={
                "source_a": ("a.docx", b"first"),
                "bad-slot!": ("b.docx", b"second"),
            },
            staging_root=staging_root,
            upload_staging_session_id="session-partial",
            staging_session=staging_session,
        )

    manifest = staging_session.read_manifest()
    assert manifest["outcome"] == OUTCOME_FAILED
    assert manifest["flow_run_id"] is None
    assert manifest["slots"] == [
        {"slot_id": "source_a", "original_file_name": "a.docx"}
    ]
    assert (staging_root / "session-partial" / "source_a" / "a.docx").is_file()
    assert not (staging_root / "session-partial" / "bad-slot!").exists()


def test_duplicate_upload_attempts_keep_independent_manifest_outcomes(
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    config = _bridge_config(tmp_path)
    uploads = {"source": (SAMPLE_DOCX.name, SAMPLE_DOCX.read_bytes())}

    first_result = run_product_task_start_request(
        config=config,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        uploads=uploads,
    )

    with (
        patch(
            "execution_flow.document_consistency_qc.flow._run_canonical_slot_through_candidate_scope_checkpoint",
            side_effect=RuntimeError("second attempt failed"),
        ),
        pytest.raises(DocumentConsistencyQcBridgeRuntimeError),
    ):
        run_product_task_start_request(
            config=config,
            task_id=INTERNAL_DSUR_QC_TASK_ID,
            uploads=uploads,
        )

    session_dirs = _staging_session_dirs(config.upload_staging_root)
    assert len(session_dirs) == 2

    manifests = [_read_manifest(session_dir) for session_dir in session_dirs]
    flow_created = [m for m in manifests if m["outcome"] == OUTCOME_FLOW_CREATED]
    failed = [m for m in manifests if m["outcome"] == OUTCOME_FAILED]
    assert len(flow_created) == 1
    assert len(failed) == 1
    assert flow_created[0]["task_run_id"] == first_result["task_run_id"]
    assert failed[0]["flow_run_id"] is not None
    assert (
        flow_created[0]["upload_staging_session_id"]
        != failed[0]["upload_staging_session_id"]
    )
