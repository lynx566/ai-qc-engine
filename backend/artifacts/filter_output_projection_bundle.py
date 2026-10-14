"""Persisted ``filter_output_projection_bundle.json`` contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core.document.doc_identity import validate_file_hash_format
from operations.filter_output_projection.contracts import (
    ALLOWED_PROJECTED_SOURCE_REPRESENTATION_KINDS,
    CanonicalSourceRef,
    FilterOutputProjectionStepResult,
    ProjectedSource,
    SemanticProjectionOutcome,
)
from operations.filter_output_projection.projected_sentence import (
    deserialize_projected_sentence,
    reject_legacy_projected_source_payload,
    serialize_projected_sentence,
    validate_projected_source_sentences,
)

FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME = "filter_output_projection_bundle.json"
FILTER_OUTPUT_PROJECTION_SCHEMA_VERSION = "0.4.0"
FILTER_OUTPUT_PROJECTION_ARTIFACT_TYPE = "filter_output_projection_bundle"

_FORBIDDEN_EXECUTION_KEYS = frozenset(
    {
        "consumed",
        "not_installed_consumer",
        "route_status",
        "execution_status",
        "consumer_installed",
    }
)

_ROOT_REQUIRED_KEYS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "filter_job_id",
        "doc_id",
        "file_hash",
        "zone_key",
        "projected_sources",
        "semantic_outcomes",
    }
)


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _reject_forbidden_execution_keys(payload: Mapping[str, Any], *, label: str) -> None:
    forbidden = _FORBIDDEN_EXECUTION_KEYS.intersection(payload)
    if forbidden:
        raise ValueError(f"{label} must not contain execution keys: {sorted(forbidden)!r}")


def _serialize_source_ref(ref: CanonicalSourceRef) -> dict[str, str]:
    return {str(key): str(value) for key, value in ref.refs.items()}


def _serialize_projected_source(source: ProjectedSource) -> dict[str, Any]:
    validate_projected_source_sentences(source, label="projected_source")
    payload = dict(source.payload)
    reject_legacy_projected_source_payload(payload, label="projected_source")
    serialized: dict[str, Any] = {
        "semantic_module_id": source.semantic_module_id,
        "representation_kind": source.representation_kind,
        "source_refs": [_serialize_source_ref(ref) for ref in source.source_refs],
        "sentences": [
            serialize_projected_sentence(sentence) for sentence in source.sentences
        ],
        "lineage": {str(key): str(value) for key, value in source.lineage.items()},
        "payload": payload,
    }
    _reject_forbidden_execution_keys(serialized, label="projected_source")
    return serialized


def _serialize_semantic_outcome(outcome: SemanticProjectionOutcome) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "semantic_module_id": outcome.semantic_module_id,
        "source_refs": [_serialize_source_ref(ref) for ref in outcome.source_refs],
        "strategy_result": dict(outcome.strategy_result),
    }
    _reject_forbidden_execution_keys(payload, label="semantic_outcome")
    return payload


def build_filter_output_projection_bundle_id(*, filter_job_id: str, run_id: str) -> str:
    return f"filter_output_projection_{filter_job_id}_{run_id}"


def build_filter_output_projection_bundle(
    *,
    step_result: FilterOutputProjectionStepResult,
    run_id: str,
) -> dict[str, Any]:
    """Build the persisted semantic-only projection artifact envelope."""

    bundle = {
        "artifact_type": FILTER_OUTPUT_PROJECTION_ARTIFACT_TYPE,
        "schema_version": FILTER_OUTPUT_PROJECTION_SCHEMA_VERSION,
        "filter_output_projection_bundle_id": build_filter_output_projection_bundle_id(
            filter_job_id=step_result.filter_job_id,
            run_id=run_id,
        ),
        "filter_job_id": step_result.filter_job_id,
        "doc_id": step_result.doc_id,
        "file_hash": validate_file_hash_format(
            step_result.file_hash,
            field="file_hash",
        ),
        "zone_key": step_result.zone_key,
        "projected_sources": [
            _serialize_projected_source(source)
            for source in step_result.projected_sources
        ],
        "semantic_outcomes": [
            _serialize_semantic_outcome(outcome)
            for outcome in step_result.semantic_outcomes
        ],
    }
    _reject_forbidden_execution_keys(bundle, label="filter_output_projection_bundle")
    validate_filter_output_projection_bundle(bundle)
    return bundle


def _deserialize_source_ref(raw: Mapping[str, Any]) -> CanonicalSourceRef:
    if not isinstance(raw, Mapping):
        raise ValueError("source_ref must be a mapping")
    refs = {str(key): str(value) for key, value in raw.items()}
    return CanonicalSourceRef(refs=refs)


def _deserialize_projected_source(
    raw: Mapping[str, Any],
    *,
    label: str = "projected_source",
) -> ProjectedSource:
    representation_kind = _require_str(
        raw.get("representation_kind"),
        field="representation_kind",
    )
    if representation_kind not in ALLOWED_PROJECTED_SOURCE_REPRESENTATION_KINDS:
        raise ValueError(
            "representation_kind must be one of: "
            + ", ".join(sorted(ALLOWED_PROJECTED_SOURCE_REPRESENTATION_KINDS))
        )
    source_refs_raw = raw.get("source_refs")
    if not isinstance(source_refs_raw, Sequence) or isinstance(
        source_refs_raw,
        (str, bytes),
    ):
        raise ValueError("source_refs must be a sequence")
    sentences_raw = raw.get("sentences")
    if not isinstance(sentences_raw, Sequence) or isinstance(sentences_raw, (str, bytes)):
        raise ValueError(f"{label}.sentences must be a sequence")
    lineage_raw = raw.get("lineage") or {}
    payload_raw = raw.get("payload") or {}
    if not isinstance(lineage_raw, Mapping):
        raise ValueError("lineage must be a mapping")
    if not isinstance(payload_raw, Mapping):
        raise ValueError("payload must be a mapping")
    reject_legacy_projected_source_payload(payload_raw, label=label)
    sentences = tuple(
        deserialize_projected_sentence(sentence, label=f"{label}.sentences[{index}]")
        for index, sentence in enumerate(sentences_raw)
        if isinstance(sentence, Mapping)
    )
    source = ProjectedSource(
        semantic_module_id=_require_str(
            raw.get("semantic_module_id"),
            field="semantic_module_id",
        ),
        representation_kind=representation_kind,
        source_refs=tuple(
            _deserialize_source_ref(ref)
            for ref in source_refs_raw
            if isinstance(ref, Mapping)
        ),
        sentences=sentences,
        lineage={str(key): str(value) for key, value in lineage_raw.items()},
        payload=dict(payload_raw),
    )
    validate_projected_source_sentences(source, label=label)
    return source


def _deserialize_semantic_outcome(raw: Mapping[str, Any]) -> SemanticProjectionOutcome:
    source_refs_raw = raw.get("source_refs")
    if not isinstance(source_refs_raw, Sequence) or isinstance(
        source_refs_raw,
        (str, bytes),
    ):
        raise ValueError("source_refs must be a sequence")
    strategy_result_raw = raw.get("strategy_result") or {}
    if not isinstance(strategy_result_raw, Mapping):
        raise ValueError("strategy_result must be a mapping")
    return SemanticProjectionOutcome(
        semantic_module_id=_require_str(
            raw.get("semantic_module_id"),
            field="semantic_module_id",
        ),
        source_refs=tuple(
            _deserialize_source_ref(ref)
            for ref in source_refs_raw
            if isinstance(ref, Mapping)
        ),
        strategy_result=dict(strategy_result_raw),
    )


def filter_output_projection_step_result_from_bundle(
    bundle: Mapping[str, Any],
) -> FilterOutputProjectionStepResult:
    """Rehydrate an in-memory projection Step result from a persisted bundle."""

    validate_filter_output_projection_bundle(bundle)
    projected_sources_raw = bundle["projected_sources"]
    semantic_outcomes_raw = bundle["semantic_outcomes"]
    return FilterOutputProjectionStepResult(
        filter_job_id=_require_str(bundle["filter_job_id"], field="filter_job_id"),
        doc_id=_require_str(bundle["doc_id"], field="doc_id"),
        file_hash=validate_file_hash_format(bundle["file_hash"], field="file_hash"),
        zone_key=_require_str(bundle["zone_key"], field="zone_key"),
        projected_sources=tuple(
            _deserialize_projected_source(
                source,
                label=f"projected_sources[{index}]",
            )
            for index, source in enumerate(projected_sources_raw)
            if isinstance(source, Mapping)
        ),
        semantic_outcomes=tuple(
            _deserialize_semantic_outcome(outcome)
            for outcome in semantic_outcomes_raw
            if isinstance(outcome, Mapping)
        ),
    )


def validate_filter_output_projection_bundle(payload: Mapping[str, Any]) -> None:
    """Validate a persisted filter_output_projection_bundle envelope."""

    if not isinstance(payload, Mapping):
        raise ValueError("filter_output_projection_bundle must be a mapping")

    _reject_forbidden_execution_keys(payload, label="filter_output_projection_bundle")

    extra = set(payload) - _ROOT_REQUIRED_KEYS - {
        "filter_output_projection_bundle_id",
    }
    if extra:
        raise ValueError(
            "filter_output_projection_bundle has unexpected keys: "
            f"{sorted(extra)!r}"
        )
    missing = _ROOT_REQUIRED_KEYS - set(payload)
    if missing:
        raise ValueError(
            "filter_output_projection_bundle is missing required keys: "
            f"{sorted(missing)!r}"
        )

    artifact_type = _require_str(payload["artifact_type"], field="artifact_type")
    if artifact_type != FILTER_OUTPUT_PROJECTION_ARTIFACT_TYPE:
        raise ValueError(
            "artifact_type must be "
            f"{FILTER_OUTPUT_PROJECTION_ARTIFACT_TYPE!r}, got {artifact_type!r}"
        )

    schema_version = _require_str(payload["schema_version"], field="schema_version")
    if schema_version != FILTER_OUTPUT_PROJECTION_SCHEMA_VERSION:
        raise ValueError(
            "schema_version must be "
            f"{FILTER_OUTPUT_PROJECTION_SCHEMA_VERSION!r}, got {schema_version!r}"
        )

    _require_str(payload["filter_job_id"], field="filter_job_id")
    _require_str(payload["doc_id"], field="doc_id")
    validate_file_hash_format(payload["file_hash"], field="file_hash")
    _require_str(payload["zone_key"], field="zone_key")

    projected_sources = payload["projected_sources"]
    semantic_outcomes = payload["semantic_outcomes"]
    if not isinstance(projected_sources, Sequence) or isinstance(
        projected_sources,
        (str, bytes),
    ):
        raise ValueError("projected_sources must be a sequence")
    if not isinstance(semantic_outcomes, Sequence) or isinstance(
        semantic_outcomes,
        (str, bytes),
    ):
        raise ValueError("semantic_outcomes must be a sequence")

    for index, source in enumerate(projected_sources):
        if not isinstance(source, Mapping):
            raise ValueError(f"projected_sources[{index}] must be a mapping")
        _deserialize_projected_source(source, label=f"projected_sources[{index}]")

    for index, outcome in enumerate(semantic_outcomes):
        if not isinstance(outcome, Mapping):
            raise ValueError(f"semantic_outcomes[{index}] must be a mapping")
        _deserialize_semantic_outcome(outcome)


__all__ = [
    "FILTER_OUTPUT_PROJECTION_ARTIFACT_TYPE",
    "FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME",
    "FILTER_OUTPUT_PROJECTION_SCHEMA_VERSION",
    "build_filter_output_projection_bundle",
    "build_filter_output_projection_bundle_id",
    "filter_output_projection_step_result_from_bundle",
    "validate_filter_output_projection_bundle",
]
