"""Formal request_file_intake_result artifact contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.document.doc_identity import validate_file_hash_format

REQUEST_FILE_INTAKE_RESULT_FILENAME = "request_file_intake_result.json"
REQUEST_FILE_INTAKE_RESULT_ARTIFACT_TYPE = "request_file_intake_result"
REQUEST_FILE_INTAKE_RESULT_SCHEMA_VERSION = "0.2.0"

_ROOT_KEYS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "document",
    }
)
_DOCUMENT_KEYS = frozenset({"file_hash", "original_file_name"})
_FORBIDDEN_DOCUMENT_KEYS = frozenset(
    {
        "doc_id",
        "source_path",
        "upload_id",
        "request_document_ref",
        "document_type",
        "zone_key",
        "comparison_profile",
    }
)


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _validate_document_record(document: Any) -> dict[str, str]:
    label = "document"
    if not isinstance(document, dict):
        raise ValueError(f"{label} must be an object")
    extra = set(document) - _DOCUMENT_KEYS
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")
    missing = _DOCUMENT_KEYS - set(document)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")
    for forbidden in _FORBIDDEN_DOCUMENT_KEYS:
        if forbidden in document:
            raise ValueError(f"{label} must not include {forbidden!r}")
    return {
        "file_hash": validate_file_hash_format(
            document["file_hash"],
            field=f"{label}.file_hash",
        ),
        "original_file_name": _require_str(
            document["original_file_name"],
            field=f"{label}.original_file_name",
        ),
    }


def validate_request_file_intake_result(payload: Mapping[str, Any]) -> None:
    """Validate a formal request_file_intake_result artifact envelope."""
    if not isinstance(payload, Mapping):
        raise ValueError("request_file_intake_result must be a mapping")

    extra_root = set(payload) - _ROOT_KEYS
    if extra_root:
        raise ValueError(
            "request_file_intake_result has unexpected root keys: "
            f"{sorted(extra_root)!r}"
        )
    missing_root = _ROOT_KEYS - set(payload)
    if missing_root:
        raise ValueError(
            "request_file_intake_result is missing required root keys: "
            f"{sorted(missing_root)!r}"
        )

    artifact_type = _require_str(payload["artifact_type"], field="artifact_type")
    if artifact_type != REQUEST_FILE_INTAKE_RESULT_ARTIFACT_TYPE:
        raise ValueError(
            "artifact_type must be "
            f"{REQUEST_FILE_INTAKE_RESULT_ARTIFACT_TYPE!r}, got {artifact_type!r}"
        )

    schema_version = _require_str(payload["schema_version"], field="schema_version")
    if schema_version != REQUEST_FILE_INTAKE_RESULT_SCHEMA_VERSION:
        raise ValueError(
            "schema_version must be "
            f"{REQUEST_FILE_INTAKE_RESULT_SCHEMA_VERSION!r}, got {schema_version!r}"
        )

    _validate_document_record(payload["document"])


def build_request_file_intake_result(
    *,
    file_hash: str,
    original_file_name: str,
) -> dict[str, Any]:
    """Build and validate a request_file_intake_result artifact envelope."""
    document = {
        "file_hash": validate_file_hash_format(
            file_hash,
            field="document.file_hash",
        ),
        "original_file_name": _require_str(
            original_file_name,
            field="document.original_file_name",
        ),
    }

    envelope: dict[str, Any] = {
        "artifact_type": REQUEST_FILE_INTAKE_RESULT_ARTIFACT_TYPE,
        "schema_version": REQUEST_FILE_INTAKE_RESULT_SCHEMA_VERSION,
        "document": document,
    }
    validate_request_file_intake_result(envelope)
    return envelope
