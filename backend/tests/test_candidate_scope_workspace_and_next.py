"""Candidate Scope bridge POST tests against canonical application resume."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.document_consistency_qc.create_flow_result import (
    DocumentConsistencyQcCreateFlowResult,
)
from artifacts.candidate_scope_decision import CANDIDATE_SCOPE_DECISION_FILENAME
from artifacts.effective_candidate_scope import RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
from bridge.candidate_scope.app import create_app
from execution_flow.document_consistency_qc.flow_loader import load_flow_run_execution
from runtime.io import load_json
from tests.candidate_scope_isolation import (
    assert_no_candidate_scope_execution_artifacts,
    assert_no_standalone_projection_artifacts,
    mark_canonical_flow_completed,
    prepare_paused_multi_slot_canonical_flow,
)


def _slot_state(state: dict, slot_id: str) -> dict:
    return next(item for item in state["slots"] if item["slot_id"] == slot_id)


def _selections_from_slot_state(slot_state: dict) -> list[dict]:
    if slot_state.get("filter_jobs"):
        return [
            {
                "filter_job_id": job["filter_job_id"],
                "anchor_block_ids": list(job["current_anchor_block_ids"]),
            }
            for job in slot_state["filter_jobs"]
        ]

    automatic = set(slot_state["automatic_anchor_block_ids"])
    grouped: dict[str, list[str]] = {}
    for heading in slot_state["headings"]:
        if heading["anchor_block_id"] not in automatic:
            continue
        grouped.setdefault(heading["filter_job_id"], []).append(
            heading["anchor_block_id"]
        )
    return [
        {
            "filter_job_id": filter_job_id,
            "anchor_block_ids": sorted(anchors),
        }
        for filter_job_id, anchors in grouped.items()
    ]


def _next_payload(
    *,
    flow_run_id: str,
    state: dict,
    slot_ids: tuple[str, ...] | list[str],
    overrides_by_slot: dict[str, dict[str, list[str]]] | None = None,
) -> dict:
    slot_decisions: list[dict] = []
    for slot_id in slot_ids:
        selections = _selections_from_slot_state(_slot_state(state, slot_id))
        if overrides_by_slot and slot_id in overrides_by_slot:
            by_job = {item["filter_job_id"]: item for item in selections}
            for filter_job_id, anchors in overrides_by_slot[slot_id].items():
                by_job[filter_job_id] = {
                    "filter_job_id": filter_job_id,
                    "anchor_block_ids": sorted(anchors),
                }
            selections = list(by_job.values())
        slot_decisions.append(
            {
                "slot_id": slot_id,
                "candidate_scope": selections,
            }
        )
    return {
        "flow_run_id": flow_run_id,
        "slot_decisions": slot_decisions,
    }


def _successful_resume_result(flow_run_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        flow_report=SimpleNamespace(
            flow_run_id=flow_run_id,
            flow_run_summary_path=Path("summary.json"),
            result=SimpleNamespace(paused_at_candidate_scope=False),
        )
    )


@pytest.fixture
def client(paused_flow: tuple) -> TestClient:
    bridge_config, _flow_run_id, _slot_id = paused_flow
    return TestClient(create_app(bridge_config=bridge_config))


@pytest.fixture
def bridge_config(paused_flow: tuple):
    return paused_flow[0]


@pytest.fixture
def flow_run_id(paused_flow: tuple) -> str:
    return paused_flow[1]


@pytest.fixture
def slot_id(paused_flow: tuple) -> str:
    return paused_flow[2]


@pytest.fixture
def paused_state(client: TestClient, flow_run_id: str) -> dict:
    response = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    )
    assert response.status_code == 200
    return response.json()


def test_next_automatic_selection_runs_canonical_resume(
    client: TestClient,
    bridge_config,
    flow_run_id: str,
    slot_id: str,
    paused_state: dict,
) -> None:
    payload = _next_payload(
        flow_run_id=flow_run_id,
        state=paused_state,
        slot_ids=(slot_id,),
    )
    with patch(
        "bridge.candidate_scope.next_service.resume_installed_clinical_trial_document_consistency_qc",
        wraps=__import__(
            "application.clinical_trial_doc_consistency_qc",
            fromlist=["resume_installed_clinical_trial_document_consistency_qc"],
        ).resume_installed_clinical_trial_document_consistency_qc,
    ) as resume_mock:
        response = client.post("/api/candidate-scope/next", json=payload)

    assert response.status_code == 200
    resume_mock.assert_called_once()

    body = response.json()
    assert body["status"] == "ready"
    assert body["flow_id"] == "document_consistency_qc"
    assert body["flow_run_id"] == flow_run_id
    assert body["completed"] is True
    assert body["paused_at_candidate_scope"] is False
    assert body["paused_slot_ids"] == []
    assert "slot_id" not in body
    assert "execution_id" not in body
    assert "projection_ref_count" not in body
    assert "next_stage_ready" not in body

    decision_path = (
        bridge_config.runs_root
        / "document_consistency_qc"
        / flow_run_id.removeprefix("document_consistency_qc_")
        / "participants"
        / slot_id
        / "candidate_scope"
        / CANDIDATE_SCOPE_DECISION_FILENAME
    )
    assert decision_path.is_file()
    validate_decision = load_json(decision_path)
    assert validate_decision["flow_run_id"] == flow_run_id

    execution = load_flow_run_execution(
        project_root=bridge_config.workspace_root,
        flow_run_id=flow_run_id,
    )
    slot = next(item for item in execution.slot_provenance if item.slot_id == slot_id)
    assert slot.projection_jobs
    projection_root = (
        bridge_config.runs_root
        / "document_consistency_qc"
        / flow_run_id.removeprefix("document_consistency_qc_")
        / "participants"
        / slot_id
        / "filter_output_projection"
    )
    assert projection_root.is_dir()
    assert any(projection_root.rglob("filter_output_projection_bundle.json"))

    assert_no_candidate_scope_execution_artifacts(bridge_config.runs_root)
    assert_no_standalone_projection_artifacts(bridge_config.runs_root)


def test_next_manual_add_accepted(
    client: TestClient,
    bridge_config,
    flow_run_id: str,
    slot_id: str,
    paused_state: dict,
) -> None:
    slot_state = _slot_state(paused_state, slot_id)
    automatic = _selections_from_slot_state(slot_state)
    clinical = next(
        item for item in automatic if item["filter_job_id"] == "dsur_clinical_safety"
    )
    manual_anchor = "C0015"
    assert manual_anchor not in slot_state["automatic_anchor_block_ids"]
    owners = {
        heading["anchor_block_id"]: heading["filter_job_id"]
        for heading in slot_state["headings"]
    }
    assert owners[manual_anchor] == "dsur_clinical_safety"
    adjusted = sorted(clinical["anchor_block_ids"] + [manual_anchor])
    payload = _next_payload(
        flow_run_id=flow_run_id,
        state=paused_state,
        slot_ids=(slot_id,),
        overrides_by_slot={slot_id: {"dsur_clinical_safety": adjusted}},
    )

    response = client.post("/api/candidate-scope/next", json=payload)
    assert response.status_code == 200

    resolved_path = (
        bridge_config.runs_root
        / "document_consistency_qc"
        / flow_run_id.removeprefix("document_consistency_qc_")
        / "participants"
        / slot_id
        / "candidate_scope"
        / "dsur_clinical_safety"
        / RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
    )
    assert resolved_path.is_file()
    decision_path = resolved_path.parent.parent / CANDIDATE_SCOPE_DECISION_FILENAME
    assert decision_path.is_file()


def test_next_unknown_heading_rejected(
    client: TestClient,
    flow_run_id: str,
    slot_id: str,
    paused_state: dict,
) -> None:
    payload = _next_payload(
        flow_run_id=flow_run_id,
        state=paused_state,
        slot_ids=(slot_id,),
        overrides_by_slot={slot_id: {"dsur_overview": ["C9999"]}},
    )
    response = client.post("/api/candidate-scope/next", json=payload)
    assert response.status_code == 400


def test_next_known_heading_wrong_job_rejected(
    client: TestClient,
    flow_run_id: str,
    slot_id: str,
    paused_state: dict,
) -> None:
    slot_state = _slot_state(paused_state, slot_id)
    manual_anchor = "C0015"
    assert manual_anchor not in slot_state["automatic_anchor_block_ids"]
    owners = {
        heading["anchor_block_id"]: heading["filter_job_id"]
        for heading in slot_state["headings"]
    }
    assert owners[manual_anchor] == "dsur_clinical_safety"
    automatic = _selections_from_slot_state(slot_state)
    overview = next(
        item for item in automatic if item["filter_job_id"] == "dsur_overview"
    )
    payload = _next_payload(
        flow_run_id=flow_run_id,
        state=paused_state,
        slot_ids=(slot_id,),
        overrides_by_slot={
            slot_id: {
                "dsur_overview": sorted(overview["anchor_block_ids"] + [manual_anchor])
            }
        },
    )
    response = client.post("/api/candidate-scope/next", json=payload)
    assert response.status_code == 400


def test_next_missing_paused_slot_rejected_by_application(
    client: TestClient,
    flow_run_id: str,
    slot_id: str,
    paused_state: dict,
) -> None:
    payload = _next_payload(
        flow_run_id=flow_run_id,
        state=paused_state,
        slot_ids=(slot_id,),
    )
    payload["slot_decisions"] = payload["slot_decisions"][:0]
    response = client.post("/api/candidate-scope/next", json=payload)
    assert response.status_code == 400


def test_next_multi_slot_one_resume_reaches_comparison(tmp_path: Path) -> None:
    bridge_config, flow_run_id, slot_ids = prepare_paused_multi_slot_canonical_flow(
        tmp_path
    )
    client = TestClient(create_app(bridge_config=bridge_config))
    state = client.get(
        "/api/candidate-scope/state",
        params={"flow_run_id": flow_run_id},
    ).json()

    payload = _next_payload(
        flow_run_id=flow_run_id,
        state=state,
        slot_ids=slot_ids,
    )
    with patch(
        "bridge.candidate_scope.next_service.resume_installed_clinical_trial_document_consistency_qc",
        wraps=__import__(
            "application.clinical_trial_doc_consistency_qc",
            fromlist=["resume_installed_clinical_trial_document_consistency_qc"],
        ).resume_installed_clinical_trial_document_consistency_qc,
    ) as resume_mock:
        response = client.post("/api/candidate-scope/next", json=payload)

    assert response.status_code == 200
    resume_mock.assert_called_once()
    body = response.json()
    assert body["paused_at_candidate_scope"] is False
    assert body["paused_slot_ids"] == []
    assert "slot_id" not in body

    for slot_id in slot_ids:
        decision_path = (
            bridge_config.runs_root
            / "document_consistency_qc"
            / flow_run_id.removeprefix("document_consistency_qc_")
            / "participants"
            / slot_id
            / "candidate_scope"
            / CANDIDATE_SCOPE_DECISION_FILENAME
        )
        assert decision_path.is_file()


def test_bridge_runtime_config_has_no_uploads_field() -> None:
    from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig

    assert "uploads" not in BridgeRuntimeConfig.__dataclass_fields__


def test_repeated_resume_rejected(
    client: TestClient,
    bridge_config,
    flow_run_id: str,
    slot_id: str,
    paused_state: dict,
) -> None:
    payload = _next_payload(
        flow_run_id=flow_run_id,
        state=paused_state,
        slot_ids=(slot_id,),
    )
    with (
        patch(
            "bridge.candidate_scope.next_service.build_document_consistency_qc_create_flow_result",
            return_value=DocumentConsistencyQcCreateFlowResult(
                flow_id="document_consistency_qc",
                flow_run_id=flow_run_id,
                flow_status="success",
                paused_at_candidate_scope=False,
                paused_slot_ids=(),
                paused_slot_id=None,
                completed=True,
                flow_run_summary_path=Path("summary.json"),
            ),
        ),
        patch(
            "bridge.candidate_scope.next_service.resume_installed_clinical_trial_document_consistency_qc",
            return_value=_successful_resume_result(flow_run_id),
        ),
    ):
        first = client.post("/api/candidate-scope/next", json=payload)
    assert first.status_code == 200
    mark_canonical_flow_completed(bridge_config, flow_run_id)

    second = client.post("/api/candidate-scope/next", json=payload)
    assert second.status_code == 400


def test_pytest_isolation_does_not_touch_repo_runs(
    bridge_config,
    flow_run_id: str,
    slot_id: str,
    paused_state: dict,
    client: TestClient,
) -> None:
    repo_runs = BACKEND_ROOT / "runs"
    before = {
        path.relative_to(repo_runs) for path in repo_runs.rglob("*") if path.is_file()
    }
    payload = _next_payload(
        flow_run_id=flow_run_id,
        state=paused_state,
        slot_ids=(slot_id,),
    )
    with (
        patch(
            "bridge.candidate_scope.next_service.build_document_consistency_qc_create_flow_result",
            return_value=DocumentConsistencyQcCreateFlowResult(
                flow_id="document_consistency_qc",
                flow_run_id=flow_run_id,
                flow_status="success",
                paused_at_candidate_scope=False,
                paused_slot_ids=(),
                paused_slot_id=None,
                completed=True,
                flow_run_summary_path=Path("summary.json"),
            ),
        ),
        patch(
            "bridge.candidate_scope.next_service.resume_installed_clinical_trial_document_consistency_qc",
            return_value=_successful_resume_result(flow_run_id),
        ),
    ):
        response = client.post("/api/candidate-scope/next", json=payload)
    assert response.status_code == 200
    after = {
        path.relative_to(repo_runs) for path in repo_runs.rglob("*") if path.is_file()
    }
    assert before == after
