"""Thin Product Task Start transport for clinical-trial document QC."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from application import build_installed_document_consistency_qc_application_composition
from artifacts.task_run import task_run_manifest_path
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.errors import (
    DocumentConsistencyQcBridgeRuntimeError,
    DocumentConsistencyQcBridgeValidationError,
)
from bridge.document_consistency_qc.upload_materialization import (
    UploadMaterializationError,
    materialize_slot_uploads,
)
from bridge.document_consistency_qc.upload_staging_session import UploadStagingSession
from execution_flow.document_consistency_qc.errors import (
    DocumentConsistencyQcFlowExecutionError,
)
from task.clinical_trial_doc_qc.start import (
    plan_installed_product_task_start,
    product_task_start_result_to_mapping,
    start_installed_product_task,
)


def run_product_task_start_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    task_id: str,
    uploads: Mapping[str, tuple[str, bytes]],
) -> dict[str, object]:
    """Materialize uploads and execute installed Product Task Start."""

    composition = build_installed_document_consistency_qc_application_composition()
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=task_id,
        upload_slot_ids=uploads,
    )

    staging_root = config.upload_staging_root or (
        config.default_workspace_root / "runs" / "upload_staging"
    )
    upload_staging_session_id = uuid4().hex
    staging_session = UploadStagingSession(
        session_dir=staging_root / upload_staging_session_id,
        upload_staging_session_id=upload_staging_session_id,
        task_run_id=planned.task_run_id,
        task_id=planned.task_id,
    )
    try:
        materialized_uploads = materialize_slot_uploads(
            uploads=uploads,
            staging_root=staging_root,
            upload_staging_session_id=upload_staging_session_id,
            staging_session=staging_session,
        )
    except UploadMaterializationError:
        raise
    except OSError as exc:
        staging_session.record_failed(str(exc))
        raise UploadMaterializationError(str(exc)) from exc

    resolved_project_root = config.project_root or config.default_workspace_root
    task_run_path = task_run_manifest_path(
        project_root=resolved_project_root,
        task_run_id=planned.task_run_id,
    )
    task_run_existed_before_start = task_run_path.is_file()

    try:
        start_result = start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs=materialized_uploads,
            project_root=config.project_root,
            projection_runtime_dependencies=config.projection_runtime_dependencies,
            evidence_source_preparation_execution_dependencies=(
                config.evidence_source_preparation_execution_dependencies
            ),
        )
    except DocumentConsistencyQcFlowExecutionError as exc:
        staging_session.record_failed(
            str(exc),
            flow_run_id=exc.flow_run_id,
            flow_run_summary_path=exc.flow_run_summary_path,
        )
        raise DocumentConsistencyQcBridgeRuntimeError(
            str(exc),
            task_run_id=(
                planned.task_run_id
                if not task_run_existed_before_start and task_run_path.is_file()
                else None
            ),
            flow_run_id=exc.flow_run_id,
            flow_run_summary_path=exc.flow_run_summary_path,
        ) from exc
    except Exception as exc:
        staging_session.record_failed(str(exc))
        task_run_id = (
            planned.task_run_id
            if not task_run_existed_before_start and task_run_path.is_file()
            else None
        )
        if task_run_id is not None:
            error_type = (
                DocumentConsistencyQcBridgeValidationError
                if isinstance(exc, ValueError)
                else DocumentConsistencyQcBridgeRuntimeError
            )
            raise error_type(str(exc), task_run_id=task_run_id) from exc
        raise

    staging_session.record_flow_created(
        flow_run_id=start_result.child_flow.flow_run_id,
        flow_run_summary_path=start_result.child_flow.flow_run_summary_path,
    )
    return product_task_start_result_to_mapping(start_result)


__all__ = [
    "run_product_task_start_request",
]
