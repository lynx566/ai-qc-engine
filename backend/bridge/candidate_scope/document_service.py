"""Bridge service for runtime Candidate Scope document read."""

from __future__ import annotations

from typing import Any

from application.document_consistency_qc.document_read import (
    resolve_slot_extract_bundle,
)
from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig


def load_candidate_scope_slot_document(
    *,
    config: BridgeRuntimeConfig,
    flow_run_id: str,
    slot_id: str,
) -> dict[str, Any]:
    """Return Extract Bundle JSON for one flow participant slot."""

    return resolve_slot_extract_bundle(
        project_root=config.workspace_root,
        flow_run_id=flow_run_id,
        slot_id=slot_id,
        require_doc_meta_bundle_reference=False,
    )


__all__ = ["load_candidate_scope_slot_document"]
