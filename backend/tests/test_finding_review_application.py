"""Targeted tests for finding review application read/write boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.finding_review import (
    FindingReviewNotFoundError,
    FindingReviewUnknownFindingError,
    load_finding_review_state,
    patch_finding_review_entry,
    set_finding_marked,
    set_finding_resolved,
    update_finding_note,
)
from application.clinical_trial_doc_consistency_qc.result_read import (
    load_document_consistency_qc_result,
)
from application.document_consistency_qc.finding_review import (
    FindingReviewPersistenceError,
    resolve_finding_review_state_path,
)
from artifacts.finding_review_state import FINDING_REVIEW_STATE_LEGACY_SCHEMA_VERSION
from runtime.io import load_json, save_json
from tests.test_internal_result_read import (
    _default_extract_blocks,
    _write_minimal_internal_result_fixture,
)


def _write_reviewable_fixture(tmp_path: Path) -> str:
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


def test_load_missing_artifact_returns_empty(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    model = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    assert model.flow_run_id == flow_run_id
    assert model.findings == ()


def test_resolved_entry_is_persisted(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=True,
    )
    path = resolve_finding_review_state_path(
        flow_root=tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    )
    assert path.is_file()
    payload = load_json(path)
    assert payload["findings"]["L001"]["decision"] == "confirmed"
    assert payload["findings"]["L001"]["marked"] is False


def test_resolved_cleared_removes_entry(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=True,
    )
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=False,
    )
    path = resolve_finding_review_state_path(
        flow_root=tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    )
    assert not path.is_file()


def test_note_only_entry_is_retained(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    update_finding_note(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L002",
        note="memo",
    )
    model = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    entry = next(item for item in model.findings if item.finding_id == "L002")
    assert entry.decision == "pending"
    assert entry.marked is False
    assert entry.note == "memo"


def test_note_cleared_and_defaults_remove_entry(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    update_finding_note(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L002",
        note="memo",
    )
    patch_finding_review_entry(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L002",
        note="",
    )
    path = resolve_finding_review_state_path(
        flow_root=tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    )
    assert not path.is_file()


def test_resolved_and_marked_persist_together(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=True,
    )
    set_finding_marked(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        marked=True,
    )
    model = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    entry = next(item for item in model.findings if item.finding_id == "L001")
    assert entry.decision == "confirmed"
    assert entry.marked is True


def test_patch_resolved_only_does_not_change_marked(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    set_finding_marked(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L002",
        marked=True,
    )
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L002",
        resolved=True,
    )
    model = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    entry = next(item for item in model.findings if item.finding_id == "L002")
    assert entry.decision == "confirmed"
    assert entry.marked is True


def test_patch_marked_only_does_not_change_resolved(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=True,
    )
    set_finding_marked(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        marked=True,
    )
    set_finding_marked(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        marked=False,
    )
    model = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    entry = next(item for item in model.findings if item.finding_id == "L001")
    assert entry.decision == "confirmed"
    assert entry.marked is False


def test_note_mutation_does_not_change_booleans(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    set_finding_marked(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L002",
        marked=True,
    )
    update_finding_note(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L002",
        note="memo",
    )
    model = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    entry = next(item for item in model.findings if item.finding_id == "L002")
    assert entry.marked is True
    assert entry.decision == "pending"
    assert entry.note == "memo"


def test_legacy_artifact_reads_with_new_semantics(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    path = resolve_finding_review_state_path(
        flow_root=tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(
        path,
        {
            "artifact_type": "document_consistency_qc_finding_review_state",
            "schema_version": FINDING_REVIEW_STATE_LEGACY_SCHEMA_VERSION,
            "flow_run_id": flow_run_id,
            "findings": {
                "L001": {
                    "review_state": "reviewed",
                    "updated_at": "2026-09-13T00:00:00Z",
                },
                "L002": {
                    "review_state": "flagged",
                    "note": "keep",
                    "updated_at": "2026-09-13T00:00:00Z",
                },
            },
        },
    )
    model = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    reviewed = next(item for item in model.findings if item.finding_id == "L001")
    flagged = next(item for item in model.findings if item.finding_id == "L002")
    assert reviewed.decision == "confirmed"
    assert reviewed.marked is False
    assert flagged.decision == "pending"
    assert flagged.marked is True
    assert flagged.note == "keep"


def test_unknown_flow_rejected(tmp_path: Path) -> None:
    with pytest.raises(FindingReviewNotFoundError):
        load_finding_review_state(
            project_root=tmp_path,
            flow_run_id="document_consistency_qc_missing",
        )


def test_unknown_finding_rejected(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    with pytest.raises(FindingReviewUnknownFindingError):
        set_finding_resolved(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            finding_id="L999",
            resolved=True,
        )


def test_review_identity_uses_consolidated_finding_id_not_source_lineage(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_minimal_internal_result_fixture(
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
                "findings": [],
            }
        ],
        final_findings=[
            {
                "finding_id": "L031",
                "label": "need_review",
                "conclusion": "consolidated",
                "source_sentence_aliases": ["T0001", "T0002"],
                "comparison_mode_id": "focus_comparison",
                "source_finding_ids": ["L001", "L002"],
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

    set_finding_marked(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L031",
        marked=True,
    )
    model = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    assert [entry.finding_id for entry in model.findings] == ["L031"]

    with pytest.raises(FindingReviewUnknownFindingError):
        set_finding_marked(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            finding_id="L001",
            marked=True,
        )


def test_need_review_accepts_mutation(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    set_finding_marked(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L002",
        marked=True,
    )
    model = load_finding_review_state(project_root=tmp_path, flow_run_id=flow_run_id)
    assert any(item.finding_id == "L002" and item.marked for item in model.findings)


def test_system_result_unchanged_after_review_mutation(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    before = load_document_consistency_qc_result(
        project_root=tmp_path, flow_run_id=flow_run_id
    )
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=True,
    )
    update_finding_note(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L002",
        note="memo",
    )
    after = load_document_consistency_qc_result(
        project_root=tmp_path, flow_run_id=flow_run_id
    )
    assert before == after


def test_noop_mutation_does_not_rewrite(tmp_path: Path) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=True,
    )
    path = resolve_finding_review_state_path(
        flow_root=tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    )
    before_mtime = path.stat().st_mtime
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=True,
    )
    after_mtime = path.stat().st_mtime
    assert after_mtime == before_mtime


def test_atomic_write_failure_does_not_corrupt_previous_artifact(
    tmp_path: Path,
) -> None:
    flow_run_id = _write_reviewable_fixture(tmp_path)
    set_finding_resolved(
        project_root=tmp_path,
        flow_run_id=flow_run_id,
        finding_id="L001",
        resolved=True,
    )
    path = resolve_finding_review_state_path(
        flow_root=tmp_path / "runs" / "document_consistency_qc" / "test_internal_result"
    )
    previous = load_json(path)
    with (
        patch(
            "application.document_consistency_qc.finding_review.save_json_atomic",
            side_effect=OSError("disk full"),
        ),
        pytest.raises(FindingReviewPersistenceError, match="disk full"),
    ):
        set_finding_marked(
            project_root=tmp_path,
            flow_run_id=flow_run_id,
            finding_id="L002",
            marked=True,
        )
    assert load_json(path) == previous
