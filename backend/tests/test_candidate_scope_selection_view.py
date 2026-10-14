"""Targeted tests for candidate-scope heading catalog ordering."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bridge.candidate_scope.app import create_app
from bridge.candidate_scope.errors import CandidateScopeValidationError
from bridge.candidate_scope.selection_view import _build_heading_catalog

SHOWCASE_DOC_ID = "doc_1342c25e-45cd-49e3-a416-ccb1fb650768"


def test_build_heading_catalog_requires_doc_order_index() -> None:
    analysis_bundle = {
        "doc_id": SHOWCASE_DOC_ID,
        "content_blocks": [
            {
                "block_id": "C0010",
                "kind": "heading",
                "meta": {"heading_level": 1},
                "heading_path": ["1. 执行概要"],
                "analysis_text": "1. 执行概要",
            }
        ],
    }
    with pytest.raises(CandidateScopeValidationError, match="doc_order_index"):
        _build_heading_catalog(
            analysis_bundle,
            review_heading_ownership={"C0010": "dsur_overview"},
        )


@pytest.fixture
def client(paused_flow: tuple) -> TestClient:
    bridge_config, _flow_run_id, _slot_id = paused_flow
    return TestClient(create_app(bridge_config=bridge_config))


def test_state_endpoint_returns_doc_order_index_for_showcase(
    client: TestClient,
    paused_flow: tuple,
) -> None:
    _config, flow_run_id, _slot_id = paused_flow
    response = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["slots"]
    headings = payload["slots"][0]["headings"]
    assert headings
    for heading in headings:
        assert isinstance(heading["doc_order_index"], int)
        assert heading["doc_order_index"] >= 0

    doc_orders = [heading["doc_order_index"] for heading in headings]
    assert doc_orders == sorted(doc_orders)
