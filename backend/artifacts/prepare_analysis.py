"""Formal contracts for Prepare Analysis artifacts.

This module owns representation-level names, versions, packaging, and validation.
It intentionally does not perform privacy, masking, date-shift, or heading semantics.
"""
# ruff: noqa: TRY004 -- schema validators consistently report contract violations as values.

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ANALYSIS_BUNDLE_FILENAME = "analysis_bundle.json"
PRIVACY_AUDIT_FILENAME = "privacy_audit.json"
RUN_SUMMARY_FILENAME = "run_summary.json"
FAILURE_FILENAME = "failure.json"

ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC = "0.4.0"
ANALYSIS_BUNDLE_SCHEMA_VERSION_IDENTITY = "0.3.0"
ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED = "public_masked_v0.4"
ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW = "local_raw_v0.3"

BLOCK_GROUPS: tuple[str, ...] = (
    "front_matter_blocks",
    "content_blocks",
    "table_blocks",
    "format_blocks",
)

_EXTRACT_NORMALIZED_TEXT_REQUIRED_VERSION = (0, 1, 9)
_EXTRACT_CANONICAL_SENTENCE_PAYLOAD_VERSION = (0, 2, 0)

_LOCAL_RAW_FORBIDDEN_SENTENCE_KEYS = frozenset(
    {"start", "end", "span_map", "text", "raw_text"}
)


def requires_canonical_sentence_normalized_text(bundle: Mapping[str, Any]) -> bool:
    """Return True when Extract sentences must carry canonical ``normalized_text``."""

    meta = bundle.get("document_meta")
    if not isinstance(meta, Mapping):
        return False
    version = _numeric_schema_version(meta.get("bundle_schema_version"))
    return (
        version is not None
        and version >= _EXTRACT_CANONICAL_SENTENCE_PAYLOAD_VERSION
    )


def resolve_prepare_sentence_normalized_text(
    sentence: Mapping[str, Any],
    *,
    sentence_path: str,
    canonical_sentence_payload_required: bool,
) -> str:
    """Resolve canonical Prepare sentence ``normalized_text`` (no coordinates)."""

    if canonical_sentence_payload_required:
        if "normalized_text" not in sentence:
            raise ValueError(f"{sentence_path}.normalized_text is required")
        sent_norm = sentence["normalized_text"]
        if not isinstance(sent_norm, str):
            raise ValueError(f"{sentence_path}.normalized_text must be a string")
        return sent_norm

    if "normalized_text" in sentence:
        value = sentence["normalized_text"]
        if not isinstance(value, str):
            raise ValueError(f"{sentence_path}.normalized_text must be a string")
        return value
    if "text" in sentence:
        value = sentence["text"]
        if not isinstance(value, str):
            raise ValueError(f"{sentence_path}.text must be a string")
        return value
    raise ValueError(f"{sentence_path}.normalized_text is required")


@dataclass(frozen=True)
class PrepareAnalysisArtifactPaths:
    analysis_bundle: Path
    block_manifest: Path
    run_summary: Path
    privacy_audit: Path | None = None
    mapping: Path | None = None
    private_audit_bundle: Path | None = None


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _numeric_schema_version(value: Any) -> tuple[int, int, int] | None:
    """Parse the repository's current three-part numeric bundle versions."""
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1]), int(parts[2])


def _requires_extract_normalized_text(bundle: Mapping[str, Any]) -> bool:
    meta = bundle.get("document_meta")
    if not isinstance(meta, Mapping):
        return False
    version = _numeric_schema_version(meta.get("bundle_schema_version"))
    return (
        version is not None
        and version >= _EXTRACT_NORMALIZED_TEXT_REQUIRED_VERSION
    )


