"""Candidate Scope bridge must not depend on DASHSCOPE_API_KEY during pytest."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bridge.candidate_scope.app import create_app
from tests.candidate_scope_isolation import prepare_paused_canonical_flow
from tests.test_candidate_scope_workspace_and_next import _next_payload


def test_paused_setup_and_resume_work_without_dashscope_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    bridge_config, flow_run_id, slot_id = prepare_paused_canonical_flow(tmp_path)
    client = TestClient(create_app(bridge_config=bridge_config))

    state = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    )
    assert state.status_code == 200

    payload = _next_payload(
        flow_run_id=flow_run_id,
        state=state.json(),
        slot_ids=(slot_id,),
    )
    response = client.post("/api/candidate-scope/next", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
