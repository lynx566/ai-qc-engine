"""Application read/write boundary for persisted source annotation state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.source_annotation_state import (
    SOURCE_ANNOTATION_KIND_COMMENT,
    SOURCE_ANNOTATION_KIND_EDIT,
    SOURCE_ANNOTATION_KIND_HIGHLIGHT,
    SOURCE_ANNOTATION_OPERATION_DIRNAME,
    SOURCE_ANNOTATION_STATE_FILENAME,
    build_source_annotation_state_payload,
    generate_annotation_id,
    validate_source_annotation_content,
    validate_source_annotation_kind,
    validate_source_annotation_replacement_text,
    validate_source_annotation_state,
    validate_source_sentence_anchor,
    validate_source_text_range,
)
from core.document.sentence_index import is_canonical_source_sentence_id
from execution_flow.document_consistency_qc.flow_loader import (
    FlowResumeError,
    load_flow_run_execution,
    resolve_flow_run_output_dir,
)
from runtime.io import load_json, save_json_atomic
from runtime.run_layout import utc_now_iso

from application.document_consistency_qc.document_read import (
    DocumentReadNotFoundError,
    DocumentReadValidationError,
    resolve_slot_extract_bundle,
)

# Blocks eligible for user-facing source annotation — mirrors DocumentView body
# collections (front_matter_blocks, content_blocks, table_blocks). format_blocks
# are excluded because DocumentReader does not surface them.
_DOCUMENT_VIEW_BLOCK_COLLECTIONS = (
    "front_matter_blocks",
    "content_blocks",
    "table_blocks",
)


class SourceAnnotationError(Exception):
    """Base error for source annotation persistence."""


class SourceAnnotationNotFoundError(SourceAnnotationError):
    """Flow or annotation target could not be located."""


class SourceAnnotationValidationError(SourceAnnotationError):
    """Request, anchor, or persisted state failed validation."""


class SourceAnnotationUnknownAnnotationError(SourceAnnotationValidationError):
    """Mutation targeted an annotation that does not exist."""


class SourceAnnotationConflictError(SourceAnnotationValidationError):
    """Mutation conflicts with an existing persisted annotation."""


class SourceAnnotationPersistenceError(SourceAnnotationError):
    """Source annotation state could not be persisted safely."""


@dataclass(frozen=True, slots=True)
class SourceSentenceAnchorReadModel:
    slot_id: str
    doc_id: str
    block_id: str
    sentence_id: str


@dataclass(frozen=True, slots=True)
class SourceTextRangeReadModel:
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class SourceAnnotationReadModel:
    annotation_id: str
    anchor: SourceSentenceAnchorReadModel
    created_at: str
    updated_at: str
    range: SourceTextRangeReadModel | None = None
    kind: str | None = None
    content: str | None = None
    replacement_text: str | None = None


@dataclass(frozen=True, slots=True)
class SourceAnnotationStateReadModel:
    flow_run_id: str
    annotations: tuple[SourceAnnotationReadModel, ...]


def resolve_source_annotation_state_path(*, flow_root: Path) -> Path:
    return flow_root / SOURCE_ANNOTATION_OPERATION_DIRNAME / SOURCE_ANNOTATION_STATE_FILENAME


def _resolve_flow_root(*, project_root: Path, flow_run_id: str) -> Path:
    try:
        return resolve_flow_run_output_dir(
            project_root=project_root,
            flow_run_id=flow_run_id,
        )
    except FlowResumeError as exc:
        raise SourceAnnotationNotFoundError(str(exc)) from exc


def _index_document_view_blocks(
    bundle: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for collection in _DOCUMENT_VIEW_BLOCK_COLLECTIONS:
        blocks = bundle.get(collection)
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            block_id = str(block.get("block_id") or "").strip()
            if not block_id:
                continue
            if block_id in indexed:
                raise SourceAnnotationValidationError(
                    f"duplicate block_id {block_id!r} in extract bundle"
                )
            indexed[block_id] = dict(block)
    return indexed


def _validate_anchor_against_extract_bundle(
    *,
    anchor: Mapping[str, str],
    bundle: Mapping[str, Any],
    provenance_doc_id: str,
) -> None:
    doc_id = anchor["doc_id"]
    block_id = anchor["block_id"]
    sentence_id = anchor["sentence_id"]

    bundle_doc_id = str(bundle.get("doc_id") or "").strip()
    if bundle_doc_id != provenance_doc_id:
        raise SourceAnnotationValidationError(
            f"extract bundle doc_id {bundle_doc_id!r} does not match slot "
            f"provenance doc_id {provenance_doc_id!r}"
        )
    if doc_id != provenance_doc_id:
        raise SourceAnnotationValidationError(
            f"anchor doc_id {doc_id!r} does not match slot extract doc_id "
            f"{provenance_doc_id!r}"
        )

    if not is_canonical_source_sentence_id(sentence_id):
        raise SourceAnnotationValidationError(
            "sentence_id must be a canonical Extract source sentence identity"
        )

    expected_prefix = f"{block_id}:"
    if not sentence_id.startswith(expected_prefix):
        raise SourceAnnotationValidationError(
            "sentence_id block prefix does not match anchor block_id"
        )

    block_index = _index_document_view_blocks(bundle)
    block = block_index.get(block_id)
    if block is None:
        raise SourceAnnotationValidationError(
            f"block_id {block_id!r} is not present in the slot extract bundle"
        )

    sentences = block.get("sentences")
    if not isinstance(sentences, list):
        raise SourceAnnotationValidationError(
            f"block_id {block_id!r} has no sentence index in extract bundle"
        )

    sentence_ids = {
        str(entry.get("sentence_id") or "").strip()
        for entry in sentences
        if isinstance(entry, Mapping)
    }
    if sentence_id not in sentence_ids:
        raise SourceAnnotationValidationError(
            f"sentence_id {sentence_id!r} is not a member of block {block_id!r}"
        )


def _resolve_sentence_raw_text(
    *,
    block: Mapping[str, Any],
    sentence_id: str,
) -> str:
    sentences = block.get("sentences")
    if not isinstance(sentences, list):
        raise SourceAnnotationValidationError(
            f"block_id {block.get('block_id')!r} has no sentence index in extract bundle"
        )

    for entry in sentences:
        if not isinstance(entry, Mapping):
            continue
        entry_sentence_id = str(entry.get("sentence_id") or "").strip()
        if entry_sentence_id != sentence_id:
            continue
        raw_text = entry.get("raw_text")
        if not isinstance(raw_text, str):
            raise SourceAnnotationValidationError(
                f"sentence_id {sentence_id!r} is missing raw_text in extract bundle"
            )
        return raw_text

    raise SourceAnnotationValidationError(
        f"sentence_id {sentence_id!r} is not a member of block {block.get('block_id')!r}"
    )


def _validate_range_against_extract_bundle(
    *,
    anchor: Mapping[str, str],
    bundle: Mapping[str, Any],
    range_payload: Mapping[str, Any],
) -> dict[str, int]:
    block_index = _index_document_view_blocks(bundle)
    block = block_index.get(anchor["block_id"])
    if block is None:
        raise SourceAnnotationValidationError(
            f"block_id {anchor['block_id']!r} is not present in the slot extract bundle"
        )

    block_kind = str(block.get("kind") or "").strip()
    if block_kind != "paragraph":
        raise SourceAnnotationValidationError(
            "source text range is only supported on paragraph blocks in this version"
        )

    validated_range = validate_source_text_range(range_payload)
    raw_text = _resolve_sentence_raw_text(
        block=block,
        sentence_id=anchor["sentence_id"],
    )
    length = len(raw_text)
    start_offset = validated_range["start_offset"]
    end_offset = validated_range["end_offset"]

    if end_offset > length:
        raise SourceAnnotationValidationError(
            "end_offset exceeds sentence raw_text length"
        )

    selected_text = raw_text[start_offset:end_offset]
    if not selected_text:
        raise SourceAnnotationValidationError(
            "source text range must select non-empty sentence raw_text"
        )

    return validated_range


def _source_ranges_overlap(
    left_start: int,
    left_end: int,
    right_start: int,
    right_end: int,
) -> bool:
    return left_start < right_end and right_start < left_end


def _highlight_ranges_overlap(
    left_start: int,
    left_end: int,
    right_start: int,
    right_end: int,
) -> bool:
    return _source_ranges_overlap(left_start, left_end, right_start, right_end)


def _anchors_match(
    left: Mapping[str, Any],
    right: Mapping[str, str],
) -> bool:
    return (
        str(left.get("slot_id") or "") == right["slot_id"]
        and str(left.get("doc_id") or "") == right["doc_id"]
        and str(left.get("block_id") or "") == right["block_id"]
        and str(left.get("sentence_id") or "") == right["sentence_id"]
    )


def _validate_comment_overlap(
    entries: Mapping[str, Mapping[str, Any]],
    *,
    anchor: Mapping[str, str],
    range_payload: Mapping[str, int],
) -> None:
    for entry in entries.values():
        if entry.get("kind") != SOURCE_ANNOTATION_KIND_COMMENT:
            continue
        entry_anchor = entry.get("anchor")
        if not isinstance(entry_anchor, Mapping):
            continue
        if not _anchors_match(entry_anchor, anchor):
            continue
        existing_range = entry.get("range")
        if not isinstance(existing_range, Mapping):
            continue
        if _source_ranges_overlap(
            range_payload["start_offset"],
            range_payload["end_offset"],
            int(existing_range["start_offset"]),
            int(existing_range["end_offset"]),
        ):
            raise SourceAnnotationValidationError(
                "comment range overlaps an existing comment on the same sentence"
            )


def _validate_edit_overlap(
    entries: Mapping[str, Mapping[str, Any]],
    *,
    anchor: Mapping[str, str],
    range_payload: Mapping[str, int],
) -> None:
    for entry in entries.values():
        if entry.get("kind") != SOURCE_ANNOTATION_KIND_EDIT:
            continue
        entry_anchor = entry.get("anchor")
        if not isinstance(entry_anchor, Mapping):
            continue
        if not _anchors_match(entry_anchor, anchor):
            continue
        existing_range = entry.get("range")
        if not isinstance(existing_range, Mapping):
            continue
        if _source_ranges_overlap(
            range_payload["start_offset"],
            range_payload["end_offset"],
            int(existing_range["start_offset"]),
            int(existing_range["end_offset"]),
        ):
            raise SourceAnnotationValidationError(
                "edit range overlaps an existing edit on the same sentence"
            )


def _validate_highlight_overlap(
    entries: Mapping[str, Mapping[str, Any]],
    *,
    anchor: Mapping[str, str],
    range_payload: Mapping[str, int],
) -> None:
    for entry in entries.values():
        if entry.get("kind") != SOURCE_ANNOTATION_KIND_HIGHLIGHT:
            continue
        entry_anchor = entry.get("anchor")
        if not isinstance(entry_anchor, Mapping):
            continue
        if not _anchors_match(entry_anchor, anchor):
            continue
        existing_range = entry.get("range")
        if not isinstance(existing_range, Mapping):
            continue
        if _highlight_ranges_overlap(
            range_payload["start_offset"],
            range_payload["end_offset"],
            int(existing_range["start_offset"]),
            int(existing_range["end_offset"]),
        ):
            raise SourceAnnotationValidationError(
                "highlight range overlaps an existing highlight on the same sentence"
            )


def _resolve_and_validate_anchor(
    *,
    project_root: Path,
    flow_run_id: str,
    anchor_payload: Mapping[str, Any],
) -> dict[str, str]:
    anchor = validate_source_sentence_anchor(anchor_payload)
    slot_id = anchor["slot_id"]

    try:
        execution = load_flow_run_execution(
            project_root=project_root,
            flow_run_id=flow_run_id,
        )
    except FlowResumeError as exc:
        raise SourceAnnotationNotFoundError(str(exc)) from exc

    try:
        bundle = resolve_slot_extract_bundle(
            project_root=project_root,
            flow_run_id=flow_run_id,
            slot_id=slot_id,
        )
    except DocumentReadNotFoundError as exc:
        raise SourceAnnotationNotFoundError(str(exc)) from exc
    except DocumentReadValidationError as exc:
        raise SourceAnnotationValidationError(str(exc)) from exc

    slot_provenance = next(
        (slot for slot in execution.slot_provenance if slot.slot_id == slot_id),
        None,
    )
    if slot_provenance is None:
        raise SourceAnnotationValidationError(
            f"slot_id {slot_id!r} is not configured for flow_run_id={flow_run_id!r}"
        )

    provenance_doc_id = str(slot_provenance.doc_id or "").strip()
    if not provenance_doc_id:
        raise SourceAnnotationValidationError(
            f"slot {slot_id!r} provenance is missing doc_id"
        )

    _validate_anchor_against_extract_bundle(
        anchor=anchor,
        bundle=bundle,
        provenance_doc_id=provenance_doc_id,
    )
    return anchor


def _range_entry_to_read_model(
    entry: Mapping[str, Any],
) -> SourceTextRangeReadModel | None:
    range_payload = entry.get("range")
    if range_payload is None:
        return None
    if not isinstance(range_payload, Mapping):
        raise SourceAnnotationValidationError("range must be an object when present")
    validated = validate_source_text_range(range_payload)
    return SourceTextRangeReadModel(
        start_offset=validated["start_offset"],
        end_offset=validated["end_offset"],
    )


def _annotation_state_to_read_model(
    *,
    flow_run_id: str,
    annotations: Mapping[str, Mapping[str, Any]],
) -> SourceAnnotationStateReadModel:
    entries = tuple(
        SourceAnnotationReadModel(
            annotation_id=annotation_id,
            anchor=SourceSentenceAnchorReadModel(
                slot_id=str(entry["anchor"]["slot_id"]),
                doc_id=str(entry["anchor"]["doc_id"]),
                block_id=str(entry["anchor"]["block_id"]),
                sentence_id=str(entry["anchor"]["sentence_id"]),
            ),
            created_at=str(entry["created_at"]),
            updated_at=str(entry["updated_at"]),
            range=_range_entry_to_read_model(entry),
            kind=(
                str(entry["kind"])
                if isinstance(entry.get("kind"), str) and entry.get("kind")
                else None
            ),
            content=(
                str(entry["content"])
                if isinstance(entry.get("content"), str) and entry.get("content")
                else None
            ),
            replacement_text=(
                str(entry["replacement_text"])
                if isinstance(entry.get("replacement_text"), str)
                and entry.get("replacement_text")
                else None
            ),
        )
        for annotation_id, entry in sorted(annotations.items())
    )
    return SourceAnnotationStateReadModel(
        flow_run_id=flow_run_id,
        annotations=entries,
    )


def source_annotation_state_to_mapping(
    model: SourceAnnotationStateReadModel,
) -> dict[str, object]:
    annotations: dict[str, dict[str, object]] = {}
    for entry in model.annotations:
        payload: dict[str, object] = {
            "annotation_id": entry.annotation_id,
            "anchor": {
                "slot_id": entry.anchor.slot_id,
                "doc_id": entry.anchor.doc_id,
                "block_id": entry.anchor.block_id,
                "sentence_id": entry.anchor.sentence_id,
            },
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }
        if entry.kind is not None:
            payload["kind"] = entry.kind
        if entry.range is not None:
            payload["range"] = {
                "start_offset": entry.range.start_offset,
                "end_offset": entry.range.end_offset,
            }
        if entry.content is not None:
            payload["content"] = entry.content
        if entry.replacement_text is not None:
            payload["replacement_text"] = entry.replacement_text
        annotations[entry.annotation_id] = payload

    return {
        "flow_run_id": model.flow_run_id,
        "annotations": annotations,
    }


def _load_validated_artifact(
    *,
    path: Path,
    flow_run_id: str,
) -> dict[str, Any]:
    if not path.is_file():
        return build_source_annotation_state_payload(
            flow_run_id=flow_run_id,
            annotations={},
        )

    payload = load_json(path)
    validated = validate_source_annotation_state(payload)
    if validated["flow_run_id"] != flow_run_id:
        raise SourceAnnotationValidationError(
            "source annotation artifact flow_run_id does not match request"
        )
    return validated


def _annotation_map_from_artifact(
    artifact: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    annotations = artifact.get("annotations")
    if not isinstance(annotations, Mapping):
        return {}
    return {str(key): dict(value) for key, value in annotations.items()}


def _persist_artifact(
    *,
    path: Path,
    artifact: Mapping[str, Any],
) -> None:
    annotations = artifact.get("annotations")
    if not isinstance(annotations, Mapping) or not annotations:
        if path.is_file():
            path.unlink()
        return

    try:
        save_json_atomic(path, dict(artifact))
    except OSError as exc:
        raise SourceAnnotationPersistenceError(str(exc)) from exc


def load_source_annotations(
    *,
    project_root: Path,
    flow_run_id: str,
) -> SourceAnnotationStateReadModel:
    """Load persisted source annotations for one flow; missing artifact is empty."""

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    artifact = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    return _annotation_state_to_read_model(
        flow_run_id=artifact["flow_run_id"],
        annotations=artifact["annotations"],
    )


def create_source_annotation(
    *,
    project_root: Path,
    flow_run_id: str,
    anchor: Mapping[str, Any],
    range: Mapping[str, Any] | None = None,
    kind: str | None = None,
    content: str | None = None,
    replacement_text: str | None = None,
) -> SourceAnnotationReadModel:
    """Persist one new canonical source sentence anchor annotation."""

    validated_kind = validate_source_annotation_kind(kind)
    if validated_kind == SOURCE_ANNOTATION_KIND_HIGHLIGHT and range is None:
        raise SourceAnnotationValidationError("range is required when kind is highlight")
    if validated_kind == SOURCE_ANNOTATION_KIND_COMMENT and range is None:
        raise SourceAnnotationValidationError("range is required when kind is comment")
    if validated_kind == SOURCE_ANNOTATION_KIND_EDIT and range is None:
        raise SourceAnnotationValidationError("range is required when kind is edit")

    validated_anchor = _resolve_and_validate_anchor(
        project_root=project_root,
        flow_run_id=flow_run_id,
        anchor_payload=anchor,
    )

    validated_range: dict[str, int] | None = None
    validated_content: str | None = None
    validated_replacement_text: str | None = None

    if validated_kind == SOURCE_ANNOTATION_KIND_COMMENT:
        try:
            validated_content = validate_source_annotation_content(content, required=True)
        except (TypeError, ValueError) as exc:
            raise SourceAnnotationValidationError(str(exc)) from exc
        if replacement_text is not None:
            raise SourceAnnotationValidationError(
                "replacement_text is only allowed when kind is edit"
            )
        if not isinstance(range, Mapping):
            raise SourceAnnotationValidationError("range must be an object when present")

        slot_id = validated_anchor["slot_id"]
        try:
            bundle = resolve_slot_extract_bundle(
                project_root=project_root,
                flow_run_id=flow_run_id,
                slot_id=slot_id,
            )
        except DocumentReadNotFoundError as exc:
            raise SourceAnnotationNotFoundError(str(exc)) from exc
        except DocumentReadValidationError as exc:
            raise SourceAnnotationValidationError(str(exc)) from exc

        validated_range = _validate_range_against_extract_bundle(
            anchor=validated_anchor,
            bundle=bundle,
            range_payload=range,
        )
    elif validated_kind == SOURCE_ANNOTATION_KIND_EDIT:
        try:
            validated_replacement_text = validate_source_annotation_replacement_text(
                replacement_text,
                required=True,
            )
        except (TypeError, ValueError) as exc:
            raise SourceAnnotationValidationError(str(exc)) from exc
        if content is not None:
            raise SourceAnnotationValidationError("content is only allowed when kind is comment")
        if not isinstance(range, Mapping):
            raise SourceAnnotationValidationError("range must be an object when present")

        slot_id = validated_anchor["slot_id"]
        try:
            bundle = resolve_slot_extract_bundle(
                project_root=project_root,
                flow_run_id=flow_run_id,
                slot_id=slot_id,
            )
        except DocumentReadNotFoundError as exc:
            raise SourceAnnotationNotFoundError(str(exc)) from exc
        except DocumentReadValidationError as exc:
            raise SourceAnnotationValidationError(str(exc)) from exc

        validated_range = _validate_range_against_extract_bundle(
            anchor=validated_anchor,
            bundle=bundle,
            range_payload=range,
        )
    elif range is not None:
        if not isinstance(range, Mapping):
            raise SourceAnnotationValidationError("range must be an object when present")

        slot_id = validated_anchor["slot_id"]
        try:
            bundle = resolve_slot_extract_bundle(
                project_root=project_root,
                flow_run_id=flow_run_id,
                slot_id=slot_id,
            )
        except DocumentReadNotFoundError as exc:
            raise SourceAnnotationNotFoundError(str(exc)) from exc
        except DocumentReadValidationError as exc:
            raise SourceAnnotationValidationError(str(exc)) from exc

        validated_range = _validate_range_against_extract_bundle(
            anchor=validated_anchor,
            bundle=bundle,
            range_payload=range,
        )
    elif content is not None:
        raise SourceAnnotationValidationError("content is only allowed when kind is comment")
    elif replacement_text is not None:
        raise SourceAnnotationValidationError(
            "replacement_text is only allowed when kind is edit"
        )

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    artifact = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    entries = _annotation_map_from_artifact(artifact)

    if validated_kind == SOURCE_ANNOTATION_KIND_COMMENT and validated_range is not None:
        _validate_comment_overlap(
            entries,
            anchor=validated_anchor,
            range_payload=validated_range,
        )
    elif validated_kind == SOURCE_ANNOTATION_KIND_EDIT and validated_range is not None:
        _validate_edit_overlap(
            entries,
            anchor=validated_anchor,
            range_payload=validated_range,
        )
    elif validated_kind == SOURCE_ANNOTATION_KIND_HIGHLIGHT and validated_range is not None:
        _validate_highlight_overlap(
            entries,
            anchor=validated_anchor,
            range_payload=validated_range,
        )

    annotation_id = generate_annotation_id()
    timestamp = utc_now_iso()
    entry: dict[str, Any] = {
        "annotation_id": annotation_id,
        "anchor": validated_anchor,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    if validated_kind is not None:
        entry["kind"] = validated_kind
    if validated_range is not None:
        entry["range"] = validated_range
    if validated_content is not None:
        entry["content"] = validated_content
    if validated_replacement_text is not None:
        entry["replacement_text"] = validated_replacement_text

    entries[annotation_id] = entry

    next_artifact = build_source_annotation_state_payload(
        flow_run_id=flow_run_id,
        annotations=entries,
    )
    _persist_artifact(path=path, artifact=next_artifact)

    return SourceAnnotationReadModel(
        annotation_id=annotation_id,
        anchor=SourceSentenceAnchorReadModel(**validated_anchor),
        created_at=timestamp,
        updated_at=timestamp,
        range=(
            SourceTextRangeReadModel(**validated_range)
            if validated_range is not None
            else None
        ),
        kind=validated_kind,
        content=validated_content,
        replacement_text=validated_replacement_text,
    )


def update_source_annotation_content(
    *,
    project_root: Path,
    flow_run_id: str,
    annotation_id: str,
    content: str,
) -> SourceAnnotationReadModel:
    """Update persisted comment content for one source annotation."""

    token = str(annotation_id or "").strip()
    if not token:
        raise SourceAnnotationValidationError("annotation_id is required")

    try:
        validated_content = validate_source_annotation_content(content, required=True)
    except (TypeError, ValueError) as exc:
        raise SourceAnnotationValidationError(str(exc)) from exc

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    artifact = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    entries = _annotation_map_from_artifact(artifact)

    if token not in entries:
        raise SourceAnnotationUnknownAnnotationError(
            f"annotation_id {token!r} is not present in source annotations"
        )

    entry = entries[token]
    if entry.get("kind") != SOURCE_ANNOTATION_KIND_COMMENT:
        raise SourceAnnotationValidationError(
            "only comment annotations support content updates"
        )

    created_at = str(entry["created_at"])
    anchor_payload = entry["anchor"]
    if not isinstance(anchor_payload, Mapping):
        raise SourceAnnotationValidationError("anchor must be an object")

    timestamp = utc_now_iso()
    updated_entry: dict[str, Any] = {
        "annotation_id": token,
        "anchor": dict(anchor_payload),
        "kind": SOURCE_ANNOTATION_KIND_COMMENT,
        "content": validated_content,
        "created_at": created_at,
        "updated_at": timestamp,
    }
    existing_range = entry.get("range")
    if isinstance(existing_range, Mapping):
        updated_entry["range"] = dict(existing_range)
    entries[token] = updated_entry

    next_artifact = build_source_annotation_state_payload(
        flow_run_id=flow_run_id,
        annotations=entries,
    )
    _persist_artifact(path=path, artifact=next_artifact)

    return SourceAnnotationReadModel(
        annotation_id=token,
        anchor=SourceSentenceAnchorReadModel(
            slot_id=str(anchor_payload["slot_id"]),
            doc_id=str(anchor_payload["doc_id"]),
            block_id=str(anchor_payload["block_id"]),
            sentence_id=str(anchor_payload["sentence_id"]),
        ),
        created_at=created_at,
        updated_at=timestamp,
        range=_range_entry_to_read_model(updated_entry),
        kind=SOURCE_ANNOTATION_KIND_COMMENT,
        content=validated_content,
    )


def update_source_annotation_replacement_text(
    *,
    project_root: Path,
    flow_run_id: str,
    annotation_id: str,
    replacement_text: str,
) -> SourceAnnotationReadModel:
    """Update persisted edit replacement_text for one source annotation."""

    token = str(annotation_id or "").strip()
    if not token:
        raise SourceAnnotationValidationError("annotation_id is required")

    try:
        validated_replacement_text = validate_source_annotation_replacement_text(
            replacement_text,
            required=True,
        )
    except (TypeError, ValueError) as exc:
        raise SourceAnnotationValidationError(str(exc)) from exc

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    artifact = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    entries = _annotation_map_from_artifact(artifact)

    if token not in entries:
        raise SourceAnnotationUnknownAnnotationError(
            f"annotation_id {token!r} is not present in source annotations"
        )

    entry = entries[token]
    if entry.get("kind") != SOURCE_ANNOTATION_KIND_EDIT:
        raise SourceAnnotationValidationError(
            "only edit annotations support replacement_text updates"
        )

    created_at = str(entry["created_at"])
    anchor_payload = entry["anchor"]
    if not isinstance(anchor_payload, Mapping):
        raise SourceAnnotationValidationError("anchor must be an object")

    existing_range = entry.get("range")
    if not isinstance(existing_range, Mapping):
        raise SourceAnnotationValidationError("range must be an object")

    timestamp = utc_now_iso()
    updated_entry: dict[str, Any] = {
        "annotation_id": token,
        "anchor": dict(anchor_payload),
        "kind": SOURCE_ANNOTATION_KIND_EDIT,
        "replacement_text": validated_replacement_text,
        "range": dict(existing_range),
        "created_at": created_at,
        "updated_at": timestamp,
    }
    entries[token] = updated_entry

    next_artifact = build_source_annotation_state_payload(
        flow_run_id=flow_run_id,
        annotations=entries,
    )
    _persist_artifact(path=path, artifact=next_artifact)

    return SourceAnnotationReadModel(
        annotation_id=token,
        anchor=SourceSentenceAnchorReadModel(
            slot_id=str(anchor_payload["slot_id"]),
            doc_id=str(anchor_payload["doc_id"]),
            block_id=str(anchor_payload["block_id"]),
            sentence_id=str(anchor_payload["sentence_id"]),
        ),
        created_at=created_at,
        updated_at=timestamp,
        range=_range_entry_to_read_model(updated_entry),
        kind=SOURCE_ANNOTATION_KIND_EDIT,
        replacement_text=validated_replacement_text,
    )


def delete_source_annotation(
    *,
    project_root: Path,
    flow_run_id: str,
    annotation_id: str,
) -> SourceAnnotationStateReadModel:
    """Remove one persisted source annotation."""

    token = str(annotation_id or "").strip()
    if not token:
        raise SourceAnnotationValidationError("annotation_id is required")

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    artifact = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    entries = _annotation_map_from_artifact(artifact)

    if token not in entries:
        raise SourceAnnotationUnknownAnnotationError(
            f"annotation_id {token!r} is not present in source annotations"
        )

    entries.pop(token, None)
    next_artifact = build_source_annotation_state_payload(
        flow_run_id=flow_run_id,
        annotations=entries,
    )
    _persist_artifact(path=path, artifact=next_artifact)
    return _annotation_state_to_read_model(
        flow_run_id=flow_run_id,
        annotations=entries,
    )


def delete_source_annotations_by_kind(
    *,
    project_root: Path,
    flow_run_id: str,
    doc_id: str,
    kind: str,
) -> SourceAnnotationStateReadModel:
    """Remove all persisted annotations of one kind within one document scope."""

    validated_kind = validate_source_annotation_kind(kind)
    if validated_kind not in {
        SOURCE_ANNOTATION_KIND_COMMENT,
        SOURCE_ANNOTATION_KIND_EDIT,
    }:
        raise SourceAnnotationValidationError(
            "kind must be comment or edit for bulk deletion"
        )

    doc_token = str(doc_id or "").strip()
    if not doc_token:
        raise SourceAnnotationValidationError("doc_id is required")

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    artifact = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    entries = _annotation_map_from_artifact(artifact)

    filtered_entries = {
        annotation_id: entry
        for annotation_id, entry in entries.items()
        if not (
            str(entry.get("kind") or "") == validated_kind
            and str(entry.get("anchor", {}).get("doc_id") or "") == doc_token
        )
    }

    next_artifact = build_source_annotation_state_payload(
        flow_run_id=flow_run_id,
        annotations=filtered_entries,
    )
    _persist_artifact(path=path, artifact=next_artifact)
    return _annotation_state_to_read_model(
        flow_run_id=flow_run_id,
        annotations=filtered_entries,
    )


@dataclass(frozen=True, slots=True)
class LegacySourceHighlightCleanupSummary:
    flow_run_id: str
    doc_id: str
    legacy_highlights_found: int
    legacy_highlights_deleted: int
    revisions_preserved: int
    comments_preserved: int


def _annotation_doc_id(entry: Mapping[str, Any]) -> str:
    anchor = entry.get("anchor")
    if not isinstance(anchor, Mapping):
        return ""
    return str(anchor.get("doc_id") or "").strip()


def _count_doc_scoped_kinds(
    entries: Mapping[str, Mapping[str, Any]],
    *,
    doc_id: str,
) -> tuple[int, int, int]:
    highlight_count = 0
    edit_count = 0
    comment_count = 0
    for entry in entries.values():
        if _annotation_doc_id(entry) != doc_id:
            continue
        kind = str(entry.get("kind") or "")
        if kind == SOURCE_ANNOTATION_KIND_HIGHLIGHT:
            highlight_count += 1
        elif kind == SOURCE_ANNOTATION_KIND_EDIT:
            edit_count += 1
        elif kind == SOURCE_ANNOTATION_KIND_COMMENT:
            comment_count += 1
    return highlight_count, edit_count, comment_count


def count_legacy_source_highlights(
    *,
    project_root: Path,
    flow_run_id: str,
    doc_id: str,
) -> int:
    """Count persisted legacy highlight annotations for one document scope."""

    doc_token = str(doc_id or "").strip()
    if not doc_token:
        raise SourceAnnotationValidationError("doc_id is required")

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    artifact = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    entries = _annotation_map_from_artifact(artifact)
    highlight_count, _, _ = _count_doc_scoped_kinds(entries, doc_id=doc_token)
    return highlight_count


def delete_legacy_source_highlights(
    *,
    project_root: Path,
    flow_run_id: str,
    doc_id: str,
) -> LegacySourceHighlightCleanupSummary:
    """Delete persisted legacy highlight annotations for one document scope."""

    doc_token = str(doc_id or "").strip()
    if not doc_token:
        raise SourceAnnotationValidationError("doc_id is required")

    flow_root = _resolve_flow_root(project_root=project_root, flow_run_id=flow_run_id)
    path = resolve_source_annotation_state_path(flow_root=flow_root)
    artifact = _load_validated_artifact(path=path, flow_run_id=flow_run_id)
    entries = _annotation_map_from_artifact(artifact)
    highlight_count, edit_count, comment_count = _count_doc_scoped_kinds(
        entries,
        doc_id=doc_token,
    )

    if highlight_count == 0:
        return LegacySourceHighlightCleanupSummary(
            flow_run_id=flow_run_id,
            doc_id=doc_token,
            legacy_highlights_found=0,
            legacy_highlights_deleted=0,
            revisions_preserved=edit_count,
            comments_preserved=comment_count,
        )

    filtered_entries = {
        annotation_id: entry
        for annotation_id, entry in entries.items()
        if not (
            str(entry.get("kind") or "") == SOURCE_ANNOTATION_KIND_HIGHLIGHT
            and _annotation_doc_id(entry) == doc_token
        )
    }

    next_artifact = build_source_annotation_state_payload(
        flow_run_id=flow_run_id,
        annotations=filtered_entries,
    )
    _persist_artifact(path=path, artifact=next_artifact)
    return LegacySourceHighlightCleanupSummary(
        flow_run_id=flow_run_id,
        doc_id=doc_token,
        legacy_highlights_found=highlight_count,
        legacy_highlights_deleted=highlight_count,
        revisions_preserved=edit_count,
        comments_preserved=comment_count,
    )


__all__ = [
    "LegacySourceHighlightCleanupSummary",
    "SourceAnnotationConflictError",
    "SourceAnnotationError",
    "SourceAnnotationNotFoundError",
    "SourceAnnotationPersistenceError",
    "SourceAnnotationReadModel",
    "SourceAnnotationStateReadModel",
    "SourceAnnotationUnknownAnnotationError",
    "SourceAnnotationValidationError",
    "SourceSentenceAnchorReadModel",
    "SourceTextRangeReadModel",
    "count_legacy_source_highlights",
    "create_source_annotation",
    "delete_legacy_source_highlights",
    "delete_source_annotation",
    "delete_source_annotations_by_kind",
    "load_source_annotations",
    "resolve_source_annotation_state_path",
    "source_annotation_state_to_mapping",
    "update_source_annotation_content",
    "update_source_annotation_replacement_text",
]