def _validate_sentence_records(
    sentences: Any,
    *,
    block_path: str,
    seen_sentence_ids: set[str],
    canonical_sentence_payload_required: bool,
) -> None:
    if not isinstance(sentences, list):
        raise ValueError(f"{block_path}.sentences must be a list")
    for index, sentence in enumerate(sentences):
        path = f"{block_path}.sentences[{index}]"
        if not isinstance(sentence, Mapping):
            raise ValueError(f"{path} must be an object")
        sentence_id = _require_non_empty_str(
            sentence.get("sentence_id"), field=f"{path}.sentence_id"
        )
        if sentence_id in seen_sentence_ids:
            raise ValueError(f"duplicate sentence_id {sentence_id!r}")
        seen_sentence_ids.add(sentence_id)
        resolve_prepare_sentence_normalized_text(
            sentence,
            sentence_path=path,
            canonical_sentence_payload_required=canonical_sentence_payload_required,
        )


def _validate_local_raw_sentence_shape(sentence: Mapping[str, Any], *, path: str) -> None:
    for forbidden in _LOCAL_RAW_FORBIDDEN_SENTENCE_KEYS:
        if forbidden in sentence:
            raise ValueError(f"{path} must not include {forbidden!r}")
    if not isinstance(sentence.get("normalized_text"), str):
        raise ValueError(f"{path}.normalized_text must be a string")


def validate_prepare_analysis_input(bundle: Mapping[str, Any]) -> None:
    """Validate only the Extract-derived invariants Prepare Analysis consumes."""

    if not isinstance(bundle, Mapping):
        raise TypeError("prepare_analysis input must be a mapping")
    _require_non_empty_str(bundle.get("doc_id"), field="bundle.doc_id")
    normalized_text_required = _requires_extract_normalized_text(bundle)
    canonical_sentence_payload_required = requires_canonical_sentence_normalized_text(
        bundle
    )

    seen_block_ids: set[str] = set()
    seen_sentence_ids: set[str] = set()
    for group in BLOCK_GROUPS:
        blocks = bundle.get(group)
        if not isinstance(blocks, list):
            raise ValueError(f"bundle.{group} must be a list")
        previous_order: int | None = None
        for index, block in enumerate(blocks):
            path = f"bundle.{group}[{index}]"
            if not isinstance(block, Mapping):
                raise ValueError(f"{path} must be an object")
            block_id = _require_non_empty_str(
                block.get("block_id"), field=f"{path}.block_id"
            )
            if block_id in seen_block_ids:
                raise ValueError(f"duplicate block_id {block_id!r}")
            seen_block_ids.add(block_id)
            _require_non_empty_str(block.get("kind"), field=f"{path}.kind")

            if normalized_text_required:
                normalized = block.get("normalized_text")
                normalized_error = f"{path}.normalized_text must be a string"
            elif "normalized_text" in block:
                normalized = block["normalized_text"]
                normalized_error = f"{path}.normalized_text must be a string"
            else:
                normalized = block.get("text")
                normalized_error = (
                    f"{path}.normalized_text (or legacy text) must be a string"
                )
            if not isinstance(normalized, str):
                raise ValueError(normalized_error)

            order = block.get("order")
            if order is not None:
                if not isinstance(order, int) or order < 0:
                    raise ValueError(f"{path}.order must be a non-negative integer")
                if previous_order is not None and order < previous_order:
                    raise ValueError(f"bundle.{group} order must be monotonic")
                previous_order = order
            doc_order = block.get("doc_order_index")
            if doc_order is not None and (
                not isinstance(doc_order, int) or doc_order < 0
            ):
                raise ValueError(
                    f"{path}.doc_order_index must be a non-negative integer"
                )

            source_ref = block.get("source_ref")
            if source_ref is not None:
                if not isinstance(source_ref, Mapping):
                    raise ValueError(f"{path}.source_ref must be an object")
                _require_non_empty_str(
                    source_ref.get("source_type"),
                    field=f"{path}.source_ref.source_type",
                )
                _require_non_empty_str(
                    source_ref.get("locator_type"),
                    field=f"{path}.source_ref.locator_type",
                )
                if not isinstance(source_ref.get("locator_payload"), Mapping):
                    raise ValueError(
                        f"{path}.source_ref.locator_payload must be an object"
                    )

            sentences = block.get("sentences")
            if sentences is not None:
                _validate_sentence_records(
                    sentences,
                    block_path=path,
                    seen_sentence_ids=seen_sentence_ids,
                    canonical_sentence_payload_required=(
                        canonical_sentence_payload_required
                    ),
                )


