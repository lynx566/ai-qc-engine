"""Targeted tests for Document Consistency QC source annotation HTTP bridge."""

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
                    }
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


def _valid_anchor() -> dict[str, str]:
    return {
        "slot_id": "source",
        "doc_id": "doc_test",
        "block_id": "C0002",
        "sentence_id": "C0002:S001",
    }


def test_get_missing_returns_empty(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    response = client.get(
        "/api/document-consistency-qc/source-annotations",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["flow_run_id"] == flow_run_id
    assert payload["annotations"] == {}


def test_post_valid_anchor_creates_annotation(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    response = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={"flow_run_id": flow_run_id, "anchor": _valid_anchor()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["annotation_id"].startswith("ann_")
    assert payload["anchor"]["sentence_id"] == "C0002:S001"


def test_post_invalid_anchor_returns_400(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    response = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "anchor": {
                "slot_id": "source",
                "doc_id": "doc_test",
                "block_id": "C0002",
                "sentence_id": "T0001",
            },
        },
    )
    assert response.status_code == 400
    assert response.json()["status"] == "failed"


def test_delete_valid_annotation(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    created = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={"flow_run_id": flow_run_id, "anchor": _valid_anchor()},
    ).json()
    response = client.delete(
        "/api/document-consistency-qc/source-annotations",
        params={
            "flow_run_id": flow_run_id,
            "annotation_id": created["annotation_id"],
        },
    )
    assert response.status_code == 200
    assert response.json()["annotations"] == {}


def test_delete_unknown_annotation_returns_400(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    response = client.delete(
        "/api/document-consistency-qc/source-annotations",
        params={
            "flow_run_id": flow_run_id,
            "annotation_id": "ann_missing",
        },
    )
    assert response.status_code == 400
    assert response.json()["status"] == "failed"


def test_post_valid_range_round_trips(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    blocks = _default_extract_blocks()
    blocks.append(
        {
            "block_id": "C0100",
            "kind": "paragraph",
            "heading_path": ["Scope A"],
            "doc_order_index": 10,
            "raw_text": "感染性肺炎2例",
            "sentences": [
                {
                    "sentence_id": "C0100:S001",
                    "raw_text": "感染性肺炎2例",
                    "normalized_text": "感染性肺炎2例",
                }
            ],
        }
    )
    flow_run_id = _write_fixture_with_blocks(
        bridge_config.project_root or bridge_config.default_workspace_root,
        blocks,
    )
    created = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "anchor": {
                "slot_id": "source",
                "doc_id": "doc_test",
                "block_id": "C0100",
                "sentence_id": "C0100:S001",
            },
            "range": {"start_offset": 0, "end_offset": 4},
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["range"] == {"start_offset": 0, "end_offset": 4}

    loaded = client.get(
        "/api/document-consistency-qc/source-annotations",
        params={"flow_run_id": flow_run_id},
    )
    assert loaded.status_code == 200
    annotation_id = payload["annotation_id"]
    assert loaded.json()["annotations"][annotation_id]["range"] == {
        "start_offset": 0,
        "end_offset": 4,
    }


def test_post_invalid_range_returns_400(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    response = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "anchor": _valid_anchor(),
            "range": {"start_offset": 0, "end_offset": 999},
        },
    )
    assert response.status_code == 400
    assert response.json()["status"] == "failed"


def _write_fixture_with_blocks(tmp_path: Path, blocks: list[dict]) -> str:
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
                    }
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
        extract_blocks=blocks,
    )


def test_post_highlight_round_trips(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    blocks = _default_extract_blocks()
    blocks.append(
        {
            "block_id": "C0101",
            "kind": "paragraph",
            "heading_path": ["Scope A"],
            "doc_order_index": 11,
            "raw_text": "感染性肺炎2例",
            "sentences": [
                {
                    "sentence_id": "C0101:S001",
                    "raw_text": "感染性肺炎2例",
                    "normalized_text": "感染性肺炎2例",
                }
            ],
        }
    )
    flow_run_id = _write_fixture_with_blocks(
        bridge_config.project_root or bridge_config.default_workspace_root,
        blocks,
    )
    created = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "kind": "highlight",
            "anchor": {
                "slot_id": "source",
                "doc_id": "doc_test",
                "block_id": "C0101",
                "sentence_id": "C0101:S001",
            },
            "range": {"start_offset": 0, "end_offset": 4},
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["kind"] == "highlight"
    assert payload["range"] == {"start_offset": 0, "end_offset": 4}


def test_post_overlapping_highlight_returns_400(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    blocks = _default_extract_blocks()
    blocks.append(
        {
            "block_id": "C0101",
            "kind": "paragraph",
            "heading_path": ["Scope A"],
            "doc_order_index": 11,
            "raw_text": "感染性肺炎2例",
            "sentences": [
                {
                    "sentence_id": "C0101:S001",
                    "raw_text": "感染性肺炎2例",
                    "normalized_text": "感染性肺炎2例",
                }
            ],
        }
    )
    flow_run_id = _write_fixture_with_blocks(
        bridge_config.project_root or bridge_config.default_workspace_root,
        blocks,
    )
    client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "kind": "highlight",
            "anchor": {
                "slot_id": "source",
                "doc_id": "doc_test",
                "block_id": "C0101",
                "sentence_id": "C0101:S001",
            },
            "range": {"start_offset": 0, "end_offset": 4},
        },
    )
    response = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "kind": "highlight",
            "anchor": {
                "slot_id": "source",
                "doc_id": "doc_test",
                "block_id": "C0101",
                "sentence_id": "C0101:S001",
            },
            "range": {"start_offset": 2, "end_offset": 6},
        },
    )
    assert response.status_code == 400


