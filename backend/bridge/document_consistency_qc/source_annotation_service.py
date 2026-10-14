"""Thin source annotation transport service for Document Consistency QC."""

from __future__ import annotations

from application.document_consistency_qc.source_annotation import (
    SourceAnnotationError,
    SourceAnnotationReadModel,
    SourceAnnotationValidationError,
    create_source_annotation,
    delete_source_annotation,
    delete_source_annotations_by_kind,
    load_source_annotations,
    source_annotation_state_to_mapping,
    update_source_annotation_content,
    update_source_annotation_replacement_text,
)
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.errors import map_source_annotation_error


def _annotation_read_model_to_payload(created: SourceAnnotationReadModel) -> dict[str, object]:
    payload: dict[str, object] = {
        "annotation_id": created.annotation_id,
        "anchor": {
            "slot_id": created.anchor.slot_id,
            "doc_id": created.anchor.doc_id,
            "block_id": created.anchor.block_id,
            "sentence_id": created.anchor.sentence_id,
        },
        "created_at": created.created_at,
        "updated_at": created.updated_at,
    }
    if created.kind is not None:
        payload["kind"] = created.kind
    if created.range is not None:
        payload["range"] = {
            "start_offset": created.range.start_offset,
            "end_offset": created.range.end_offset,
        }
    if created.content is not None:
        payload["content"] = created.content
    if created.replacement_text is not None:
        payload["replacement_text"] = created.replacement_text
    return payload


def load_source_annotations_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    flow_run_id: str,
) -> dict[str, object]:
    project_root = config.project_root or config.default_workspace_root
    try:
        model = load_source_annotations(
            project_root=project_root,
            flow_run_id=flow_run_id,
        )
    except SourceAnnotationError as exc:
        raise map_source_annotation_error(exc) from exc
    return source_annotation_state_to_mapping(model)


def create_source_annotation_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    flow_run_id: str,
    anchor: dict[str, str],
    range: dict[str, int] | None = None,
    kind: str | None = None,
    content: str | None = None,
    replacement_text: str | None = None,
) -> dict[str, object]:
    project_root = config.project_root or config.default_workspace_root
    try:
        created = create_source_annotation(
            project_root=project_root,
            flow_run_id=flow_run_id,
            anchor=anchor,
            range=range,
            kind=kind,
            content=content,
            replacement_text=replacement_text,
        )
    except SourceAnnotationError as exc:
        raise map_source_annotation_error(exc) from exc
    return _annotation_read_model_to_payload(created)


def update_source_annotation_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    flow_run_id: str,
    annotation_id: str,
    content: str | None = None,
    replacement_text: str | None = None,
) -> dict[str, object]:
    project_root = config.project_root or config.default_workspace_root
    try:
        if replacement_text is not None:
            updated = update_source_annotation_replacement_text(
                project_root=project_root,
                flow_run_id=flow_run_id,
                annotation_id=annotation_id,
                replacement_text=replacement_text,
            )
        elif content is not None:
            updated = update_source_annotation_content(
                project_root=project_root,
                flow_run_id=flow_run_id,
                annotation_id=annotation_id,
                content=content,
            )
        else:
            raise SourceAnnotationValidationError(
                "content or replacement_text is required"
            )
    except SourceAnnotationError as exc:
        raise map_source_annotation_error(exc) from exc
    return _annotation_read_model_to_payload(updated)


def delete_source_annotation_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    flow_run_id: str,
    annotation_id: str,
) -> dict[str, object]:
    project_root = config.project_root or config.default_workspace_root
    try:
        model = delete_source_annotation(
            project_root=project_root,
            flow_run_id=flow_run_id,
            annotation_id=annotation_id,
        )
    except SourceAnnotationError as exc:
        raise map_source_annotation_error(exc) from exc
    return source_annotation_state_to_mapping(model)


def delete_source_annotations_by_kind_request(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    flow_run_id: str,
    doc_id: str,
    kind: str,
) -> dict[str, object]:
    project_root = config.project_root or config.default_workspace_root
    try:
        model = delete_source_annotations_by_kind(
            project_root=project_root,
            flow_run_id=flow_run_id,
            doc_id=doc_id,
            kind=kind,
        )
    except SourceAnnotationError as exc:
        raise map_source_annotation_error(exc) from exc
    return source_annotation_state_to_mapping(model)


__all__ = [
    "create_source_annotation_request",
    "delete_source_annotation_request",
    "delete_source_annotations_by_kind_request",
    "load_source_annotations_request",
    "update_source_annotation_request",
]