def validate_analysis_bundle(payload: Mapping[str, Any]) -> None:
    """Validate the complete persisted Prepare Analysis analysis-bundle contract."""

    if not isinstance(payload, Mapping):
        raise TypeError("analysis_bundle must be a mapping")
    analysis_bundle_id = payload.get("analysis_bundle_id")
    if analysis_bundle_id is not None:
        _require_non_empty_str(analysis_bundle_id, field="analysis_bundle_id")
    _require_non_empty_str(payload.get("doc_id"), field="doc_id")
    file_hash = payload.get("file_hash")
    if file_hash is not None:
        _require_non_empty_str(file_hash, field="file_hash")
    if payload.get("stage") != "prepare_analysis":
        raise ValueError("analysis_bundle.stage must be 'prepare_analysis'")
    if payload.get("pipeline") != ["extract", "prepare_analysis"]:
        raise ValueError(
            "analysis_bundle.pipeline must be ['extract', 'prepare_analysis']"
        )

    contract = payload.get("analysis_bundle_contract")
    version = payload.get("analysis_bundle_schema_version")
    expected = {
        ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW: ANALYSIS_BUNDLE_SCHEMA_VERSION_IDENTITY,
        ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED: ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
    }
    if contract not in expected:
        raise ValueError(f"unsupported analysis_bundle_contract: {contract!r}")
    if version != expected[contract]:
        raise ValueError(
            f"analysis_bundle_schema_version mismatch for {contract!r}: {version!r}"
        )
    if not isinstance(payload.get("privacy_enabled"), bool):
        raise ValueError("analysis_bundle.privacy_enabled must be bool")
    transforms = payload.get("privacy_transforms")
    if not isinstance(transforms, Mapping) or "after_extract" not in transforms:
        raise ValueError("analysis_bundle.privacy_transforms.after_extract is required")

    seen_ids: set[str] = set()
    seen_sentence_ids: set[str] = set()
    for group in BLOCK_GROUPS:
        blocks = payload.get(group)
        if not isinstance(blocks, list):
            raise ValueError(f"analysis_bundle.{group} must be a list")
        for index, block in enumerate(blocks):
            path = f"analysis_bundle.{group}[{index}]"
            if not isinstance(block, Mapping):
                raise ValueError(f"{path} must be an object")
            block_id = _require_non_empty_str(
                block.get("block_id"), field=f"{path}.block_id"
            )
            if block_id in seen_ids:
                raise ValueError(f"duplicate analysis block_id {block_id!r}")
            seen_ids.add(block_id)
            if not isinstance(block.get("analysis_text"), str):
                raise ValueError(f"{path}.analysis_text must be a string")
            if contract == ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW:
                if not isinstance(block.get("normalized_text"), str):
                    raise ValueError(f"{path}.normalized_text must be a string")
                if "span_map" in block:
                    raise ValueError(f"{path} must not include 'span_map'")
            sentences = block.get("sentences")
            if sentences is not None:
                if not isinstance(sentences, list):
                    raise ValueError(f"{path}.sentences must be a list")
                for sentence_index, sentence in enumerate(sentences):
                    sentence_path = f"{path}.sentences[{sentence_index}]"
                    if not isinstance(sentence, Mapping):
                        raise ValueError(f"{sentence_path} must be an object")
                    sentence_id = _require_non_empty_str(
                        sentence.get("sentence_id"),
                        field=f"{sentence_path}.sentence_id",
                    )
                    if sentence_id in seen_sentence_ids:
                        raise ValueError(
                            f"duplicate analysis sentence_id {sentence_id!r}"
                        )
                    seen_sentence_ids.add(sentence_id)
                    if not isinstance(sentence.get("analysis_text"), str):
                        raise ValueError(
                            f"{sentence_path}.analysis_text must be a string"
                        )
                    if contract == ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED:
                        for forbidden in ("start", "end", "normalized_text", "span_map"):
                            if forbidden in sentence:
                                raise ValueError(
                                    f"{sentence_path} must not include {forbidden!r} "
                                    "on public masked sentences"
                                )
                        continue
                    _validate_local_raw_sentence_shape(
                        sentence,
                        path=sentence_path,
                    )


