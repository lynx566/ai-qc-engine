"""Targeted tests for application runtime document read."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.document_consistency_qc.document_read import (
    DocumentReadNotFoundError,
    DocumentReadValidationError,
    resolve_slot_extract_bundle,
    resolve_slot_extract_bundle_path,
)
from execution_flow.document_consistency_qc.flow_loader import load_flow_run_execution
from runtime.io import load_json, save_json
from tests.candidate_scope_isolation import (
    prepare_paused_canonical_flow,
    prepare_paused_multi_slot_canonical_flow,
)


def test_single_slot_resolves_extract_bundle(tmp_path: Path) -> None:
    bridge_config, flow_run_id, slot_id = prepare_paused_canonical_flow(tmp_path)

    bundle = resolve_slot_extract_bundle(
        project_root=bridge_config.workspace_root,
        flow_run_id=flow_run_id,
        slot_id=slot_id,
    )

    execution = load_flow_run_execution(
        project_root=bridge_config.workspace_root,
        flow_run_id=flow_run_id,
    )
    slot = next(item for item in execution.slot_provenance if item.slot_id == slot_id)
    assert bundle["doc_id"] == slot.doc_id
    assert bundle["content_blocks"]
    assert any(block.get("raw_text") for block in bundle["content_blocks"])


def test_multi_slot_documents_do_not_cross(tmp_path: Path) -> None:
    bridge_config, flow_run_id, slot_ids = prepare_paused_multi_slot_canonical_flow(
        tmp_path
    )

    bundle_a = resolve_slot_extract_bundle(
        project_root=bridge_config.workspace_root,
        flow_run_id=flow_run_id,
        slot_id=slot_ids[0],
    )
    bundle_b = resolve_slot_extract_bundle(
        project_root=bridge_config.workspace_root,
        flow_run_id=flow_run_id,
        slot_id=slot_ids[1],
    )

    assert bundle_a["doc_id"] != bundle_b["doc_id"]


def test_invalid_slot_id_rejected(tmp_path: Path) -> None:
    bridge_config, flow_run_id, _slot_id = prepare_paused_canonical_flow(tmp_path)

    with pytest.raises(DocumentReadValidationError, match="not configured"):
        resolve_slot_extract_bundle(
            project_root=bridge_config.workspace_root,
            flow_run_id=flow_run_id,
            slot_id="missing_slot",
        )


def test_missing_extract_bundle_returns_read_error(tmp_path: Path) -> None:
    bridge_config, flow_run_id, slot_id = prepare_paused_canonical_flow(tmp_path)
    execution = load_flow_run_execution(
        project_root=bridge_config.workspace_root,
        flow_run_id=flow_run_id,
    )
    slot = next(item for item in execution.slot_provenance if item.slot_id == slot_id)
    bundle_path = resolve_slot_extract_bundle_path(
        execution=execution,
        slot_provenance=slot,
    )
    bundle_path.unlink()

    with pytest.raises(DocumentReadNotFoundError, match="extract bundle is missing"):
        resolve_slot_extract_bundle(
            project_root=bridge_config.workspace_root,
            flow_run_id=flow_run_id,
            slot_id=slot_id,
        )


def test_doc_id_mismatch_rejected(tmp_path: Path) -> None:
    bridge_config, flow_run_id, slot_id = prepare_paused_canonical_flow(tmp_path)
    execution = load_flow_run_execution(
        project_root=bridge_config.workspace_root,
        flow_run_id=flow_run_id,
    )
    slot = next(item for item in execution.slot_provenance if item.slot_id == slot_id)
    bundle_path = resolve_slot_extract_bundle_path(
        execution=execution,
        slot_provenance=slot,
    )
    bundle = load_json(bundle_path)
    bundle["doc_id"] = "doc_mismatch"
    save_json(bundle_path, bundle)

    with pytest.raises(DocumentReadValidationError, match="does not match"):
        resolve_slot_extract_bundle(
            project_root=bridge_config.workspace_root,
            flow_run_id=flow_run_id,
            slot_id=slot_id,
        )


def test_resolver_uses_participant_layout_not_global_extract_runs(
    tmp_path: Path,
) -> None:
    bridge_config, flow_run_id, slot_id = prepare_paused_canonical_flow(tmp_path)
    execution = load_flow_run_execution(
        project_root=bridge_config.workspace_root,
        flow_run_id=flow_run_id,
    )
    slot = next(item for item in execution.slot_provenance if item.slot_id == slot_id)
    bundle_path = resolve_slot_extract_bundle_path(
        execution=execution,
        slot_provenance=slot,
    )
    normalized = bundle_path.as_posix()
    assert "/participants/" in normalized
    assert "/extract/bundle.json" in normalized
    assert "runs/extract/" not in normalized

    bundle = resolve_slot_extract_bundle(
        project_root=bridge_config.workspace_root,
        flow_run_id=flow_run_id,
        slot_id=slot_id,
    )
    assert bundle["doc_id"] == slot.doc_id
