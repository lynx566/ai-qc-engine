"""FastAPI composition root for the Clinical Trial Document QC Product HTTP bridge."""

from __future__ import annotations

from pathlib import Path

from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig
from bridge.candidate_scope.routes import register_candidate_scope_routes
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.catalog_service import load_task_catalog
from bridge.document_consistency_qc.errors import (
    DocumentConsistencyQcBridgeError,
    DocumentConsistencyQcBridgeRuntimeError,
    DocumentConsistencyQcBridgeValidationError,
)
from bridge.document_consistency_qc.finding_review_schemas import (
    FindingReviewPatchRequest,
)
from bridge.document_consistency_qc.finding_review_service import (
    load_finding_review_request,
    patch_finding_review_request,
)
from bridge.document_consistency_qc.product_task_start_service import (
    run_product_task_start_request,
)
from bridge.document_consistency_qc.result_service import load_flow_result_request
from bridge.document_consistency_qc.qc_report_service import generate_qc_report_download
from bridge.document_consistency_qc.source_annotation_schemas import (
    SourceAnnotationCreateRequest,
    SourceAnnotationUpdateRequest,
)
from bridge.document_consistency_qc.source_annotation_service import (
    create_source_annotation_request,
    delete_source_annotation_request,
    delete_source_annotations_by_kind_request,
    load_source_annotations_request,
    update_source_annotation_request,
)
from bridge.document_consistency_qc.task_run_service import load_task_run_page_request
from bridge.document_consistency_qc.upload_materialization import (
    UploadMaterializationError,
)
from fastapi import FastAPI, Form, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import UploadFile

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _default_bridge_config() -> DocumentConsistencyQcBridgeConfig:
    return DocumentConsistencyQcBridgeConfig(default_workspace_root=BACKEND_ROOT)


