"""Concrete lifecycle vocabulary and validators for clinical-safety aggregate evidence.

Ownership: ``clinical_trial_doc × clinical_safety × aggregate_evidence``.

These phase labels and validators apply to the installed aggregate-evidence
implementation only. Generic ESP artifact contracts must not import this
module unless they are building or validating that concrete artifact family.
"""

from __future__ import annotations

from typing import Any, Mapping

from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE
from artifacts.routing.schema import (
    ROUTED_UNITS_ROUTE_FILENAMES,
    validate_route_routing_manifest,
    validate_routed_unit_bundle,
)

EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE = "prepare"
EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE = "assess"
EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_PHASE = "eligibility"
EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE = "assemble"

ASSESSMENT_INPUT_SCHEMA_VERSION = "1.4.0"
ASSESSMENT_OUTPUT_SCHEMA_VERSION = "1.0.0"


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def validate_aggregate_evidence_prepare_route_artifacts(
    *,
    aggregate_bundle: Mapping[str, Any],
    routing_manifest: Mapping[str, Any],
    projected_fan_in: bool = False,
) -> None:
    """Fail fast when selected aggregate route artifacts are inconsistent."""
    doc_id = _require_str(aggregate_bundle.get("doc_id"), field="doc_id")
    zone_key_raw = aggregate_bundle.get("zone_key")
    zone_key = str(zone_key_raw or "").strip()
    if not projected_fan_in:
        zone_key = _require_str(zone_key_raw, field="zone_key")

    validate_routed_unit_bundle(
        aggregate_bundle,
        expected_route="aggregate",
        expected_doc_id=doc_id,
        expected_zone_key=zone_key if zone_key else None,
    )

    if routing_manifest.get("routing_manifest_id") is None:
        raise ValueError("routing_manifest.routing_manifest_id is required")

    validate_route_routing_manifest(routing_manifest)

    manifest_doc_id = _require_str(routing_manifest.get("doc_id"), field="doc_id")
    manifest_zone = str(routing_manifest.get("zone_key") or "").strip()
    if manifest_doc_id != doc_id:
        raise ValueError(
            f"routing_manifest doc_id mismatch: manifest={manifest_doc_id!r} "
            f"aggregate={doc_id!r}"
        )
    if zone_key and manifest_zone and manifest_zone != zone_key:
        raise ValueError(
            f"routing_manifest zone_key mismatch: manifest={manifest_zone!r} "
            f"aggregate={zone_key!r}"
        )

    route_artifact_files = routing_manifest.get("route_artifact_files") or {}
    aggregate_entry = route_artifact_files.get("aggregate")
    if not isinstance(aggregate_entry, dict):
        raise ValueError("route_artifact_files['aggregate'] must be an object")
    expected_filename = ROUTED_UNITS_ROUTE_FILENAMES["aggregate"]
    actual_path = _require_str(
        aggregate_entry.get("path"),
        field="route_artifact_files[aggregate].path",
    )
    if actual_path != expected_filename:
        raise ValueError(
            f"route_artifact_files['aggregate'].path={actual_path!r} "
            f"expected {expected_filename!r}"
        )
    manifest_aggregate_id = _require_str(
        aggregate_entry.get("routed_unit_bundle_id"),
        field="route_artifact_files[aggregate].routed_unit_bundle_id",
    )
    aggregate_id = _require_str(
        aggregate_bundle.get("routed_unit_bundle_id"),
        field="routed_unit_bundle_id",
    )
    if manifest_aggregate_id != aggregate_id:
        raise ValueError(
            "routing_manifest aggregate routed_unit_bundle_id mismatch"
        )


def validate_assessment_input(payload: Mapping[str, Any]) -> None:
    """Validate clinical-safety aggregate-evidence assessment_input envelope."""
    stage = _require_str(payload.get("stage"), field="stage")
    if stage != EVIDENCE_SOURCE_PREPARATION_STAGE:
        raise ValueError(
            f"stage must be {EVIDENCE_SOURCE_PREPARATION_STAGE!r}, got {stage!r}"
        )

    phase = _require_str(payload.get("phase"), field="phase")
    if phase != EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE:
        raise ValueError(
            f"phase must be {EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE!r}, "
            f"got {phase!r}"
        )

    source_stage = _require_str(payload.get("source_stage"), field="source_stage")
    if source_stage != "route":
        raise ValueError(f"source_stage must be 'route', got {source_stage!r}")

    schema_version = _require_str(payload.get("schema_version"), field="schema_version")
    if schema_version != ASSESSMENT_INPUT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported assessment_input schema_version {schema_version!r}; "
            f"expected {ASSESSMENT_INPUT_SCHEMA_VERSION!r}"
        )

    route = _require_str(payload.get("route"), field="route")
    if route != "aggregate":
        raise ValueError(f"route must be 'aggregate', got {route!r}")

    if "tag_profile_ref" in payload:
        raise ValueError("assessment_input must not include legacy field tag_profile_ref")

    _require_str(payload.get("llm_input_bundle_id"), field="llm_input_bundle_id")

    _require_str(
        payload.get("assessment_profile_ref"),
        field="assessment_profile_ref",
    )

    runtime_context_ref = payload.get("runtime_context_ref")
    if not isinstance(runtime_context_ref, dict):
        raise ValueError("runtime_context_ref must be an object")
    _require_str(
        runtime_context_ref.get("runtime_context_id"),
        field="runtime_context_ref.runtime_context_id",
    )

    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
        validate_compact_assessment_input_shape,
    )

    validate_compact_assessment_input_shape(payload)


__all__ = [
    "ASSESSMENT_INPUT_SCHEMA_VERSION",
    "ASSESSMENT_OUTPUT_SCHEMA_VERSION",
    "EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE",
    "EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE",
    "EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_PHASE",
    "EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE",
    "validate_aggregate_evidence_prepare_route_artifacts",
    "validate_assessment_input",
]
