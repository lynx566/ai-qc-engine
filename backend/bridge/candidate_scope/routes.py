"""Register Candidate Scope HTTP routes on a FastAPI app."""

from __future__ import annotations

from application.document_consistency_qc.document_read import DocumentReadError
from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig
from bridge.candidate_scope.document_service import load_candidate_scope_slot_document
from bridge.candidate_scope.errors import (
    CandidateScopeBridgeError,
    map_document_read_error,
    map_flow_resume_error,
)
from bridge.candidate_scope.next_service import run_candidate_scope_next_request
from bridge.candidate_scope.schemas import CandidateScopeNextRequest
from bridge.candidate_scope.state_service import load_candidate_scope_state
from execution_flow.document_consistency_qc.flow_loader import FlowResumeError
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse


def register_candidate_scope_routes(
    app: FastAPI,
    *,
    config: BridgeRuntimeConfig,
) -> None:
    @app.exception_handler(CandidateScopeBridgeError)
    async def _bridge_error_handler(
        _request: Request,
        exc: CandidateScopeBridgeError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "failed", "message": exc.message},
        )

    @app.exception_handler(FlowResumeError)
    async def _flow_resume_error_handler(
        _request: Request,
        exc: FlowResumeError,
    ) -> JSONResponse:
        mapped = map_flow_resume_error(exc)
        return JSONResponse(
            status_code=mapped.status_code,
            content={"status": "failed", "message": mapped.message},
        )

    @app.get("/api/candidate-scope/state")
    def get_candidate_scope_state(
        flow_run_id: str = Query(...),
    ) -> dict:
        state = load_candidate_scope_state(
            config=config,
            flow_run_id=flow_run_id,
        )
        return state.model_dump()

    @app.get("/api/candidate-scope/document")
    def get_candidate_scope_document(
        flow_run_id: str = Query(...),
        slot_id: str = Query(...),
    ) -> dict:
        try:
            return load_candidate_scope_slot_document(
                config=config,
                flow_run_id=flow_run_id,
                slot_id=slot_id,
            )
        except DocumentReadError as exc:
            mapped = map_document_read_error(exc)
            raise mapped from exc

    @app.post("/api/candidate-scope/next")
    def post_candidate_scope_next(request: CandidateScopeNextRequest) -> dict:
        result = run_candidate_scope_next_request(
            request,
            config=config,
        )
        return result.model_dump()


__all__ = ["register_candidate_scope_routes"]