def _candidate_scope_config_from_bridge_config(
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> BridgeRuntimeConfig:
    project_root = bridge_config.project_root or bridge_config.default_workspace_root
    return BridgeRuntimeConfig(
        workspace_root=project_root,
        runs_root=project_root / "runs",
        git_root=bridge_config.default_workspace_root.parent,
        projection_runtime_dependencies=bridge_config.projection_runtime_dependencies,
        evidence_source_preparation_execution_dependencies=(
            bridge_config.evidence_source_preparation_execution_dependencies
        ),
    )


async def _extract_slot_uploads(request: Request) -> dict[str, tuple[str, bytes]]:
    form = await request.form()
    uploads: dict[str, tuple[str, bytes]] = {}
    for field_name, field_value in form.multi_items():
        if field_name == "task_id":
            continue
        if not isinstance(field_value, UploadFile):
            continue
        filename = field_value.filename or ""
        content = await field_value.read()
        uploads[field_name] = (filename, content)
    return uploads


def create_app(
    *,
    bridge_config: DocumentConsistencyQcBridgeConfig | None = None,
    candidate_scope_config: BridgeRuntimeConfig | None = None,
) -> FastAPI:
    resolved_bridge_config = bridge_config or _default_bridge_config()
    resolved_candidate_scope_config = (
        candidate_scope_config
        or _candidate_scope_config_from_bridge_config(resolved_bridge_config)
    )
    app = FastAPI(title="Clinical Trial Document QC Bridge", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @app.exception_handler(DocumentConsistencyQcBridgeError)
    async def _bridge_error_handler(
        _request: Request,
        exc: DocumentConsistencyQcBridgeError,
    ) -> JSONResponse:
        content: dict[str, object] = {
            "status": "failed",
            "message": exc.message,
        }
        if exc.task_run_id is not None:
            content["task_run_id"] = exc.task_run_id
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )

    @app.get("/api/clinical-trial-doc-qc/tasks")
    def get_task_catalog() -> dict[str, object]:
        return {"tasks": load_task_catalog()}

    @app.get("/api/clinical-trial-doc-qc/task-runs/{task_run_id}")
    def get_task_run_page(task_run_id: str) -> dict[str, object]:
        try:
            return load_task_run_page_request(
                config=resolved_bridge_config,
                task_run_id=task_run_id,
            )
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    @app.get(
        "/api/clinical-trial-doc-qc/task-runs/{task_run_id}/qc-report",
        response_class=Response,
    )
    def get_qc_report(task_run_id: str) -> Response:
        download = generate_qc_report_download(
            config=resolved_bridge_config,
            task_run_id=task_run_id,
        )
        return Response(
            content=download.pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": download.content_disposition,
                "Cache-Control": "no-store",
            },
        )

    @app.get("/api/document-consistency-qc/result")
    def get_flow_result(
        flow_run_id: str = Query(...),
    ) -> dict[str, object]:
        try:
            return load_flow_result_request(
                config=resolved_bridge_config,
                flow_run_id=flow_run_id,
            )
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    @app.get("/api/document-consistency-qc/finding-review")
    def get_finding_review(
        flow_run_id: str = Query(...),
    ) -> dict[str, object]:
        try:
            return load_finding_review_request(
                config=resolved_bridge_config,
                flow_run_id=flow_run_id,
            )
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    @app.get("/api/document-consistency-qc/source-annotations")
    def get_source_annotations(
        flow_run_id: str = Query(...),
    ) -> dict[str, object]:
        try:
            return load_source_annotations_request(
                config=resolved_bridge_config,
                flow_run_id=flow_run_id,
            )
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    @app.post("/api/document-consistency-qc/source-annotations")
    def post_source_annotation(
        request: SourceAnnotationCreateRequest,
    ) -> dict[str, object]:
        try:
            return create_source_annotation_request(
                config=resolved_bridge_config,
                flow_run_id=request.flow_run_id,
                anchor=request.anchor.model_dump(),
                range=request.range.model_dump() if request.range is not None else None,
                kind=request.kind,
                content=request.content,
                replacement_text=request.replacement_text,
            )
        except ValueError as exc:
            raise DocumentConsistencyQcBridgeValidationError(str(exc)) from exc
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    @app.patch("/api/document-consistency-qc/source-annotations")
    def patch_source_annotation(
        request: SourceAnnotationUpdateRequest,
    ) -> dict[str, object]:
        try:
            return update_source_annotation_request(
                config=resolved_bridge_config,
                flow_run_id=request.flow_run_id,
                annotation_id=request.annotation_id,
                content=request.content,
                replacement_text=request.replacement_text,
            )
        except ValueError as exc:
            raise DocumentConsistencyQcBridgeValidationError(str(exc)) from exc
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    @app.delete("/api/document-consistency-qc/source-annotations")
    def delete_source_annotation_route(
        flow_run_id: str = Query(...),
        annotation_id: str = Query(...),
    ) -> dict[str, object]:
        try:
            return delete_source_annotation_request(
                config=resolved_bridge_config,
                flow_run_id=flow_run_id,
                annotation_id=annotation_id,
            )
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    @app.delete("/api/document-consistency-qc/source-annotations/by-kind")
    def delete_source_annotations_by_kind_route(
        flow_run_id: str = Query(...),
        doc_id: str = Query(...),
        kind: str = Query(...),
    ) -> dict[str, object]:
        try:
            return delete_source_annotations_by_kind_request(
                config=resolved_bridge_config,
                flow_run_id=flow_run_id,
                doc_id=doc_id,
                kind=kind,
            )
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    @app.patch("/api/document-consistency-qc/finding-review")
    def patch_finding_review(
        request: FindingReviewPatchRequest,
    ) -> dict[str, object]:
        try:
            return patch_finding_review_request(
                config=resolved_bridge_config,
                flow_run_id=request.flow_run_id,
                finding_id=request.finding_id,
                decision=request.decision,
                resolved=request.resolved,
                marked=request.marked,
                note=request.note if "note" in request.model_fields_set else ...,
            )
        except ValueError as exc:
            raise DocumentConsistencyQcBridgeValidationError(str(exc)) from exc
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    @app.post("/api/clinical-trial-doc-qc/task-runs")
    async def post_start_product_task(
        request: Request,
        task_id: str = Form(...),
    ) -> dict[str, object]:
        try:
            uploads = await _extract_slot_uploads(request)
            return run_product_task_start_request(
                config=resolved_bridge_config,
                task_id=task_id,
                uploads=uploads,
            )
        except UploadMaterializationError as exc:
            raise DocumentConsistencyQcBridgeValidationError(str(exc)) from exc
        except ValueError as exc:
            raise DocumentConsistencyQcBridgeValidationError(str(exc)) from exc
        except DocumentConsistencyQcBridgeError:
            raise
        except Exception as exc:
            raise DocumentConsistencyQcBridgeRuntimeError(str(exc)) from exc

    register_candidate_scope_routes(
        app,
        config=resolved_candidate_scope_config,
    )

    return app


app = create_app()
