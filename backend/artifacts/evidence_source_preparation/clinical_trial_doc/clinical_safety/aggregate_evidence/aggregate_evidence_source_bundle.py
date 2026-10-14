# ruff: noqa: TRY004
"""Formal aggregate evidence source bundle contract (declared ESP downstream output)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from core.serialization import stable_json_dumps

AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME = "aggregate_evidence_source_bundle.json"
AGGREGATE_EVIDENCE_SOURCE_BUNDLE_ARTIFACT_TYPE = "aggregate_evidence_source_bundle"
AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION = "0.3.0"

ALLOWED_DOCUMENT_TYPES = frozenset({"ib", "csr", "dsur"})

_ROOT_KEYS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "aggregate_evidence_source_bundle_id",
        "doc_id",
        "file_hash",
        "document_context",
        "heading_scopes",
    }
)
_DOCUMENT_CONTEXT_KEYS = frozenset({"document_type"})
_SCOPE_KEYS = frozenset({"scope_id", "scope_order", "heading_path", "units"})
_UNIT_KEYS = frozenset({"unit_id", "unit_order", "text", "source", "sentences"})
_UNIT_SOURCE_KEYS = frozenset({"block_ids"})
_SENTENCE_KEYS = frozenset(
    {"sentence_id", "sentence_order", "text", "source_block_ids"}
)


def build_aggregate_evidence_source_bundle_id(
    *,
    file_hash: str,
    document_type: str,
    heading_scopes: Sequence[Mapping[str, Any]],
) -> str:
    """Hash retained canonical content; exclude source-instance/runtime identity."""
    fingerprint_payload = {
        "artifact_type": AGGREGATE_EVIDENCE_SOURCE_BUNDLE_ARTIFACT_TYPE,
        "schema_version": AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION,
        "file_hash": _require_str(file_hash, field="file_hash"),
        "document_context": {
            "document_type": _validate_document_type(document_type),
        },
        "heading_scopes": [dict(scope) for scope in heading_scopes],
    }
    digest = hashlib.sha256(
        stable_json_dumps(fingerprint_payload).encode("utf-8")
    ).hexdigest()
    return f"aggregate_evidence_source_bundle_{digest}"


def build_aggregate_evidence_source_bundle(
    *,
    doc_id: str,
    file_hash: str,
    document_type: str,
    heading_scopes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate the formal evidence/provenance envelope."""
    canonical_scopes = [dict(scope) for scope in heading_scopes]
    canonical_file_hash = _require_str(file_hash, field="file_hash")
    canonical_document_type = _validate_document_type(document_type)
    envelope: dict[str, Any] = {
        "artifact_type": AGGREGATE_EVIDENCE_SOURCE_BUNDLE_ARTIFACT_TYPE,
        "schema_version": AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION,
        "aggregate_evidence_source_bundle_id": build_aggregate_evidence_source_bundle_id(
            file_hash=canonical_file_hash,
            document_type=canonical_document_type,
            heading_scopes=canonical_scopes,
        ),
        "doc_id": _require_str(doc_id, field="doc_id"),
        "file_hash": canonical_file_hash,
        "document_context": {"document_type": canonical_document_type},
        "heading_scopes": canonical_scopes,
    }
    validate_aggregate_evidence_source_bundle(envelope)
    return envelope


