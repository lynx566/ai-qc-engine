"""Configuration scope display projection from canonical Extract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.document_consistency_qc.configuration_scope_projection import (
    project_configuration_scope_items,
    project_configuration_selection_scope_display,
)
from application.document_consistency_qc.document_read import (
    DocumentReadValidationError,
)


def _bundle(*blocks):
    return {"doc_id": "doc_test", "content_blocks": list(blocks)}


def _heading(block_id: str, path: list[str], order: int = 1):
    return {
        "block_id": block_id,
        "kind": "heading",
        "heading_path": path,
        "doc_order_index": order,
        "raw_text": path[-1],
        "meta": {"heading_level": len(path)},
    }


def test_automatic_equals_effective_scope_items():
    bundle = _bundle(_heading("C0001", ["Scope A"]))
    items = project_configuration_scope_items(bundle, ["C0001"])
    assert items == [
        {"anchor_block_id": "C0001", "heading_path": ["Scope A"], "doc_order_index": 1}
    ]
    display = project_configuration_selection_scope_display(
        bundle,
        automatic_anchor_block_ids=["C0001"],
        effective_anchor_block_ids=["C0001"],
        added_anchor_block_ids=[],
        removed_anchor_block_ids=[],
    )
    assert display["automatic_scope_items"] == display["effective_scope_items"]


def test_added_and_removed_scope_items():
    bundle = _bundle(
        _heading("C0001", ["Parent", "Child A"], order=1),
        _heading("C0002", ["Parent", "Child B"], order=2),
    )
    display = project_configuration_selection_scope_display(
        bundle,
        automatic_anchor_block_ids=["C0001"],
        effective_anchor_block_ids=["C0002"],
        added_anchor_block_ids=["C0002"],
        removed_anchor_block_ids=["C0001"],
    )
    assert display["added_scope_items"][0]["heading_path"] == ["Parent", "Child B"]
    assert display["removed_scope_items"][0]["heading_path"] == ["Parent", "Child A"]


def test_missing_anchor_fails_closed():
    bundle = _bundle(_heading("C0001", ["Scope A"]))
    with pytest.raises(DocumentReadValidationError, match="absent from canonical"):
        project_configuration_scope_items(bundle, ["C0099"])


def test_canonical_heading_order_is_carried_without_reordering_selection():
    bundle = _bundle(
        _heading("C0099", ["Early"], order=0), _heading("C0001", ["Late"], order=12)
    )
    items = project_configuration_scope_items(bundle, ["C0001", "C0099"])
    assert [item["doc_order_index"] for item in items] == [12, 0]
    assert [item["anchor_block_id"] for item in items] == ["C0001", "C0099"]


@pytest.mark.parametrize("order", [None, -1, True, 1.5, "1"])
def test_missing_or_invalid_canonical_heading_order_fails_closed(order):
    heading = _heading("C0001", ["Scope A"], order=order)
    if order is None:
        heading.pop("doc_order_index")
    with pytest.raises(DocumentReadValidationError, match="document order"):
        project_configuration_scope_items(_bundle(heading), ["C0001"])


def test_non_heading_anchor_rejected():
    bundle = _bundle(
        {
            "block_id": "C0002",
            "kind": "paragraph",
            "heading_path": ["Scope A"],
            "doc_order_index": 2,
            "raw_text": "text",
        }
    )
    with pytest.raises(DocumentReadValidationError, match="not a canonical heading"):
        project_configuration_scope_items(bundle, ["C0002"])


def test_real_task_run_clinical_safety_scope_headings(representative_qc_task_run):
    from task.clinical_trial_doc_qc.report_read import load_qc_report

    project_root, task_run_id = representative_qc_task_run
    report = load_qc_report(project_root=project_root, task_run_id=task_run_id)
    selections = report["contributions"][0]["configuration"]["selections"]
    safety = next(
        row for row in selections if row["filter_job_id"] == "dsur_clinical_safety"
    )
    assert safety["added_anchor_block_ids"] == []
    assert safety["removed_anchor_block_ids"] == []
    assert [
        item["anchor_block_id"] for item in safety["automatic_scope_items"]
    ] == safety["automatic_anchor_block_ids"]
    assert safety["automatic_scope_items"][0]["heading_path"]
    assert all(item["heading_path"] for item in safety["automatic_scope_items"])
    overview = next(
        row for row in selections if row["filter_job_id"] == "dsur_overview"
    )
    assert len(overview["effective_scope_items"]) == len(
        overview["effective_anchor_block_ids"]
    )
