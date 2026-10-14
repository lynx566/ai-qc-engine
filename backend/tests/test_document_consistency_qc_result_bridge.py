"""Targeted tests for Document Consistency QC Result HTTP bridge."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

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

SENTINEL_RESULT = {
    "flow_id": "document_consistency_qc",
    "flow_run_id": "document_consistency_qc_sentinel",
    "capability_id": "internal_dsur",
    "flow_status": "completed",
    "comparison_run_status": "success",
    "scope_results": [],
}


@pytest.fixture
def bridge_config(tmp_path: Path) -> DocumentConsistencyQcBridgeConfig:
    return DocumentConsistencyQcBridgeConfig(
        default_workspace_root=tmp_path,
        project_root=tmp_path,
    )


@pytest.fixture
def client(bridge_config: DocumentConsistencyQcBridgeConfig) -> TestClient:
    return TestClient(create_app(bridge_config=bridge_config))


def test_get_result_returns_200_for_completed_internal_flow(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        bridge_config.project_root or bridge_config.default_workspace_root,
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
        final_findings=[
            {
                "finding_id": "L031",
                "label": "need_review",
                "conclusion": "product first",
                "source_sentence_aliases": ["T0001"],
                "comparison_mode_id": "focus_comparison",
                "source_finding_ids": ["L009", "L003"],
            },
            {
                "finding_id": "L002",
                "label": "fail",
                "conclusion": "product second",
                "source_sentence_aliases": ["T0002"],
                "comparison_mode_id": "scope_local",
                "source_finding_ids": ["L002"],
            },
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

    response = client.get(
        "/api/document-consistency-qc/result",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["flow_id"] == "document_consistency_qc"
    assert payload["flow_run_id"] == flow_run_id
    assert payload["capability_id"] == "internal_dsur"
    assert payload["finalization_status"] == "completed"
    assert payload["fallback_comparison_modes"] == []
    assert [finding["finding_id"] for finding in payload["findings"]] == [
        "L031",
        "L002",
    ]
    finding = payload["findings"][0]
    assert finding["label"] == "need_review"
    assert finding["evidence_refs"][0]["block_id"] == "C0002"
    assert "frozen_job_index" not in finding
    assert "source_finding_ids" not in finding
    assert payload["scope_results"]
    scope = payload["scope_results"][0]
    assert scope["outline_heading_block_id"] == "C0001"
    assert "findings" not in scope
    assert "owner_jobs" not in scope


def test_get_result_reports_successful_second_pass_without_verification(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        bridge_config.project_root or bridge_config.default_workspace_root,
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
                "findings": [],
            }
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "scope_local",
                "assessment": {"status": "success"},
                "assessment_second_pass": {"status": "success"},
                "verification": None,
            }
        ],
        extract_blocks=_default_extract_blocks(),
    )

    response = client.get(
        "/api/document-consistency-qc/result",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["findings"] == []
    scope = payload["scope_results"][0]
    assert scope["execution_status"] == "complete"
    assert scope["has_successful_check"] is True
    assert "owner_jobs" not in scope


def test_result_endpoint_calls_application_boundary_not_filesystem(
    client: TestClient,
) -> None:
    with patch(
        "bridge.document_consistency_qc.result_service.load_document_consistency_qc_result",
    ) as loader:
        loader.return_value = type(
            "SentinelResult",
            (),
            {
                "flow_run_id": SENTINEL_RESULT["flow_run_id"],
                "capability_id": SENTINEL_RESULT["capability_id"],
                "flow_status": SENTINEL_RESULT["flow_status"],
                "comparison_run_status": SENTINEL_RESULT["comparison_run_status"],
                "scope_results": (),
            },
        )()
        with patch(
            "bridge.document_consistency_qc.result_service.internal_result_read_model_to_mapping",
            return_value=SENTINEL_RESULT,
        ) as serializer:
            response = client.get(
                "/api/document-consistency-qc/result",
                params={"flow_run_id": SENTINEL_RESULT["flow_run_id"]},
            )

    assert response.status_code == 200
    assert response.json() == SENTINEL_RESULT
    loader.assert_called_once()
    serializer.assert_called_once()


def test_missing_flow_run_id_returns_client_error(client: TestClient) -> None:
    response = client.get("/api/document-consistency-qc/result")
    assert response.status_code == 422


def test_unknown_flow_returns_not_found(client: TestClient) -> None:
    response = client.get(
        "/api/document-consistency-qc/result",
        params={"flow_run_id": "document_consistency_qc_missing_flow"},
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["message"]


def test_persisted_result_resolution_error_returns_client_error(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        bridge_config.project_root or bridge_config.default_workspace_root,
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
                "findings": [],
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
        extract_blocks=[
            block for block in _default_extract_blocks() if block["block_id"] != "C0001"
        ],
    )

    response = client.get(
        "/api/document-consistency-qc/result",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert "unable to resolve extract heading block" in payload["message"]


def test_unsupported_cross_mode_returns_client_error(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        bridge_config.project_root or bridge_config.default_workspace_root,
        plan_jobs=[
            {
                "comparison_mode_id": "ib_to_dsur",
                "groups": [{"group_role": "scope", "scope_aliases": ["H0001"]}],
            }
        ],
        findings_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "ib_to_dsur",
                "comparison_groups": [
                    {"group_role": "scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [],
            }
        ],
        run_summary_jobs=[
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "ib_to_dsur",
                "assessment": {"status": "success"},
                "verification": {"status": "success"},
            }
        ],
        extract_blocks=_default_extract_blocks(),
    )

    response = client.get(
        "/api/document-consistency-qc/result",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert "not supported" in payload["message"].lower()


def test_response_does_not_leak_filesystem_paths(
    client: TestClient,
    bridge_config: DocumentConsistencyQcBridgeConfig,
    tmp_path: Path,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
        bridge_config.project_root or bridge_config.default_workspace_root,
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
                "findings": [],
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

    response = client.get(
        "/api/document-consistency-qc/result",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    serialized = json.dumps(response.json())
    assert str(tmp_path).replace("\\", "/") not in serialized
    assert "runs/document_consistency_qc" not in serialized
