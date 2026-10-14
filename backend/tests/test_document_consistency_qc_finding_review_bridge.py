"""Targeted tests for Document Consistency QC finding review HTTP bridge."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bridge.clinical_trial_doc_qc.app import create_app
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from tests.test_internal_result_read import (
    _default_extract_blocks,
    _write_minimal_internal_result_fixture,
)


@pytest.fixture
def bridge_config(tmp_path: Path) -> DocumentConsistencyQcBridgeConfig:
    return DocumentConsistencyQcBridgeConfig(
        default_workspace_root=tmp_path,
        project_root=tmp_path,
    )


@pytest.fixture
def client(bridge_config: DocumentConsistencyQcBridgeConfig) -> TestClient:
    return TestClient(create_app(bridge_config=bridge_config))


def _write_fixture(tmp_path: Path) -> str:
    return _write_minimal_internal_result_fixture(
        tmp_path,
        plan_jobs=[
            {
                "comparison_mode_id": "scope_local",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [
                    {
                        "finding_id": "L001",
                        "label": "fail",
                        "conclusion": "issue",
                        "source_sentence_aliases": ["T0001"],
                    },
                    {
                        "finding_id": "L002",
                        "label": "need_review",
                        "conclusion": "maybe",
                        "source_sentence_aliases": ["T0001"],
                    },
                ],
            }
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            }
        ],
        extract_blocks=_default_extract_blocks(),
    )


def test_get_missing_artifact_returns_empty_state(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    response = client.get(
        "/api/document-consistency-qc/finding-review",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["flow_run_id"] == flow_run_id
    assert payload["findings"] == {}


def test_patch_resolved_marked_and_note(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)

    resolved = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L001",
            "resolved": True,
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["findings"]["L001"]["decision"] == "confirmed"
    assert resolved.json()["findings"]["L001"]["marked"] is False

    marked = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "marked": True,
        },
    )
    assert marked.status_code == 200
    assert marked.json()["findings"]["L002"]["marked"] is True
    assert marked.json()["findings"]["L002"]["decision"] == "pending"

    note = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "note": "follow up",
        },
    )
    assert note.status_code == 200
    assert note.json()["findings"]["L002"]["note"] == "follow up"
    assert note.json()["findings"]["L002"]["marked"] is True

    clear_note = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "note": "",
        },
    )
    assert clear_note.status_code == 200
    assert "note" not in clear_note.json()["findings"]["L002"]
    assert clear_note.json()["findings"]["L002"]["marked"] is True

    unresolved = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L001",
            "resolved": False,
        },
    )
    assert unresolved.status_code == 200
    assert "L001" not in unresolved.json()["findings"]


def test_patch_clear_note_only_on_marked_finding(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)

    marked = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "marked": True,
        },
    )
    assert marked.status_code == 200

    noted = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "note": "follow up",
        },
    )
    assert noted.status_code == 200
    assert noted.json()["findings"]["L002"]["note"] == "follow up"

    cleared = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "note": "",
        },
    )
    assert cleared.status_code == 200
    payload = cleared.json()["findings"]["L002"]
    assert payload["marked"] is True
    assert "note" not in payload


def test_patch_resolved_only_does_not_change_marked(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)

    client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "marked": True,
        },
    )
    response = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "resolved": True,
        },
    )
    payload = response.json()["findings"]["L002"]
    assert payload["decision"] == "confirmed"
    assert payload["marked"] is True


def test_patch_ignored_decision(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)

    ignored = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "decision": "ignored",
        },
    )
    assert ignored.status_code == 200
    assert ignored.json()["findings"]["L002"]["decision"] == "ignored"

    confirmed = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L002",
            "decision": "confirmed",
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["findings"]["L002"]["decision"] == "confirmed"
    assert confirmed.json()["findings"]["L002"].get("decision") != "ignored"


def test_invalid_finding_returns_error(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    response = client.patch(
        "/api/document-consistency-qc/finding-review",
        json={
            "flow_run_id": flow_run_id,
            "finding_id": "L999",
            "resolved": True,
        },
    )
    assert response.status_code == 400
    assert response.json()["status"] == "failed"
