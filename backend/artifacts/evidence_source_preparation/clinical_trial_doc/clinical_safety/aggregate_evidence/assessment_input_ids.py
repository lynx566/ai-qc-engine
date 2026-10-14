"""Deterministic llm_input_bundle_id builders for Aggregate Evidence prepare."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

from core.serialization import stable_json_dumps

from artifacts.routing.types import Route


def build_llm_input_bundle_id(
    *,
    coverage_bundle_id: str,
    route: Route | None = None,
) -> str:
    if route is not None:
        return f"llm_input_{route}_{coverage_bundle_id}"
    return f"llm_input_{coverage_bundle_id}"


def build_projected_fan_in_llm_input_bundle_id(
    *,
    file_hash: str,
    semantic_module_id: str,
    projection_input_refs: Sequence[Mapping[str, str]],
    route: Route | None = "aggregate",
) -> str:
    """Deterministic aggregate identity for projected multi-source fan-in executions."""

    resolved_file_hash = str(file_hash or "").strip()
    resolved_semantic_module_id = str(semantic_module_id or "").strip()
    if not resolved_file_hash:
        raise ValueError("file_hash is required for projected fan-in llm_input_bundle_id")
    if not resolved_semantic_module_id:
        raise ValueError(
            "semantic_module_id is required for projected fan-in llm_input_bundle_id"
        )
    if not projection_input_refs:
        raise ValueError(
            "projection_input_refs must be non-empty for projected fan-in llm_input_bundle_id"
        )

    ordered_refs: list[dict[str, str]] = []
    for ref in projection_input_refs:
        filter_job_id = str(ref.get("filter_job_id") or "").strip()
        zone_key = str(ref.get("zone_key") or "").strip()
        bundle_id = str(ref.get("filter_output_projection_bundle_id") or "").strip()
        if not filter_job_id or not zone_key or not bundle_id:
            raise ValueError(
                "projection_input_refs entries require filter_job_id, zone_key, and "
                "filter_output_projection_bundle_id"
            )
        ordered_refs.append(
            {
                "filter_output_projection_bundle_id": bundle_id,
                "filter_job_id": filter_job_id,
                "zone_key": zone_key,
            }
        )

    payload = {
        "file_hash": resolved_file_hash,
        "semantic_module_id": resolved_semantic_module_id,
        "projection_input_refs": ordered_refs,
    }
    digest_hex = hashlib.sha256(stable_json_dumps(payload).encode("utf-8")).hexdigest()
    route_token = route or "aggregate"
    return f"llm_input_{route_token}_projected_{digest_hex}"
