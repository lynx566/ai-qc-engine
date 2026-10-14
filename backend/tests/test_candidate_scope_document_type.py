"""Persisted slot diagnostics exposed by the normal QC Setup read path."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bridge.candidate_scope.app import create_app
from application.clinical_trial_doc_consistency_qc.document_type_read import (
    read_slot_document_type_diagnostic,
)
from application.clinical_trial_doc_consistency_qc.result_readiness import (
    probe_result_readiness,
)
from application.task_run import create_task_run_for_flow
from task.clinical_trial_doc_qc.task_run_read import load_task_run_page_context
from execution_flow.document_consistency_qc.flow_loader import load_flow_run_execution
from runtime.io import load_json, save_json
from tests.candidate_scope_isolation import (
    mark_canonical_flow_completed,
    prepare_paused_canonical_flow,
    prepare_paused_multi_slot_canonical_flow,
)
from tests.test_result_readiness import _fixture


@pytest.fixture
def paused_flow(tmp_path):
    # Metadata is mutated here: do not use the shared baseline's absolute paths.
    return prepare_paused_canonical_flow(tmp_path)


def _execution(config, flow_run_id):
    return load_flow_run_execution(
        project_root=config.workspace_root, flow_run_id=flow_run_id
    )


def _set_metadata(config, flow_run_id, slot_id, observed, warnings=()):
    slot = next(
        slot
        for slot in _execution(config, flow_run_id).slot_provenance
        if slot.slot_id == slot_id
    )
    path = Path(slot.doc_meta_bundle_path)
    bundle = load_json(path)
    bundle["doc_type"]["value"] = observed
    bundle["warnings"] = list(warnings)
    save_json(path, bundle)
    return path


def _read(config, flow_run_id):
    # A fresh app/client for each read rules out in-memory execution enrichment.
    with TestClient(create_app(bridge_config=config)) as client:
        response = client.get(
            "/api/candidate-scope/state", params={"flow_run_id": flow_run_id}
        )
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    "observed,warnings,status,reason",
    [
        ("DSUR", [], "match", "observed_matches_expected"),
        ("IB", [], "mismatch", "observed_differs_from_expected"),
        (None, [], "uncertain", "observed_unavailable"),
        ("DSUR", ["doc_type_conflict"], "uncertain", "doc_type_conflict"),
    ],
)
def test_state_reads_persisted_diagnostic_on_refresh_and_historical_reentry(
    paused_flow, observed, warnings, status, reason
):
    config, flow_run_id, slot_id = paused_flow
    _set_metadata(config, flow_run_id, slot_id, observed, warnings)
    expected = {"status": status, "expected_document_type": "DSUR", "reason": reason}
    for _ in range(2):
        state = _read(config, flow_run_id)
        assert state["slots"][0].get("document_type_diagnostic") == expected
        assert state["can_resume"] is True
    mark_canonical_flow_completed(config, flow_run_id, persist_decision=True)
    state = _read(config, flow_run_id)
    assert state["slots"][0].get("document_type_diagnostic") == expected
    assert state["can_resume"] is False


@pytest.mark.parametrize(
    "failure",
    [
        "no_reference",
        "missing_file",
        "invalid_json",
        "invalid_bundle",
        "invalid_encoding",
    ],
)
def test_unavailable_metadata_keeps_setup_readable_without_fabricated_uncertain(
    paused_flow, failure
):
    config, flow_run_id, slot_id = paused_flow
    path = _set_metadata(config, flow_run_id, slot_id, "IB")
    if failure in {"no_reference", "missing_file"}:
        execution = _execution(config, flow_run_id)
        summary = load_json(execution.flow_run_summary_path)
        if failure == "no_reference":
            summary["slots"][0].pop("doc_meta_bundle_path", None)
        else:
            summary["slots"][0]["doc_meta_bundle_path"] = str(
                path.parent / "missing.json"
            )
        save_json(execution.flow_run_summary_path, summary)
    elif failure == "invalid_json":
        path.write_text("{broken", encoding="utf-8")
    elif failure == "invalid_encoding":
        path.write_bytes(b"\xff\xfe")
    else:
        save_json(path, [])
    state = _read(config, flow_run_id)
    assert state["can_resume"] is True
    assert state["slots"][0].get("document_type_diagnostic") is None
    assert state["slots"][0]["headings"]
    if failure == "no_reference":
        with TestClient(create_app(bridge_config=config)) as client:
            document_response = client.get(
                "/api/candidate-scope/document",
                params={"flow_run_id": flow_run_id, "slot_id": slot_id},
            )
        assert document_response.status_code == 200
        assert document_response.json()["doc_id"] == state["slots"][0]["doc_id"]
        # Tolerant Setup reads must not weaken the default execution/resume loader.
        with pytest.raises(ValueError, match="requires 'doc_meta_bundle_path'"):
            _execution(config, flow_run_id)


def test_dual_document_diagnostics_and_read_failures_are_slot_local(tmp_path):
    config, flow_run_id, _ = prepare_paused_multi_slot_canonical_flow(tmp_path)
    path_a = _set_metadata(config, flow_run_id, "source_a", "IB")
    _set_metadata(config, flow_run_id, "source_b", "IB")
    state = _read(config, flow_run_id)
    by_slot = {slot["slot_id"]: slot for slot in state["slots"]}
    assert by_slot["source_a"].get("document_type_diagnostic") == {
        "status": "mismatch",
        "expected_document_type": "DSUR",
        "reason": "observed_differs_from_expected",
    }
    assert by_slot["source_b"].get("document_type_diagnostic") == {
        "status": "match",
        "expected_document_type": "IB",
        "reason": "observed_matches_expected",
    }
    path_a.write_text("{broken", encoding="utf-8")
    state = _read(config, flow_run_id)
    assert state["slots"][0].get("document_type_diagnostic") is None
    assert state["slots"][1]["document_type_diagnostic"]["status"] == "match"


@pytest.mark.parametrize(
    "capability_id,slot_id,expected",
    [
        ("internal_dsur", "source", "DSUR"),
        ("internal_csr", "source", "CSR"),
        ("internal_ib", "source", "IB"),
        ("dsur_updated_ib", "source_a", "DSUR"),
        ("dsur_updated_ib", "source_b", "IB"),
    ],
)
def test_read_uses_installed_slot_expected_type(
    tmp_path, capability_id, slot_id, expected
):
    path = tmp_path / "doc_meta_bundle.json"
    save_json(path, {"doc_type": {"value": expected}, "warnings": []})
    diagnostic = read_slot_document_type_diagnostic(
        capability_id=capability_id, slot_id=slot_id, doc_meta_bundle_path=str(path)
    )
    assert diagnostic is not None
    assert diagnostic.status == "match"
    assert diagnostic.expected_document_type == expected


@pytest.mark.parametrize(
    "bundle",
    [
        {},
        {"doc_type": "DSUR", "warnings": []},
        {"doc_type": {}, "warnings": []},
        {"doc_type": {"value": "DSUR"}, "warnings": "doc_type_conflict"},
        {"doc_type": {"value": 123}, "warnings": []},
    ],
)
def test_malformed_metadata_has_no_semantic_diagnostic(tmp_path, bundle):
    path = tmp_path / "doc_meta_bundle.json"
    save_json(path, bundle)
    assert (
        read_slot_document_type_diagnostic(
            capability_id="internal_dsur",
            slot_id="source",
            doc_meta_bundle_path=str(path),
        )
        is None
    )


def test_read_permission_failure_is_not_uncertain(monkeypatch, caplog):
    def denied(_path):
        raise PermissionError("test read failure")

    monkeypatch.setattr(
        "application.clinical_trial_doc_consistency_qc.document_type_read.load_json",
        denied,
    )
    assert (
        read_slot_document_type_diagnostic(
            capability_id="internal_dsur",
            slot_id="source",
            doc_meta_bundle_path="unreadable.json",
        )
        is None
    )
    assert "Document-type advice unavailable" in caplog.text


def test_missing_binding_is_unavailable_not_uncertain(tmp_path):
    path = tmp_path / "doc_meta_bundle.json"
    save_json(path, {"doc_type": {"value": "DSUR"}, "warnings": []})
    assert (
        read_slot_document_type_diagnostic(
            capability_id="retired_capability",
            slot_id="source",
            doc_meta_bundle_path=str(path),
        )
        is None
    )


@pytest.mark.parametrize("completed", [False, True])
def test_missing_meta_reference_keeps_task_page_and_document_readable(
    paused_flow, completed
):
    config, flow_run_id, slot_id = paused_flow
    execution = _execution(config, flow_run_id)
    if completed:
        mark_canonical_flow_completed(config, flow_run_id, persist_decision=True)
    task_run_id = "task_run_20261010_000000_000000Z_setup_read"
    create_task_run_for_flow(
        project_root=config.workspace_root,
        task_run_id=task_run_id,
        task_id="internal_dsur_qc",
        flow_id="document_consistency_qc",
        flow_run_id=flow_run_id,
    )
    summary = load_json(execution.flow_run_summary_path)
    summary["slots"][0].pop("doc_meta_bundle_path", None)
    save_json(execution.flow_run_summary_path, summary)
    context = load_task_run_page_context(
        project_root=config.workspace_root, task_run_id=task_run_id
    )
    assert context.state.flow_outcome == (
        "success" if completed else "paused_at_candidate_scope"
    )
    assert context.state.requires_user_action is (not completed)
    assert context.state.result_available is False
    assert context.flow_runs[0].flow_run_id == flow_run_id
    state = _read(config, flow_run_id)
    assert state["slots"][0].get("document_type_diagnostic") is None
    with TestClient(create_app(bridge_config=config)) as client:
        response = client.get(
            "/api/candidate-scope/document",
            params={"flow_run_id": flow_run_id, "slot_id": slot_id},
        )
    assert response.status_code == 200
    assert response.json()["doc_id"] == state["slots"][0]["doc_id"]
    if not completed:
        with pytest.raises(ValueError, match="requires 'doc_meta_bundle_path'"):
            _execution(config, flow_run_id)


def test_historical_success_missing_meta_reference_keeps_page_readable_and_result_strict(
    tmp_path,
):
    flow_run_id, summary = _fixture(tmp_path)
    task_run_id = "task_run_20261010_000000_000000Z_historical_setup"
    create_task_run_for_flow(
        project_root=tmp_path,
        task_run_id=task_run_id,
        task_id="internal_dsur_qc",
        flow_id="document_consistency_qc",
        flow_run_id=flow_run_id,
    )
    summary["slots"][0].pop("doc_meta_bundle_path", None)
    save_json(
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / "test_internal_result"
        / "flow_run_summary.json",
        summary,
    )
    context = load_task_run_page_context(project_root=tmp_path, task_run_id=task_run_id)
    assert context.state.flow_outcome == "success"
    assert context.state.requires_user_action is False
    assert context.state.result_available is False
    with pytest.raises(ValueError, match="requires 'doc_meta_bundle_path'"):
        load_flow_run_execution(project_root=tmp_path, flow_run_id=flow_run_id)
    with pytest.raises(ValueError, match="requires 'doc_meta_bundle_path'"):
        probe_result_readiness(
            project_root=tmp_path, flow_run_id=flow_run_id, summary=summary
        )
