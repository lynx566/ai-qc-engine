"""Thin FastAPI app for local candidate-scope bridge."""

from __future__ import annotations

from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig
from bridge.candidate_scope.routes import register_candidate_scope_routes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app(
    *,
    bridge_config: BridgeRuntimeConfig,
) -> FastAPI:
    """Register Candidate Scope routes using caller-owned runtime configuration."""
    app = FastAPI(title="Candidate Scope Bridge", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_candidate_scope_routes(app, config=bridge_config)
    return app
