"""Targeted tests for the candidate-scope HTTP bridge."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bridge.candidate_scope.app import create_app
from runtime.io import load_json, save_json
from tests.candidate_scope_isolation import (
    SHOWCASE_SLOT_ID,
    clone_paused_canonical_flow_workspace,
    mark_canonical_flow_completed,
    minimal_bridge_runtime_config,
    prepare_paused_multi_slot_canonical_flow,
)


def _slot_state(state: dict, slot_id: str) -> dict:
    return next(item for item in state["slots"] if item["slot_id"] == slot_id)


@pytest.fixture
def client(paused_flow: tuple) -> TestClient:
    bridge_config, _flow_run_id, _slot_id = paused_flow
    return TestClient(create_app(bridge_config=bridge_config))


@pytest.fixture
def flow_run_id(paused_flow: tuple) -> str:
    return paused_flow[1]


def test_state_endpoint_returns_canonical_paused_headings(
    client: TestClient,
    flow_run_id: str,
) -> None:
    response = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["flow_id"] == "document_consistency_qc"
    assert payload["flow_run_id"] == flow_run_id
    assert payload["capability_id"] == "internal_dsur"
    assert payload["flow_status"] == "paused_at_candidate_scope"
    assert payload["can_resume"] is True
    assert len(payload["slots"]) == 1
    slot = payload["slots"][0]
    assert slot["slot_id"] == "source"
    assert slot["doc_id"].startswith("doc_")
    assert "C0017" in slot["automatic_anchor_block_ids"]
    assert payload["capability_title"] == "研发期间安全性更新报告（DSUR）"
    assert payload["content_domain_groups"] == [
        {
            "content_domain_id": "clinical_safety",
            "display_label": "临床安全性",
            "filter_job_ids": ["dsur_clinical_safety", "dsur_overview"],
        }
    ]
    assert "base_filter_run_id" not in payload
    assert "slot_id" not in payload


def test_state_current_equals_automatic(client: TestClient, flow_run_id: str) -> None:
    response = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    slot = response.json()["slots"][0]
    assert slot["current_anchor_block_ids"] == slot["automatic_anchor_block_ids"]


def test_state_multi_slot_returns_canonical_order(tmp_path: Path) -> None:
    bridge_config, flow_run_id, slot_ids = prepare_paused_multi_slot_canonical_flow(
        tmp_path
    )
    client = TestClient(create_app(bridge_config=bridge_config))

    with patch(
        "execution_flow.document_consistency_qc.flow_loader.resolve_unique_paused_candidate_scope_slot",
        side_effect=AssertionError(
            "resolve_unique_paused_candidate_scope_slot must not be used"
        ),
    ):
        response = client.get(
            "/api/candidate-scope/state",
            params={"flow_run_id": flow_run_id},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["flow_run_id"] == flow_run_id
    assert payload["capability_id"] == "dsur_updated_ib"
    assert [slot["slot_id"] for slot in payload["slots"]] == list(slot_ids)
    doc_ids = {slot["slot_id"]: slot["doc_id"] for slot in payload["slots"]}
    assert doc_ids["source_a"] != doc_ids["source_b"]
    assert payload["slots"][0]["filter_jobs"]
    assert payload["slots"][1]["filter_jobs"]


def test_get_unknown_flow_returns_not_found(tmp_path: Path) -> None:
    bridge_config = minimal_bridge_runtime_config(tmp_path)
    client = TestClient(create_app(bridge_config=bridge_config))
    response = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": "document_consistency_qc_missing_flow"},
    )
    assert response.status_code == 404
    assert response.json()["status"] == "failed"


def test_get_completed_flow_without_decision_returns_client_error(
    tmp_path: Path,
    paused_canonical_flow_baseline,
) -> None:
    bridge_config, flow_run_id, _slot_id = clone_paused_canonical_flow_workspace(
        tmp_path,
        paused_canonical_flow_baseline,
    )
    mark_canonical_flow_completed(bridge_config, flow_run_id)
    client = TestClient(create_app(bridge_config=bridge_config))

    response = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert "decision artifacts are unavailable" in payload["message"]


def test_get_completed_flow_with_decision_returns_historical_state(
    tmp_path: Path,
    paused_canonical_flow_baseline,
) -> None:
    bridge_config, flow_run_id, _slot_id = clone_paused_canonical_flow_workspace(
        tmp_path,
        paused_canonical_flow_baseline,
    )
    mark_canonical_flow_completed(
        bridge_config,
        flow_run_id,
        persist_decision=True,
    )
    client = TestClient(create_app(bridge_config=bridge_config))

    response = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["flow_status"] != "paused_at_candidate_scope"
    assert payload["can_resume"] is False
    slot = payload["slots"][0]
    assert slot["current_anchor_block_ids"] == slot["automatic_anchor_block_ids"]


def test_get_completed_flow_next_still_rejected(
    tmp_path: Path,
    paused_canonical_flow_baseline,
) -> None:
    bridge_config, flow_run_id, slot_id = clone_paused_canonical_flow_workspace(
        tmp_path,
        paused_canonical_flow_baseline,
    )
    mark_canonical_flow_completed(
        bridge_config,
        flow_run_id,
        persist_decision=True,
    )
    client = TestClient(create_app(bridge_config=bridge_config))
    state = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    ).json()
    slot = state["slots"][0]
    response = client.post(
        "/api/candidate-scope/next",
        json={
            "flow_run_id": flow_run_id,
            "slot_decisions": [
                {
                    "slot_id": slot_id,
                    "candidate_scope": [
                        {
                            "filter_job_id": job["filter_job_id"],
                            "anchor_block_ids": job["current_anchor_block_ids"],
                        }
                        for job in slot["filter_jobs"]
                    ],
                }
            ],
        },
    )
    assert response.status_code == 400
    assert "not paused_at_candidate_scope" in response.json()["message"]


def test_get_completed_flow_restores_submitted_decision_not_automatic_default(
    tmp_path: Path,
    paused_canonical_flow_baseline,
) -> None:
    bridge_config, flow_run_id, _slot_id = clone_paused_canonical_flow_workspace(
        tmp_path,
        paused_canonical_flow_baseline,
    )
    mark_canonical_flow_completed(
        bridge_config,
        flow_run_id,
        persist_decision=True,
    )
    session_dir = flow_run_id.removeprefix("document_consistency_qc_")
    decision_path = (
        bridge_config.runs_root
        / "document_consistency_qc"
        / session_dir
        / "participants"
        / "source"
        / "candidate_scope"
        / "decision.json"
    )
    decision = load_json(decision_path)
    removed_anchor = decision["candidate_selections"][0]["anchor_block_ids"][0]
    decision["candidate_selections"][0]["anchor_block_ids"] = decision[
        "candidate_selections"
    ][0]["anchor_block_ids"][1:]
    save_json(decision_path, decision)

    client = TestClient(create_app(bridge_config=bridge_config))
    response = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    slot = response.json()["slots"][0]
    assert removed_anchor in slot["automatic_anchor_block_ids"]
    assert removed_anchor not in slot["current_anchor_block_ids"]


def test_apply_route_is_not_registered(tmp_path: Path) -> None:
    bridge_config = minimal_bridge_runtime_config(tmp_path)
    client = TestClient(create_app(bridge_config=bridge_config))
    response = client.post(
        "/api/candidate-scope/apply",
        json={"flow_run_id": "document_consistency_qc_unused", "changes": []},
    )
    assert response.status_code == 404


def test_document_endpoint_returns_extract_bundle(
    client: TestClient,
    flow_run_id: str,
) -> None:
    response = client.get(
        "/api/candidate-scope/document",
        params={"flow_run_id": flow_run_id, "slot_id": SHOWCASE_SLOT_ID},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_id"].startswith("doc_")
    assert payload["content_blocks"]
    assert "bundle.json" not in response.text
    assert "participants/" not in response.text


def test_document_endpoint_multi_slot_returns_distinct_docs(tmp_path: Path) -> None:
    bridge_config, flow_run_id, slot_ids = prepare_paused_multi_slot_canonical_flow(
        tmp_path
    )
    client = TestClient(create_app(bridge_config=bridge_config))

    doc_a = client.get(
        "/api/candidate-scope/document",
        params={"flow_run_id": flow_run_id, "slot_id": slot_ids[0]},
    ).json()["doc_id"]
    doc_b = client.get(
        "/api/candidate-scope/document",
        params={"flow_run_id": flow_run_id, "slot_id": slot_ids[1]},
    ).json()["doc_id"]
    assert doc_a != doc_b


def test_document_endpoint_calls_application_boundary_not_filesystem(
    client: TestClient,
    flow_run_id: str,
) -> None:
    sentinel = {
        "doc_id": "doc_sentinel",
        "file_name": "sentinel.docx",
        "display_name": "sentinel",
        "content_blocks": [],
        "front_matter_blocks": [],
        "table_blocks": [],
    }

    with patch(
        "bridge.candidate_scope.document_service.resolve_slot_extract_bundle",
        return_value=sentinel,
    ) as resolver:
        response = client.get(
            "/api/candidate-scope/document",
            params={"flow_run_id": flow_run_id, "slot_id": SHOWCASE_SLOT_ID},
        )

    assert response.status_code == 200
    assert response.json()["doc_id"] == "doc_sentinel"
    resolver.assert_called_once()


def test_unified_bridge_app_exposes_product_and_candidate_scope_routes(
    tmp_path: Path,
) -> None:
    from bridge.clinical_trial_doc_qc.app import create_app as create_unified_app
    from bridge.document_consistency_qc.bridge_runtime import (
        DocumentConsistencyQcBridgeConfig,
    )

    bridge_config, flow_run_id, _slot_id = prepare_paused_multi_slot_canonical_flow(
        tmp_path / "multi"
    )
    dcqc_bridge_config = DocumentConsistencyQcBridgeConfig(
        default_workspace_root=bridge_config.workspace_root,
        project_root=bridge_config.workspace_root,
    )
    client = TestClient(
        create_unified_app(
            bridge_config=dcqc_bridge_config,
            candidate_scope_config=bridge_config,
        )
    )

    catalog = client.get("/api/clinical-trial-doc-qc/tasks")
    assert catalog.status_code == 200
    assert catalog.json()["tasks"]

    state = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    )
    assert state.status_code == 200
    assert len(state.json()["slots"]) == 2
