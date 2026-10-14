"""Canonical source annotation state artifact contract for Document Consistency QC."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from typing import Any

from core.document.sentence_index import is_canonical_source_sentence_id

SOURCE_ANNOTATION_STATE_FILENAME = "annotations.json"
SOURCE_ANNOTATION_OPERATION_DIRNAME = "source_annotations"
SOURCE_ANNOTATION_STATE_ARTIFACT_TYPE = "document_consistency_qc_source_annotation_state"
SOURCE_ANNOTATION_STATE_SCHEMA_VERSION = "0.6.0"
SOURCE_ANNOTATION_STATE_SCHEMA_VERSION_LEGACY = "0.1.0"
SUPPORTED_SOURCE_ANNOTATION_STATE_SCHEMA_VERSIONS = frozenset(
    {
        SOURCE_ANNOTATION_STATE_SCHEMA_VERSION,
        "0.5.0",
        "0.4.0",
        "0.3.0",
        "0.2.0",
        SOURCE_ANNOTATION_STATE_SCHEMA_VERSION_LEGACY,
    }
)
ANNOTATION_ID_PREFIX = "ann_"
SOURCE_ANNOTATION_KIND_COMMENT = "comment"
SOURCE_ANNOTATION_KIND_EDIT = "edit"
SOURCE_ANNOTATION_KIND_HIGHLIGHT = "highlight"
SOURCE_ANNOTATION_KINDS = frozenset(
    {
        SOURCE_ANNOTATION_KIND_COMMENT,
        SOURCE_ANNOTATION_KIND_EDIT,
        SOURCE_ANNOTATION_KIND_HIGHLIGHT,
    }
)

# Bare comparison aliases (H/U/T + 4 digits) — never valid sentence anchors.
_COMPARISON_ALIAS_RE = re.compile(r"^[HUT]\d{4}$")


def generate_annotation_id() -> str:
    """Return a new opaque source annotation identifier."""

    return f"{ANNOTATION_ID_PREFIX}{uuid.uuid4()}"


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _reject_bare_comparison_alias(token: str, *, field: str) -> None:
    if _COMPARISON_ALIAS_RE.fullmatch(token) is not None:
        raise ValueError(f"{field} must not be a bare comparison alias")


def validate_source_sentence_anchor(payload: Mapping[str, Any]) -> dict[str, str]:
    slot_id = _require_str(payload.get("slot_id"), field="slot_id")
    doc_id = _require_str(payload.get("doc_id"), field="doc_id")
    block_id = _require_str(payload.get("block_id"), field="block_id")
    sentence_id = _require_str(payload.get("sentence_id"), field="sentence_id")

    _reject_bare_comparison_alias(sentence_id, field="sentence_id")

    if not is_canonical_source_sentence_id(sentence_id):
        raise ValueError(
            "sentence_id must be a canonical Extract source sentence identity "
            "(<block_id>:Snnn)"
        )

    expected_prefix = f"{block_id}:"
    if not sentence_id.startswith(expected_prefix):
        raise ValueError(
            "sentence_id block prefix does not match anchor block_id"
        )

    return {
        "slot_id": slot_id,
        "doc_id": doc_id,
        "block_id": block_id,
        "sentence_id": sentence_id,
    }


def _require_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    return value


def validate_source_annotation_content(
    value: Any,
    *,
    required: bool = False,
) -> str | None:
    if value is None:
        if required:
            raise ValueError("content is required")
        return None
    if not isinstance(value, str):
        raise TypeError("content must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError("content must be non-empty after trimming whitespace")
    return stripped


def validate_source_annotation_replacement_text(
    value: Any,
    *,
    required: bool = False,
) -> str | None:
    if value is None:
        if required:
            raise ValueError("replacement_text is required")
        return None
    if not isinstance(value, str):
        raise TypeError("replacement_text must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(
            "replacement_text must be non-empty after trimming whitespace"
        )
    return stripped


def validate_source_annotation_kind(
    value: Any,
    *,
    required: bool = False,
) -> str | None:
    if value is None:
        if required:
            raise ValueError("kind is required")
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("kind is required")
    token = value.strip()
    if token not in SOURCE_ANNOTATION_KINDS:
        raise ValueError(f"kind must be one of {sorted(SOURCE_ANNOTATION_KINDS)!r}")
    return token


def validate_source_text_range(payload: Mapping[str, Any]) -> dict[str, int]:
    start_offset = _require_int(payload.get("start_offset"), field="start_offset")
    end_offset = _require_int(payload.get("end_offset"), field="end_offset")

    if start_offset < 0:
        raise ValueError("start_offset must be >= 0")
    if end_offset <= start_offset:
        raise ValueError("end_offset must be greater than start_offset")

    return {
        "start_offset": start_offset,
        "end_offset": end_offset,
    }


def validate_source_annotation_entry(
    payload: Mapping[str, Any],
    *,
    annotation_id: str,
) -> dict[str, Any]:
    entry_annotation_id = _require_str(
        payload.get("annotation_id"),
        field="annotation_id",
    )
    if entry_annotation_id != annotation_id:
        raise ValueError("annotation_id must match annotations map key")

    if not entry_annotation_id.startswith(ANNOTATION_ID_PREFIX):
        raise ValueError("annotation_id must be an opaque ann_<uuid> identifier")

    anchor_raw = payload.get("anchor")
    if not isinstance(anchor_raw, Mapping):
        raise TypeError("anchor must be an object")

    created_at = _require_str(payload.get("created_at"), field="created_at")
    updated_at = _require_str(payload.get("updated_at"), field="updated_at")

    kind = validate_source_annotation_kind(payload.get("kind"))
    range_raw = payload.get("range")
    content_raw = payload.get("content")
    replacement_text_raw = payload.get("replacement_text")

    if kind == SOURCE_ANNOTATION_KIND_HIGHLIGHT:
        if content_raw is not None:
            raise ValueError("content must be absent when kind is highlight")
        if replacement_text_raw is not None:
            raise ValueError("replacement_text must be absent when kind is highlight")
        if range_raw is None:
            raise ValueError("range is required when kind is highlight")
        if not isinstance(range_raw, Mapping):
            raise TypeError("range must be an object when present")
        validated_range = validate_source_text_range(range_raw)
        return {
            "annotation_id": entry_annotation_id,
            "anchor": validate_source_sentence_anchor(anchor_raw),
            "kind": kind,
            "range": validated_range,
            "created_at": created_at,
            "updated_at": updated_at,
        }

    if kind == SOURCE_ANNOTATION_KIND_COMMENT:
        validated_content = validate_source_annotation_content(content_raw, required=True)
        if replacement_text_raw is not None:
            raise ValueError("replacement_text must be absent when kind is comment")
        entry: dict[str, Any] = {
            "annotation_id": entry_annotation_id,
            "anchor": validate_source_sentence_anchor(anchor_raw),
            "kind": kind,
            "content": validated_content,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        if range_raw is not None:
            if not isinstance(range_raw, Mapping):
                raise TypeError("range must be an object when present")
            entry["range"] = validate_source_text_range(range_raw)
        return entry

    if kind == SOURCE_ANNOTATION_KIND_EDIT:
        if content_raw is not None:
            raise ValueError("content must be absent when kind is edit")
        if range_raw is None:
            raise ValueError("range is required when kind is edit")
        if not isinstance(range_raw, Mapping):
            raise TypeError("range must be an object when present")
        validated_range = validate_source_text_range(range_raw)
        validated_replacement_text = validate_source_annotation_replacement_text(
            replacement_text_raw,
            required=True,
        )
        return {
            "annotation_id": entry_annotation_id,
            "anchor": validate_source_sentence_anchor(anchor_raw),
            "kind": kind,
            "range": validated_range,
            "replacement_text": validated_replacement_text,
            "created_at": created_at,
            "updated_at": updated_at,
        }

    if content_raw is not None:
        raise ValueError("content is only allowed when kind is comment")
    if replacement_text_raw is not None:
        raise ValueError("replacement_text is only allowed when kind is edit")

    entry: dict[str, Any] = {
        "annotation_id": entry_annotation_id,
        "anchor": validate_source_sentence_anchor(anchor_raw),
        "created_at": created_at,
        "updated_at": updated_at,
    }
    if kind is not None:
        entry["kind"] = kind

    if range_raw is None:
        return entry
    if not isinstance(range_raw, Mapping):
        raise TypeError("range must be an object when present")
    entry["range"] = validate_source_text_range(range_raw)
    return entry


def validate_source_annotation_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("artifact_type") != SOURCE_ANNOTATION_STATE_ARTIFACT_TYPE:
        raise ValueError("source_annotation_state.artifact_type mismatch")

    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_SOURCE_ANNOTATION_STATE_SCHEMA_VERSIONS:
        raise ValueError("source_annotation_state.schema_version mismatch")

    flow_run_id = _require_str(payload.get("flow_run_id"), field="flow_run_id")
    raw_annotations = payload.get("annotations")
    if not isinstance(raw_annotations, Mapping):
        raise TypeError("annotations must be an object")

    normalized_annotations: dict[str, dict[str, Any]] = {}
    for annotation_id, entry in raw_annotations.items():
        if not isinstance(annotation_id, str) or not annotation_id.strip():
            raise ValueError("annotations key must be a non-empty annotation_id")
        if not isinstance(entry, Mapping):
            raise TypeError(f"annotations[{annotation_id!r}] must be an object")
        normalized_annotations[annotation_id] = validate_source_annotation_entry(
            entry,
            annotation_id=annotation_id,
        )

    return {
        "artifact_type": SOURCE_ANNOTATION_STATE_ARTIFACT_TYPE,
        "schema_version": schema_version,
        "flow_run_id": flow_run_id,
        "annotations": normalized_annotations,
    }


def build_source_annotation_state_payload(
    *,
    flow_run_id: str,
    annotations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_annotations = {
        annotation_id: validate_source_annotation_entry(entry, annotation_id=annotation_id)
        for annotation_id, entry in annotations.items()
    }
    return validate_source_annotation_state(
        {
            "artifact_type": SOURCE_ANNOTATION_STATE_ARTIFACT_TYPE,
            "schema_version": SOURCE_ANNOTATION_STATE_SCHEMA_VERSION,
            "flow_run_id": flow_run_id,
            "annotations": normalized_annotations,
        }
    )


__all__ = [
    "ANNOTATION_ID_PREFIX",
    "SOURCE_ANNOTATION_KINDS",
    "SOURCE_ANNOTATION_KIND_COMMENT",
    "SOURCE_ANNOTATION_KIND_EDIT",
    "SOURCE_ANNOTATION_KIND_HIGHLIGHT",
    "SOURCE_ANNOTATION_OPERATION_DIRNAME",
    "SOURCE_ANNOTATION_STATE_ARTIFACT_TYPE",
    "SOURCE_ANNOTATION_STATE_FILENAME",
    "SOURCE_ANNOTATION_STATE_SCHEMA_VERSION",
    "SOURCE_ANNOTATION_STATE_SCHEMA_VERSION_LEGACY",
    "SUPPORTED_SOURCE_ANNOTATION_STATE_SCHEMA_VERSIONS",
    "build_source_annotation_state_payload",
    "generate_annotation_id",
    "validate_source_annotation_content",
    "validate_source_annotation_entry",
    "validate_source_annotation_kind",
    "validate_source_annotation_replacement_text",
    "validate_source_annotation_state",
    "validate_source_sentence_anchor",
    "validate_source_text_range",
]
