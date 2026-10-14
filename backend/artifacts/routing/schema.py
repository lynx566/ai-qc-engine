"""Route stage artifact schema validation (route-neutral bundles, no LLM fields)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from artifacts.routing.types import ROUTES, Route

ROUTE_SCHEMA_VERSION = "0.7.0"
ROUTE_STAGE = "route"

_PROJECTED_ROUTE_INPUT_ID_PREFIX = "projected_route_"
_PROJECTION_INPUT_REF_REQUIRED_KEYS = frozenset(
    {
        "filter_output_projection_bundle_id",
        "filter_job_id",
        "zone_key",
    }
)

ROUTED_UNITS_ROUTE_FILENAMES: dict[Route, str] = {
    "aggregate": "routed_units_aggregate.json",
    "table": "routed_units_table.json",
    "case": "routed_units_case.json",
    "unknown": "routed_units_unknown.json",
}

ROUTING_MANIFEST_FILENAME = "routing_manifest.json"

_FORBIDDEN_ROUTE_ARTIFACT_KEYS = frozenset(
    {
        "instructions",
        "messages",
        "prompt_name",
        "prompt_version",
        "tag_profile_ref",
        "expected_schema_ref",
        "expected_schema",
        "llm_mode",
        "model",
        "max_tokens",
        "temporal_context",
        "program_registry",
        "pre_llm_review_state_ref",
        "doc_meta",
        "llm_input_bundle_id",
        "route_input_files",
    }
)


def build_routed_unit_bundle_id(*, route_input_id: str, route: Route) -> str:
    return f"routed_units_{route}_{route_input_id}"


def build_route_routing_manifest_id(*, route_input_id: str) -> str:
    return f"route_routing_{route_input_id}"


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def is_projected_source_route_input_id(route_input_id: str) -> bool:
    """Return whether ``route_input_id`` denotes canonical projected-source Route entry."""

    return route_input_id.startswith(_PROJECTED_ROUTE_INPUT_ID_PREFIX)


def _validate_source_refs_projection_input_refs(
    source_refs: Mapping[str, Any],
    *,
    route_input_id: str,
) -> None:
    if not is_projected_source_route_input_id(route_input_id):
        return

    field = "source_refs.projection_input_refs"
    projection_input_refs = source_refs.get("projection_input_refs")
    if not isinstance(projection_input_refs, list):
        raise TypeError(f"{field} must be a list")
    if not projection_input_refs:
        raise ValueError(f"{field} must be non-empty for projected-source route artifacts")

    seen_bundle_ids: set[str] = set()
    for index, ref in enumerate(projection_input_refs):
        ref_field = f"{field}[{index}]"
        if not isinstance(ref, Mapping):
            raise TypeError(f"{ref_field} must be an object")
        extra = set(ref) - _PROJECTION_INPUT_REF_REQUIRED_KEYS
        if extra:
            raise ValueError(f"{ref_field} has unexpected keys: {sorted(extra)!r}")
        missing = _PROJECTION_INPUT_REF_REQUIRED_KEYS - set(ref)
        if missing:
            raise ValueError(f"{ref_field} is missing required keys: {sorted(missing)!r}")
        bundle_id = _require_str(
            ref.get("filter_output_projection_bundle_id"),
            field=f"{ref_field}.filter_output_projection_bundle_id",
        )
        if bundle_id in seen_bundle_ids:
            raise ValueError(
                f"{field} contains duplicate filter_output_projection_bundle_id "
                f"{bundle_id!r}"
            )
        seen_bundle_ids.add(bundle_id)
        _require_str(
            ref.get("filter_job_id"),
            field=f"{ref_field}.filter_job_id",
        )
        _require_str(ref.get("zone_key"), field=f"{ref_field}.zone_key")


def assert_route_bundle_route_neutral(payload: Mapping[str, Any]) -> None:
    for key in _FORBIDDEN_ROUTE_ARTIFACT_KEYS:
        if key in payload:
            raise ValueError(
                f"route artifact must not contain LLM/prepare field {key!r}"
            )


def validate_routed_unit_bundle(
    bundle: Mapping[str, Any],
    *,
    expected_route: Route | None = None,
    expected_doc_id: str | None = None,
    expected_zone_key: str | None = None,
) -> None:
    """Validate a single routed-units bundle envelope and its units."""
    assert_route_bundle_route_neutral(bundle)

    stage = _require_str(bundle.get("stage"), field="stage")
    if stage != ROUTE_STAGE:
        raise ValueError(f"stage must be {ROUTE_STAGE!r}, got {stage!r}")

    schema_version = _require_str(bundle.get("schema_version"), field="schema_version")
    if schema_version != ROUTE_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported route schema_version {schema_version!r}; "
            f"expected {ROUTE_SCHEMA_VERSION!r}"
        )

    _require_str(bundle.get("routed_unit_bundle_id"), field="routed_unit_bundle_id")
    route = _require_str(bundle.get("route"), field="route")
    if route not in ROUTES:
        raise ValueError(f"invalid route {route!r}; expected one of {ROUTES!r}")
    if expected_route is not None and route != expected_route:
        raise ValueError(
            f"route mismatch: expected {expected_route!r}, got {route!r}"
        )

    doc_id = _require_str(bundle.get("doc_id"), field="doc_id")
    if expected_doc_id is not None and doc_id != expected_doc_id:
        raise ValueError(
            f"doc_id mismatch: expected {expected_doc_id!r}, got {doc_id!r}"
        )

    zone_key = bundle.get("zone_key")
    if zone_key is not None and not isinstance(zone_key, str):
        raise ValueError("zone_key must be a string")
    if expected_zone_key is not None and zone_key != expected_zone_key:
        raise ValueError(
            f"zone_key mismatch: expected {expected_zone_key!r}, got {zone_key!r}"
        )

    _require_str(bundle.get("file_hash"), field="file_hash")

    source_refs = bundle.get("source_refs")
    if not isinstance(source_refs, dict):
        raise TypeError("source_refs must be an object")
    _require_str(
        source_refs.get("route_input_id"),
        field="source_refs.route_input_id",
    )
    _require_str(
        source_refs.get("block_manifest_id"),
        field="source_refs.block_manifest_id",
    )
    _require_str(
        source_refs.get("analysis_bundle_id"),
        field="source_refs.analysis_bundle_id",
    )
    route_input_id = str(source_refs["route_input_id"])
    _validate_source_refs_projection_input_refs(
        source_refs,
        route_input_id=route_input_id,
    )

    units = bundle.get("units")
    if not isinstance(units, list):
        raise TypeError("units must be a list")

    seen_unit_ids: set[str] = set()
    for index, unit in enumerate(units):
        if not isinstance(unit, dict):
            raise TypeError(f"units[{index}] must be an object")
        unit_id = _require_str(unit.get("unit_id"), field=f"units[{index}].unit_id")
        if unit_id in seen_unit_ids:
            raise ValueError(f"duplicate unit_id {unit_id!r}")
        seen_unit_ids.add(unit_id)
        unit_route = _require_str(unit.get("route"), field=f"units[{index}].route")
        if unit_route != route:
            raise ValueError(
                f"units[{index}].route={unit_route!r} "
                f"does not match bundle route={route!r}"
            )
        if unit_route not in ROUTES:
            raise ValueError(f"units[{index}].route invalid: {unit_route!r}")
        _validate_text_unit_primary_sentence_contract(
            unit,
            unit_path=f"units[{index}]",
        )


def _text_unit_requires_primary_sentences(unit: Mapping[str, Any]) -> bool:
    if unit.get("unit_kind") != "text_unit":
        return False
    source_stage = str(unit.get("source_stage") or "").strip()
    if source_stage == "filter_projection":
        return True
    sentences = unit.get("sentences")
    return isinstance(sentences, list) and bool(sentences)


def _validate_text_unit_primary_sentence_contract(
    unit: Mapping[str, Any],
    *,
    unit_path: str,
) -> None:
    from artifacts.routing.primary_sentence_contract import (
        validate_text_unit_body_consistency,
    )

    if not _text_unit_requires_primary_sentences(unit):
        return

    sentences = unit.get("sentences")
    if not isinstance(sentences, list):
        raise TypeError(f"{unit_path}.sentences must be a list")
    if not sentences:
        raise ValueError(f"{unit_path}.sentences must be non-empty")

    validate_text_unit_body_consistency(unit, unit_path=unit_path)

    for sentence_index, sentence in enumerate(sentences):
        if not isinstance(sentence, dict):
            raise TypeError(f"{unit_path}.sentences[{sentence_index}] must be an object")
        _require_str(
            sentence.get("sentence_id"),
            field=f"{unit_path}.sentences[{sentence_index}].sentence_id",
        )
        _require_str(
            sentence.get("source_block_id"),
            field=f"{unit_path}.sentences[{sentence_index}].source_block_id",
        )
        _require_str(
            sentence.get("text"),
            field=f"{unit_path}.sentences[{sentence_index}].text",
        )


def validate_route_routing_manifest(manifest: Mapping[str, Any]) -> None:
    assert_route_bundle_route_neutral(manifest)

    stage = _require_str(manifest.get("stage"), field="stage")
    if stage != ROUTE_STAGE:
        raise ValueError(f"stage must be {ROUTE_STAGE!r}, got {stage!r}")

    schema_version = _require_str(manifest.get("schema_version"), field="schema_version")
    if schema_version != ROUTE_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported route schema_version {schema_version!r}; "
            f"expected {ROUTE_SCHEMA_VERSION!r}"
        )

    _require_str(manifest.get("routing_manifest_id"), field="routing_manifest_id")
    _require_str(manifest.get("doc_id"), field="doc_id")
    manifest_zone_key = manifest.get("zone_key")
    if manifest_zone_key is not None and not isinstance(manifest_zone_key, str):
        raise ValueError("zone_key must be a string")

    route_counts = manifest.get("route_counts")
    if not isinstance(route_counts, dict):
        raise TypeError("route_counts must be an object")
    for route in ROUTES:
        count = route_counts.get(route)
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"route_counts[{route!r}] must be a non-negative int")

    route_artifact_files = manifest.get("route_artifact_files")
    if not isinstance(route_artifact_files, dict):
        raise TypeError("route_artifact_files must be an object")
    for route in ROUTES:
        entry = route_artifact_files.get(route)
        if not isinstance(entry, dict):
            raise TypeError(f"route_artifact_files[{route!r}] must be an object")
        _require_str(entry.get("path"), field=f"route_artifact_files[{route}].path")
        _require_str(
            entry.get("routed_unit_bundle_id"),
            field=f"route_artifact_files[{route}].routed_unit_bundle_id",
        )

    units = manifest.get("units")
    if not isinstance(units, list):
        raise TypeError("units must be a list")

    source_refs = manifest.get("source_refs")
    if not isinstance(source_refs, dict):
        raise TypeError("source_refs must be an object")
    route_input_id = _require_str(
        source_refs.get("route_input_id"),
        field="source_refs.route_input_id",
    )
    _validate_source_refs_projection_input_refs(
        source_refs,
        route_input_id=route_input_id,
    )


def validate_route_upstream_identity(
    *,
    coverage_bundle: Mapping[str, Any],
    block_manifest: Mapping[str, Any],
    doc_meta_bundle: Mapping[str, Any],
    analysis_bundle: Mapping[str, Any],
) -> tuple[str, str]:
    """Fail fast on doc_id / file_hash / bundle ref mismatches across upstream inputs."""
    from core.document.doc_identity import require_bundle_file_hash

    coverage_doc_id = _require_str(coverage_bundle.get("doc_id"), field="coverage_bundle.doc_id")
    manifest_doc_id = _require_str(
        block_manifest.get("doc_id"),
        field="block_manifest.doc_id",
    )
    meta_doc_id = _require_str(
        doc_meta_bundle.get("doc_id"),
        field="doc_meta_bundle.doc_id",
    )
    analysis_doc_id = _require_str(
        analysis_bundle.get("doc_id"),
        field="analysis_bundle.doc_id",
    )
    doc_ids = {coverage_doc_id, manifest_doc_id, meta_doc_id, analysis_doc_id}
    if len(doc_ids) != 1:
        raise ValueError(
            "doc_id mismatch across route upstream inputs: "
            f"coverage={coverage_doc_id!r}, block_manifest={manifest_doc_id!r}, "
            f"doc_meta_bundle={meta_doc_id!r}, analysis={analysis_doc_id!r}"
        )

    coverage_file_hash = require_bundle_file_hash(
        coverage_bundle,
        label="coverage_bundle",
    )
    manifest_file_hash = require_bundle_file_hash(
        block_manifest,
        label="block_manifest",
    )
    if coverage_file_hash != manifest_file_hash:
        raise ValueError(
            f"file_hash mismatch: coverage_bundle={coverage_file_hash!r} "
            f"block_manifest={manifest_file_hash!r}"
        )
    meta_hash_raw = doc_meta_bundle.get("file_hash")
    if isinstance(meta_hash_raw, str) and meta_hash_raw.strip() and meta_hash_raw.strip() != coverage_file_hash:
        raise ValueError(
            f"file_hash mismatch: coverage_bundle={coverage_file_hash!r} "
            f"doc_meta_bundle={meta_hash_raw.strip()!r}"
        )
    analysis_hash_raw = analysis_bundle.get("file_hash")
    if isinstance(analysis_hash_raw, str) and analysis_hash_raw.strip() and analysis_hash_raw.strip() != coverage_file_hash:
        raise ValueError(
            f"file_hash mismatch: coverage_bundle={coverage_file_hash!r} "
            f"analysis_bundle={analysis_hash_raw.strip()!r}"
        )

    coverage_manifest_ref = coverage_bundle.get("block_manifest_ref") or {}
    coverage_manifest_id = _require_str(
        coverage_manifest_ref.get("block_manifest_id"),
        field="coverage_bundle.block_manifest_ref.block_manifest_id",
    )
    block_manifest_id = _require_str(
        block_manifest.get("block_manifest_id"),
        field="block_manifest.block_manifest_id",
    )
    if coverage_manifest_id != block_manifest_id:
        raise ValueError("block_manifest_id mismatch between coverage and block_manifest")

    coverage_analysis_ref = coverage_bundle.get("analysis_bundle_ref") or {}
    coverage_analysis_id = _require_str(
        coverage_analysis_ref.get("analysis_bundle_id"),
        field="coverage_bundle.analysis_bundle_ref.analysis_bundle_id",
    )
    analysis_bundle_id = _require_str(
        analysis_bundle.get("analysis_bundle_id"),
        field="analysis_bundle.analysis_bundle_id",
    )
    if coverage_analysis_id != analysis_bundle_id:
        raise ValueError("analysis_bundle_id mismatch between coverage and analysis")

    manifest_analysis_ref = block_manifest.get("analysis_bundle_ref") or {}
    manifest_analysis_id = str(
        (manifest_analysis_ref.get("analysis_bundle_id") or "").strip()
    )
    if manifest_analysis_id and manifest_analysis_id != analysis_bundle_id:
        raise ValueError(
            "analysis_bundle_id mismatch between block_manifest and analysis"
        )

    zone_key = _require_str(coverage_bundle.get("zone_key"), field="coverage_bundle.zone_key")
    _require_str(
        coverage_bundle.get("coverage_bundle_id"),
        field="coverage_bundle.coverage_bundle_id",
    )
    return coverage_doc_id, zone_key


def validate_route_projected_upstream_identity(
    *,
    block_manifest: Mapping[str, Any],
    doc_meta_bundle: Mapping[str, Any],
    analysis_bundle: Mapping[str, Any],
) -> tuple[str, str]:
    """Validate doc/file identity for projected-source Route entry."""

    from core.document.doc_identity import require_bundle_file_hash

    manifest_doc_id = _require_str(
        block_manifest.get("doc_id"),
        field="block_manifest.doc_id",
    )
    meta_doc_id = _require_str(
        doc_meta_bundle.get("doc_id"),
        field="doc_meta_bundle.doc_id",
    )
    analysis_doc_id = _require_str(
        analysis_bundle.get("doc_id"),
        field="analysis_bundle.doc_id",
    )
    doc_ids = {manifest_doc_id, meta_doc_id, analysis_doc_id}
    if len(doc_ids) != 1:
        raise ValueError(
            "doc_id mismatch across projected-route upstream inputs: "
            f"block_manifest={manifest_doc_id!r}, doc_meta_bundle={meta_doc_id!r}, "
            f"analysis={analysis_doc_id!r}"
        )

    manifest_file_hash = require_bundle_file_hash(
        block_manifest,
        label="block_manifest",
    )
    meta_hash_raw = doc_meta_bundle.get("file_hash")
    if isinstance(meta_hash_raw, str) and meta_hash_raw.strip() and meta_hash_raw.strip() != manifest_file_hash:
        raise ValueError(
            f"file_hash mismatch: block_manifest={manifest_file_hash!r} "
            f"doc_meta_bundle={meta_hash_raw.strip()!r}"
        )
    analysis_hash_raw = analysis_bundle.get("file_hash")
    if isinstance(analysis_hash_raw, str) and analysis_hash_raw.strip() and analysis_hash_raw.strip() != manifest_file_hash:
        raise ValueError(
            f"file_hash mismatch: block_manifest={manifest_file_hash!r} "
            f"analysis_bundle={analysis_hash_raw.strip()!r}"
        )

    return manifest_doc_id, manifest_file_hash


def validate_route_projection_static_upstream_document_identity(
    *,
    projection_doc_id: str,
    projection_file_hash: str,
    block_manifest: Mapping[str, Any],
    doc_meta_bundle: Mapping[str, Any],
    analysis_bundle: Mapping[str, Any],
) -> tuple[str, str]:
    """Fail fast when projection fan-in identity diverges from static upstream."""

    static_doc_id, static_file_hash = validate_route_projected_upstream_identity(
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
        analysis_bundle=analysis_bundle,
    )
    if projection_doc_id != static_doc_id:
        raise ValueError(
            "doc_id mismatch between projection fan-in and static upstream: "
            f"projection={projection_doc_id!r} static_upstream={static_doc_id!r}"
        )
    if projection_file_hash != static_file_hash:
        raise ValueError(
            "file_hash mismatch between projection fan-in and static upstream: "
            f"projection={projection_file_hash!r} static_upstream={static_file_hash!r}"
        )
    return static_doc_id, static_file_hash