def build_analysis_bundle_artifact(
    semantic_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Package and validate already-produced Prepare Analysis semantic values."""

    artifact = deepcopy(dict(semantic_payload))
    validate_analysis_bundle(artifact)
    return artifact


def validate_prepare_analysis_result(result: Any) -> None:
    """Validate the complete formal in-memory result returned by the Step."""

    analysis_bundle = getattr(result, "analysis_bundle", None)
    validate_analysis_bundle(analysis_bundle)
    doc_id = _require_non_empty_str(
        getattr(result, "doc_id", None), field="result.doc_id"
    )
    if analysis_bundle.get("doc_id") != doc_id:
        raise ValueError("result.doc_id must match analysis_bundle.doc_id")

    mask_result = getattr(result, "mask_result", None)
    audit_surfaces = getattr(result, "block_audit_surfaces", None)
    if not isinstance(audit_surfaces, list) or not all(
        isinstance(item, Mapping) for item in audit_surfaces
    ):
        raise ValueError("result.block_audit_surfaces must be a list of objects")

    if mask_result is None:
        if audit_surfaces:
            raise ValueError(
                "result.block_audit_surfaces must be empty when mask_result is absent"
            )
    else:
        if getattr(mask_result, "doc_id", None) != doc_id:
            raise ValueError("result.mask_result.doc_id must match result.doc_id")
        if not isinstance(getattr(mask_result, "masked_blocks", None), list):
            raise ValueError("result.mask_result.masked_blocks must be a list")
        masked_ids = [
            _require_non_empty_str(
                getattr(block, "block_id", None),
                field="result.mask_result.masked_blocks.block_id",
            )
            for block in mask_result.masked_blocks
        ]
        if len(masked_ids) != len(set(masked_ids)):
            raise ValueError(
                "result.mask_result.masked_blocks contains duplicate block_id"
            )
        if set(masked_ids) != {
            str(block["block_id"])
            for group in BLOCK_GROUPS
            for block in analysis_bundle[group]
        }:
            raise ValueError(
                "result.mask_result.masked_blocks must cover every analysis block"
            )
        if not isinstance(getattr(mask_result, "mapping", None), Mapping):
            raise ValueError("result.mask_result.mapping must be an object")
        if not isinstance(getattr(mask_result, "date_shift", None), Mapping):
            raise ValueError("result.mask_result.date_shift must be an object")
        if not isinstance(getattr(mask_result, "detectors", None), list):
            raise ValueError("result.mask_result.detectors must be a list")

    projection = getattr(result, "heading_projection", None)
    content_projection = getattr(projection, "content", None)
    table_projection = getattr(projection, "tables", None)
    if not isinstance(content_projection, Mapping) or not isinstance(
        table_projection, Mapping
    ):
        raise ValueError(
            "result.heading_projection must contain content/table mappings"
        )
    expected_content = {
        str(block["block_id"]) for block in analysis_bundle["content_blocks"]
    }
    expected_tables = {
        str(block["block_id"]) for block in analysis_bundle["table_blocks"]
    }
    if (
        set(content_projection) != expected_content
        or set(table_projection) != expected_tables
    ):
        raise ValueError(
            "result.heading_projection must cover every content/table block"
        )


__all__ = [
    "ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW",
    "ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED",
    "ANALYSIS_BUNDLE_FILENAME",
    "ANALYSIS_BUNDLE_SCHEMA_VERSION_IDENTITY",
    "ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC",
    "FAILURE_FILENAME",
    "PRIVACY_AUDIT_FILENAME",
    "RUN_SUMMARY_FILENAME",
    "PrepareAnalysisArtifactPaths",
    "build_analysis_bundle_artifact",
    "requires_canonical_sentence_normalized_text",
    "resolve_prepare_sentence_normalized_text",
    "validate_analysis_bundle",
    "validate_prepare_analysis_input",
    "validate_prepare_analysis_result",
]