def test_post_comment_round_trips(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    created = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "kind": "comment",
            "anchor": _valid_anchor(),
            "content": "这里应改为80.0%",
            "range": {"start_offset": 0, "end_offset": 1},
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["kind"] == "comment"
    assert payload["content"] == "这里应改为80.0%"
    assert payload["range"] == {"start_offset": 0, "end_offset": 1}


def test_second_overlapping_comment_returns_400(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "kind": "comment",
            "anchor": _valid_anchor(),
            "content": "first",
            "range": {"start_offset": 0, "end_offset": 2},
        },
    )
    response = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "kind": "comment",
            "anchor": _valid_anchor(),
            "content": "second",
            "range": {"start_offset": 1, "end_offset": 3},
        },
    )
    assert response.status_code == 400


def test_patch_comment_content_round_trips(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    created = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "kind": "comment",
            "anchor": _valid_anchor(),
            "content": "first",
            "range": {"start_offset": 0, "end_offset": 1},
        },
    ).json()
    response = client.patch(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "annotation_id": created["annotation_id"],
            "content": "second",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "second"
    assert payload["kind"] == "comment"
    assert payload["range"] == {"start_offset": 0, "end_offset": 1}


def test_post_edit_round_trips(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    response = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "kind": "edit",
            "anchor": _valid_anchor(),
            "range": {"start_offset": 0, "end_offset": 1},
            "replacement_text": "80.0%",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "edit"
    assert payload["replacement_text"] == "80.0%"


def test_patch_edit_replacement_text_round_trips(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_fixture(bridge_config.project_root or bridge_config.default_workspace_root)
    created = client.post(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "kind": "edit",
            "anchor": _valid_anchor(),
            "range": {"start_offset": 0, "end_offset": 1},
            "replacement_text": "80.0%",
        },
    ).json()
    response = client.patch(
        "/api/document-consistency-qc/source-annotations",
        json={
            "flow_run_id": flow_run_id,
            "annotation_id": created["annotation_id"],
            "replacement_text": "85.0%",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["replacement_text"] == "85.0%"
    assert payload["kind"] == "edit"