def validate_aggregate_evidence_source_bundle(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise ValueError("aggregate_evidence_source_bundle must be an object")
    _require_exact_keys(payload, expected=_ROOT_KEYS, path="root")

    if payload.get("artifact_type") != AGGREGATE_EVIDENCE_SOURCE_BUNDLE_ARTIFACT_TYPE:
        raise ValueError(
            "artifact_type must be "
            f"{AGGREGATE_EVIDENCE_SOURCE_BUNDLE_ARTIFACT_TYPE!r}"
        )
    if payload.get("schema_version") != AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION:
        raise ValueError(
            "schema_version must be "
            f"{AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION!r}"
        )

    bundle_id = _require_str(
        payload.get("aggregate_evidence_source_bundle_id"),
        field="aggregate_evidence_source_bundle_id",
    )
    doc_id = _require_str(payload.get("doc_id"), field="doc_id")
    file_hash = _require_str(payload.get("file_hash"), field="file_hash")

    document_context = payload.get("document_context")
    if not isinstance(document_context, Mapping):
        raise ValueError("document_context must be an object")
    _require_exact_keys(
        document_context,
        expected=_DOCUMENT_CONTEXT_KEYS,
        path="document_context",
    )
    document_type = _validate_document_type(document_context.get("document_type"))

    heading_scopes = payload.get("heading_scopes")
    if not isinstance(heading_scopes, list):
        raise ValueError("heading_scopes must be a list")

    seen_scope_ids: set[str] = set()
    previous_scope_order: int | None = None
    for scope_index, scope in enumerate(heading_scopes):
        if not isinstance(scope, Mapping):
            raise ValueError(f"heading_scopes[{scope_index}] must be an object")
        previous_scope_order = _validate_scope(
            scope,
            scope_index=scope_index,
            seen_scope_ids=seen_scope_ids,
            previous_scope_order=previous_scope_order,
        )

    expected_id = build_aggregate_evidence_source_bundle_id(
        file_hash=file_hash,
        document_type=document_type,
        heading_scopes=heading_scopes,
    )
    if bundle_id != expected_id:
        raise ValueError(
            "aggregate_evidence_source_bundle_id does not match canonical content "
            f"for doc_id {doc_id!r}"
        )


def _validate_scope(
    scope: Mapping[str, Any],
    *,
    scope_index: int,
    seen_scope_ids: set[str],
    previous_scope_order: int | None,
) -> int:
    path = f"heading_scopes[{scope_index}]"
    _require_exact_keys(scope, expected=_SCOPE_KEYS, path=path)
    scope_id = _require_str(scope.get("scope_id"), field=f"{path}.scope_id")
    if scope_id in seen_scope_ids:
        raise ValueError(f"duplicate scope_id {scope_id!r}")
    seen_scope_ids.add(scope_id)

    scope_order = scope.get("scope_order")
    if not isinstance(scope_order, int) or isinstance(scope_order, bool) or scope_order < 0:
        raise ValueError(f"scope {scope_id!r} scope_order must be a non-negative integer")
    if previous_scope_order is not None and scope_order <= previous_scope_order:
        raise ValueError(
            f"scope {scope_id!r} scope_order must be strictly increasing across heading_scopes"
        )

    heading_path = scope.get("heading_path")
    if not isinstance(heading_path, list) or not all(
        isinstance(item, str) for item in heading_path
    ):
        raise ValueError(f"scope {scope_id!r} heading_path must be a string list")

    units = scope.get("units")
    if not isinstance(units, list) or not units:
        raise ValueError(f"scope {scope_id!r} units must be a non-empty list")
    seen_unit_ids: set[str] = set()
    for unit_index, unit in enumerate(units):
        if not isinstance(unit, Mapping):
            raise ValueError(f"scope {scope_id!r} units[{unit_index}] must be an object")
        _validate_unit(
            unit,
            scope_id=scope_id,
            unit_index=unit_index,
            seen_unit_ids=seen_unit_ids,
        )
    return scope_order


def _validate_unit(
    unit: Mapping[str, Any],
    *,
    scope_id: str,
    unit_index: int,
    seen_unit_ids: set[str],
) -> None:
    path = f"scope {scope_id!r} units[{unit_index}]"
    _require_exact_keys(unit, expected=_UNIT_KEYS, path=path)
    unit_id = _require_str(unit.get("unit_id"), field=f"{path}.unit_id")
    if unit_id in seen_unit_ids:
        raise ValueError(f"duplicate unit_id {unit_id!r} in scope {scope_id!r}")
    seen_unit_ids.add(unit_id)
    if unit.get("unit_order") != unit_index:
        raise ValueError(
            f"scope {scope_id!r} unit {unit_id!r} unit_order must be {unit_index}, "
            f"got {unit.get('unit_order')!r}"
        )
    text = unit.get("text")
    if not isinstance(text, str) or not text:
        raise ValueError(f"scope {scope_id!r} unit {unit_id!r} text must be non-empty")

    source = unit.get("source")
    if not isinstance(source, Mapping):
        raise ValueError(f"scope {scope_id!r} unit {unit_id!r} source must be an object")
    _require_exact_keys(source, expected=_UNIT_SOURCE_KEYS, path=f"{path}.source")
    _require_non_empty_string_list(
        source.get("block_ids"),
        field=f"scope {scope_id!r} unit {unit_id!r} source.block_ids",
    )

    sentences = unit.get("sentences")
    if not isinstance(sentences, list) or not sentences:
        raise ValueError(f"scope {scope_id!r} unit {unit_id!r} sentences must be non-empty")
    seen_sentence_ids: set[str] = set()
    for sentence_index, sentence in enumerate(sentences):
        if not isinstance(sentence, Mapping):
            raise ValueError(
                f"scope {scope_id!r} unit {unit_id!r} sentences[{sentence_index}] "
                "must be an object"
            )
        _validate_sentence(
            sentence,
            scope_id=scope_id,
            unit_id=unit_id,
            sentence_index=sentence_index,
            seen_sentence_ids=seen_sentence_ids,
        )


def _validate_sentence(
    sentence: Mapping[str, Any],
    *,
    scope_id: str,
    unit_id: str,
    sentence_index: int,
    seen_sentence_ids: set[str],
) -> None:
    path = f"scope {scope_id!r} unit {unit_id!r} sentences[{sentence_index}]"
    _require_exact_keys(sentence, expected=_SENTENCE_KEYS, path=path)
    sentence_id = _require_str(sentence.get("sentence_id"), field=f"{path}.sentence_id")
    if sentence_id in seen_sentence_ids:
        raise ValueError(f"duplicate sentence_id {sentence_id!r} within unit {unit_id!r}")
    seen_sentence_ids.add(sentence_id)
    if sentence.get("sentence_order") != sentence_index:
        raise ValueError(
            f"scope {scope_id!r} unit {unit_id!r} sentence {sentence_id!r} "
            f"sentence_order must be {sentence_index}"
        )
    if not isinstance(sentence.get("text"), str):
        raise ValueError(f"{path}.text must be a string")
    _require_non_empty_string_list(
        sentence.get("source_block_ids"),
        field=f"{path}.source_block_ids",
    )


def _validate_document_type(value: Any) -> str:
    document_type = _require_str(value, field="document_context.document_type")
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError(
            "document_context.document_type must be one of "
            f"{sorted(ALLOWED_DOCUMENT_TYPES)!r}, got {document_type!r}"
        )
    return document_type


def _require_exact_keys(
    value: Mapping[str, Any],
    *,
    expected: frozenset[str],
    path: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{path} keys mismatch; missing={missing!r}, unknown={unknown!r}")


def _require_non_empty_string_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty string list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must contain only non-empty strings")
    return value


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()
