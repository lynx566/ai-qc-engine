"""Build route-neutral artifact bundles from ``RoutedUnitSet``."""

from __future__ import annotations

from typing import Any

from runtime.run_layout import utc_now_iso

from artifacts.routing.schema import (
    ROUTE_SCHEMA_VERSION,
    ROUTE_STAGE,
    ROUTED_UNITS_ROUTE_FILENAMES,
    build_route_routing_manifest_id,
    build_routed_unit_bundle_id,
    validate_route_routing_manifest,
    validate_routed_unit_bundle,
)
from artifacts.routing.types import ROUTES, Route, RoutedUnitSet


def _manifest_block_kinds(unit: dict[str, Any]) -> list[str]:
    if unit.get("unit_kind") == "table_unit":
        return [
            str(component.get("block_kind") or "")
            for component in unit.get("components") or []
            if isinstance(component, dict) and component.get("block_kind")
        ]
    candidate_kinds = unit.get("candidate_block_kinds")
    if candidate_kinds:
        return list(candidate_kinds)
    return list(unit.get("block_kinds") or [])


def _manifest_unit_entry(unit: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "unit_id": unit.get("unit_id"),
        "route": unit.get("route"),
        "unit_kind": unit.get("unit_kind"),
        "route_basis": unit.get("route_basis"),
        "route_matched_terms": list(unit.get("route_matched_terms") or []),
        "heading_path": list(unit.get("heading_path") or []),
        "source_block_ids": list(unit.get("source_block_ids") or []),
        "context_block_ids": list(unit.get("context_block_ids") or []),
        "source_table_ids": list(unit.get("source_table_ids") or []),
    }
    if unit.get("unit_kind") == "table_unit":
        components = unit.get("components") or []
        entry["all_source_refs"] = list(unit.get("all_source_refs") or [])
        entry["component_roles"] = [
            str(component.get("component_role") or "")
            for component in components
            if isinstance(component, dict) and component.get("component_role")
        ]
        entry["component_status"] = dict(unit.get("component_status") or {})
    else:
        entry["all_source_block_ids"] = list(
            unit.get("all_source_block_ids") or unit.get("source_block_ids") or []
        )
        entry["candidate_block_kinds"] = _manifest_block_kinds(unit)
    return entry


def routing_manifest_units(
    units_by_route: dict[Route, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Lightweight per-unit routing entries for routing_manifest.json."""
    manifest_units: list[dict[str, Any]] = []
    for route in ROUTES:
        manifest_units.extend(
            _manifest_unit_entry(unit) for unit in units_by_route[route]
        )
    return manifest_units


def _build_source_refs(
    *,
    route_input_envelope: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any],
) -> dict[str, Any]:
    refs: dict[str, Any] = {
        "route_input_id": str(route_input_envelope["route_input_id"]),
        "block_manifest_id": str(block_manifest["block_manifest_id"]),
        "analysis_bundle_id": str(analysis_bundle["analysis_bundle_id"]),
    }
    meta_id = str(doc_meta_bundle.get("doc_meta_bundle_id") or "").strip()
    if meta_id:
        refs["doc_meta_bundle_id"] = meta_id
    projection_input_refs = route_input_envelope.get("projection_input_refs")
    if projection_input_refs is not None:
        refs["projection_input_refs"] = [
            dict(ref) for ref in projection_input_refs
        ]
    return refs


def build_routed_unit_bundle(
    *,
    route: Route,
    units: list[dict[str, Any]],
    route_input_envelope: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    route_input_id = str(route_input_envelope["route_input_id"])
    file_hash = str(
        route_input_envelope.get("file_hash") or block_manifest.get("file_hash") or ""
    )
    bundle: dict[str, Any] = {
        "routed_unit_bundle_id": build_routed_unit_bundle_id(
            route_input_id=route_input_id,
            route=route,
        ),
        "schema_version": ROUTE_SCHEMA_VERSION,
        "stage": ROUTE_STAGE,
        "doc_id": str(route_input_envelope["doc_id"]),
        "file_hash": file_hash,
        "zone_key": str(route_input_envelope.get("zone_key") or ""),
        "route": route,
        "source_refs": _build_source_refs(
            route_input_envelope=route_input_envelope,
            block_manifest=block_manifest,
            doc_meta_bundle=doc_meta_bundle,
            analysis_bundle=analysis_bundle,
        ),
        "units": [dict(unit) for unit in units],
        "created_at": created_at or utc_now_iso(),
    }
    validate_routed_unit_bundle(bundle, expected_route=route)
    return bundle


def build_route_routing_manifest(
    *,
    routed_bundles: dict[Route, dict[str, Any]],
    units_by_route: dict[Route, list[dict[str, Any]]],
    route_counts: dict[str, int],
    route_input_envelope: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    route_input_id = str(route_input_envelope["route_input_id"])
    counts_by_route = {
        route: route_counts[f"{route}_unit_count"] for route in ROUTES
    }
    manifest: dict[str, Any] = {
        "routing_manifest_id": build_route_routing_manifest_id(
            route_input_id=route_input_id,
        ),
        "schema_version": ROUTE_SCHEMA_VERSION,
        "stage": ROUTE_STAGE,
        "doc_id": str(route_input_envelope["doc_id"]),
        "zone_key": str(route_input_envelope.get("zone_key") or ""),
        "route_counts": counts_by_route,
        "unit_count": route_counts.get("total_routed_unit_count", 0),
        "unknown_unit_count": counts_by_route.get("unknown", 0),
        "route_artifact_files": {
            route: {
                "path": ROUTED_UNITS_ROUTE_FILENAMES[route],
                "routed_unit_bundle_id": routed_bundles[route]["routed_unit_bundle_id"],
            }
            for route in ROUTES
        },
        "units": routing_manifest_units(units_by_route),
        "source_refs": _build_source_refs(
            route_input_envelope=route_input_envelope,
            block_manifest=block_manifest,
            doc_meta_bundle=doc_meta_bundle,
            analysis_bundle=analysis_bundle,
        ),
        "created_at": created_at or utc_now_iso(),
    }
    validate_route_routing_manifest(manifest)
    return manifest


def build_route_stage_artifacts(
    *,
    routed: RoutedUnitSet,
    route_input_envelope: dict[str, Any],
    block_manifest: dict[str, Any],
    doc_meta_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    """Return per-route bundles, routing manifest, and route counts."""
    timestamp = created_at or utc_now_iso()
    routed_bundles: dict[Route, dict[str, Any]] = {}
    for route in ROUTES:
        routed_bundles[route] = build_routed_unit_bundle(
            route=route,
            units=routed.units_by_route[route],
            route_input_envelope=route_input_envelope,
            block_manifest=block_manifest,
            doc_meta_bundle=doc_meta_bundle,
            analysis_bundle=analysis_bundle,
            created_at=timestamp,
        )
    routing_manifest = build_route_routing_manifest(
        routed_bundles=routed_bundles,
        units_by_route=routed.units_by_route,
        route_counts=routed.route_counts,
        route_input_envelope=route_input_envelope,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=analysis_bundle,
        created_at=timestamp,
    )
    return {
        "routed_bundles": routed_bundles,
        "routing_manifest": routing_manifest,
        "route_counts": routed.route_counts,
        "units_by_route": routed.units_by_route,
    }
