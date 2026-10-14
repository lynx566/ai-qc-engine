"""Targeted tests for candidate-scope heading ownership."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS,
)
from bridge.candidate_scope.app import create_app
from bridge.candidate_scope.selection_view import _build_heading_catalog
from bridge.candidate_scope.state_service import load_candidate_scope_state
from execution_flow.document_consistency_qc.candidate_scope_selection import (
    build_automatic_heading_ownership,
    build_review_heading_ownership,
)

from tests.candidate_scope_isolation import SHOWCASE_SLOT_ID

SHOWCASE_DOC_ID = "doc_1342c25e-45cd-49e3-a416-ccb1fb650768"
INTERNAL_DSUR_MANUAL_DEFAULT = (
    INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS[
        ("internal_dsur", "source")
    ]
)


def _heading_block(
    *,
    block_id: str,
    title: str,
    level: int,
    heading_path: list[str],
    doc_order_index: int,
) -> dict:
    return {
        "block_id": block_id,
        "kind": "heading",
        "meta": {"heading_level": level},
        "heading_path": heading_path,
        "analysis_text": title,
        "doc_order_index": doc_order_index,
    }


def _analysis_bundle(*blocks: dict) -> dict:
    return {
        "doc_id": SHOWCASE_DOC_ID,
        "content_blocks": list(blocks),
    }


def _owner_for_anchor(
    analysis_bundle: dict,
    *,
    automatic_ownership: dict[str, str],
    anchor: str,
    manual_default_filter_job_id: str = INTERNAL_DSUR_MANUAL_DEFAULT,
) -> str:
    automatic_by_job = {
        "dsur_overview": {
            anchor_id
            for anchor_id, owner in automatic_ownership.items()
            if owner == "dsur_overview"
        },
        "dsur_clinical_safety": {
            anchor_id
            for anchor_id, owner in automatic_ownership.items()
            if owner == "dsur_clinical_safety"
        },
    }
    review_heading_ownership = build_review_heading_ownership(
        automatic_by_job,
        analysis_bundle=analysis_bundle,
        manual_default_filter_job_id=manual_default_filter_job_id,
    )
    catalog = _build_heading_catalog(
        analysis_bundle,
        review_heading_ownership=review_heading_ownership,
    )
    match = next(item for item in catalog if item.anchor_block_id == anchor)
    return match.filter_job_id


def test_automatic_overview_owner() -> None:
    ownership = build_automatic_heading_ownership(
        {"dsur_overview": {"C0010"}, "dsur_clinical_safety": set()},
    )
    assert ownership["C0010"] == "dsur_overview"


def test_automatic_clinical_safety_owner() -> None:
    ownership = build_automatic_heading_ownership(
        {"dsur_overview": set(), "dsur_clinical_safety": {"C0030"}},
    )
    assert ownership["C0030"] == "dsur_clinical_safety"


def test_unmatched_level_one_heading_defaults_to_clinical_safety() -> None:
    bundle = _analysis_bundle(
        _heading_block(
            block_id="C0014",
            title="2. 报告范围与方法",
            level=1,
            heading_path=["2. 报告范围与方法"],
            doc_order_index=30,
        ),
    )
    owner = _owner_for_anchor(bundle, automatic_ownership={}, anchor="C0014")
    assert owner == INTERNAL_DSUR_MANUAL_DEFAULT


def test_unmatched_nested_heading_defaults_to_clinical_safety() -> None:
    bundle = _analysis_bundle(
        _heading_block(
            block_id="C0038",
            title="4.3 其他安全性观察",
            level=2,
            heading_path=["4. 临床安全性", "4.3 其他安全性观察"],
            doc_order_index=100,
        ),
    )
    owner = _owner_for_anchor(bundle, automatic_ownership={}, anchor="C0038")
    assert owner == INTERNAL_DSUR_MANUAL_DEFAULT


def test_title_like_overview_without_automatic_provenance_stays_clinical_safety() -> (
    None
):
    bundle = _analysis_bundle(
        _heading_block(
            block_id="C9000",
            title="结论与其他内容",
            level=1,
            heading_path=["结论与其他内容"],
            doc_order_index=10,
        ),
    )
    owner = _owner_for_anchor(bundle, automatic_ownership={}, anchor="C9000")
    assert owner == INTERNAL_DSUR_MANUAL_DEFAULT


def test_remove_readd_automatic_overview_owner_unchanged() -> None:
    bundle = _analysis_bundle(
        _heading_block(
            block_id="C0010",
            title="1. 执行概要",
            level=1,
            heading_path=["1. 执行概要"],
            doc_order_index=10,
        ),
    )
    ownership = build_automatic_heading_ownership({"dsur_overview": {"C0010"}})
    owner = _owner_for_anchor(bundle, automatic_ownership=ownership, anchor="C0010")
    assert owner == "dsur_overview"


def test_dual_automatic_match_fails_explicitly() -> None:
    with pytest.raises(
        ValueError, match="multiple automatic processing owners"
    ) as exc_info:
        build_automatic_heading_ownership(
            {
                "dsur_overview": {"C9999"},
                "dsur_clinical_safety": {"C9999"},
            },
            heading_titles={"C9999": "冲突标题"},
            heading_paths={"C9999": ["冲突标题"]},
        )
    message = str(exc_info.value)
    assert "C9999" in message
    assert "dsur_overview" in message
    assert "dsur_clinical_safety" in message


def test_automatic_ownership_is_independent_of_job_iteration_order() -> None:
    forward = build_automatic_heading_ownership(
        {
            "dsur_overview": {"C0010", "C0044"},
            "dsur_clinical_safety": {"C0030", "C0033", "C0040"},
        }
    )
    reverse = build_automatic_heading_ownership(
        {
            "dsur_clinical_safety": {"C0030", "C0033", "C0040"},
            "dsur_overview": {"C0010", "C0044"},
        }
    )
    assert forward == reverse


def test_showcase_catalog_ownership_closure(paused_flow: tuple) -> None:
    config, flow_run_id, _slot_id = paused_flow
    state = load_candidate_scope_state(
        config=config,
        flow_run_id=flow_run_id,
    )
    slot = state.slots[0]
    owners = {
        heading.anchor_block_id: heading.filter_job_id for heading in slot.headings
    }

    assert owners["C0006"] == "dsur_overview"
    assert owners["C0012"] == "dsur_overview"
    assert owners["C0106"] == "dsur_overview"
    assert owners["C0017"] == "dsur_clinical_safety"
    assert owners["C0020"] == "dsur_clinical_safety"
    assert owners["C0035"] == "dsur_clinical_safety"

    for anchor in ("C0015", "C0024", "C0028", "C0033", "C0036"):
        assert owners[anchor] == INTERNAL_DSUR_MANUAL_DEFAULT


@pytest.fixture
def client(paused_flow: tuple) -> TestClient:
    bridge_config, _flow_run_id, _slot_id = paused_flow
    return TestClient(create_app(bridge_config=bridge_config))


def test_state_endpoint_returns_showcase_ownership(
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
    owners = {
        heading["anchor_block_id"]: heading["filter_job_id"]
        for heading in payload["slots"][0]["headings"]
    }
    assert owners["C0015"] == INTERNAL_DSUR_MANUAL_DEFAULT
    assert owners["C0024"] == INTERNAL_DSUR_MANUAL_DEFAULT
