"""Canonical Extract source projections for evidence and persisted annotations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from application.document_consistency_qc.document_read import (
    DocumentReadError,
    DocumentReadIdentityError,
    DocumentReadValidationError,
    load_document_read_execution,
    resolve_slot_extract_bundle_for_execution,
)
from application.document_consistency_qc.source_annotation import (
    SourceSentenceAnchorReadModel,
    SourceTextRangeReadModel,
    load_source_annotations,
)
from artifacts.source_annotation_state import (
    validate_source_sentence_anchor,
    validate_source_text_range,
)

_BODY_COLLECTIONS = ("front_matter_blocks", "content_blocks", "table_blocks")


class CanonicalSourceReference(Protocol):
    """Structural input shared by Result evidence refs and annotation anchors."""

    @property
    def slot_id(self) -> str: ...
    @property
    def doc_id(self) -> str: ...
    @property
    def block_id(self) -> str: ...
    @property
    def sentence_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class CanonicalDocumentIdentity:
    flow_run_id: str
    slot_id: str
    doc_id: str
    original_file_name: str
    file_hash: str | None


@dataclass(frozen=True, slots=True)
class CanonicalBlockContext:
    kind: str
    original_block_text: str


@dataclass(frozen=True, slots=True)
class CanonicalTableContext:
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class CanonicalSource:
    anchor: SourceSentenceAnchorReadModel
    document: CanonicalDocumentIdentity
    heading_path: tuple[str, ...]
    doc_order_index: int
    original_sentence_text: str
    block_context: CanonicalBlockContext
    table_context: CanonicalTableContext | None = None


@dataclass(frozen=True, slots=True)
class CanonicalSourceAnnotation:
    annotation_id: str
    source: CanonicalSource
    kind: str | None
    range: SourceTextRangeReadModel | None
    selected_original_text: str | None
    replacement_text: str | None
    content: str | None
    created_at: str
    updated_at: str


class CanonicalAnnotationProjectionError(DocumentReadValidationError):
    """Strict read failed for optional records; usable projections remain available.

    Identity mismatches are always raised separately and never salvaged.
    """

    def __init__(
        self,
        *,
        flow_run_id: str,
        annotations: tuple[CanonicalSourceAnnotation, ...],
        unusable_annotation_ids: tuple[str, ...],
    ):
        super().__init__("Some saved source annotations cannot be projected")
        self.flow_run_id = flow_run_id
        self.annotations = annotations
        self.unusable_annotation_ids = unusable_annotation_ids


def _document_identity(execution, slot, bundle) -> CanonicalDocumentIdentity:
    file_name = slot.original_file_name or bundle.get("file_name")
    if not isinstance(file_name, str) or not file_name:
        raise DocumentReadValidationError(
            "missing persisted original document filename"
        )
    if (
        slot.original_file_name
        and bundle.get("file_name")
        and slot.original_file_name != bundle["file_name"]
    ):
        raise DocumentReadIdentityError(
            "Extract filename does not match participant provenance"
        )
    return CanonicalDocumentIdentity(
        execution.flow_run_id, slot.slot_id, slot.doc_id, file_name, slot.file_hash
    )


def load_canonical_documents(
    *, project_root: Path, flow_run_id: str
) -> tuple[CanonicalDocumentIdentity, ...]:
    """Load document identities even when a Result has no evidence sentences."""
    execution = load_document_read_execution(
        project_root=project_root, flow_run_id=flow_run_id
    )
    return tuple(
        _document_identity(
            execution,
            slot,
            resolve_slot_extract_bundle_for_execution(
                execution=execution, slot_id=slot.slot_id
            ),
        )
        for slot in execution.slot_provenance
    )


class _CanonicalSourceResolver:
    """One validated execution, one Extract bundle/index per requested slot."""

    def __init__(self, *, project_root: Path, flow_run_id: str):
        self.execution = load_document_read_execution(
            project_root=project_root, flow_run_id=flow_run_id
        )
        self.slots = {slot.slot_id: slot for slot in self.execution.slot_provenance}
        self.bundles: dict[str, dict[str, Any]] = {}
        self.blocks: dict[str, dict[str, Any]] = {}

    def resolve(
        self, anchor: Mapping[str, str] | CanonicalSourceReference
    ) -> CanonicalSource:
        try:
            fields = validate_source_sentence_anchor(
                anchor
                if isinstance(anchor, Mapping)
                else {
                    key: getattr(anchor, key)
                    for key in ("slot_id", "doc_id", "block_id", "sentence_id")
                }
            )
        except (ValueError, TypeError, AttributeError) as exc:
            raise DocumentReadValidationError(str(exc)) from exc
        slot_id = fields["slot_id"]
        slot = self.slots.get(slot_id)
        if slot is None or fields["doc_id"] != slot.doc_id:
            raise DocumentReadIdentityError(
                "source anchor does not match requested flow participant/document"
            )
        if slot_id not in self.bundles:
            bundle = resolve_slot_extract_bundle_for_execution(
                execution=self.execution, slot_id=slot_id
            )
            indexed = {}
            for collection in _BODY_COLLECTIONS:
                blocks = bundle.get(collection, [])
                if not isinstance(blocks, list):
                    raise DocumentReadValidationError(
                        f"Extract {collection} must be a list"
                    )
                for block in blocks:
                    if not isinstance(block, Mapping) or not isinstance(
                        block.get("block_id"), str
                    ):
                        raise DocumentReadValidationError("invalid Extract block")
                    block_id = block["block_id"]
                    if block_id in indexed:
                        raise DocumentReadValidationError(
                            "duplicate Extract block identity"
                        )
                    indexed[block_id] = block
            self.bundles[slot_id], self.blocks[slot_id] = bundle, indexed
        bundle = self.bundles[slot_id]
        block = self.blocks[slot_id].get(fields["block_id"])
        if block is None:
            raise DocumentReadValidationError(
                "source block is absent from canonical Extract body"
            )
        sentences = block.get("sentences")
        if not isinstance(sentences, list):
            raise DocumentReadValidationError(
                "source block has no canonical sentence index"
            )
        index = {}
        for sentence in sentences:
            if not isinstance(sentence, Mapping) or not isinstance(
                sentence.get("sentence_id"), str
            ):
                raise DocumentReadValidationError("invalid Extract sentence")
            sentence_id = sentence["sentence_id"]
            if sentence_id in index:
                raise DocumentReadValidationError(
                    "duplicate canonical sentence identity"
                )
            index[sentence_id] = sentence
        sentence = index.get(fields["sentence_id"])
        if (
            sentence is None
            or not isinstance(sentence.get("raw_text"), str)
            or not sentence["raw_text"]
        ):
            raise DocumentReadValidationError(
                "canonical sentence missing or has no raw_text"
            )
        order = block.get("doc_order_index")
        if isinstance(order, bool) or not isinstance(order, int) or order < 0:
            raise DocumentReadValidationError(
                "source block missing canonical document order"
            )
        path = block.get("heading_path", [])
        if not isinstance(path, list) or any(
            not isinstance(part, str) for part in path
        ):
            raise DocumentReadValidationError("invalid Extract heading_path")
        if (
            not isinstance(block.get("raw_text"), str)
            or not block["raw_text"]
            or not isinstance(block.get("kind"), str)
        ):
            raise DocumentReadValidationError(
                "source block missing canonical kind/raw_text"
            )
        table = None
        meta = block.get("meta") or {}
        if not isinstance(meta, Mapping):
            raise DocumentReadValidationError("invalid Extract block metadata")
        rows = meta.get("raw_rows")
        if rows is not None:
            if not isinstance(rows, list) or any(
                not isinstance(row, list)
                or any(not isinstance(cell, str) for cell in row)
                for row in rows
            ):
                raise DocumentReadValidationError("invalid Extract raw table rows")
            table = CanonicalTableContext(tuple(tuple(row) for row in rows))
        return CanonicalSource(
            SourceSentenceAnchorReadModel(**fields),
            _document_identity(self.execution, slot, bundle),
            tuple(path),
            order,
            sentence["raw_text"],
            CanonicalBlockContext(block["kind"], block["raw_text"]),
            table,
        )


def project_canonical_sources(
    *,
    project_root: Path,
    flow_run_id: str,
    anchors: Sequence[Mapping[str, str] | CanonicalSourceReference],
) -> tuple[CanonicalSource, ...]:
    """Resolve canonical refs (including Result reader refs); preserve input order."""
    resolver = _CanonicalSourceResolver(
        project_root=project_root, flow_run_id=flow_run_id
    )
    return tuple(resolver.resolve(anchor) for anchor in anchors)


def load_canonical_source_annotations(
    *,
    project_root: Path,
    flow_run_id: str,
) -> tuple[CanonicalSourceAnnotation, ...]:
    """Rejoin all persisted annotations to the same canonical source resolver.

    Legacy untyped records retain kind=None and selected_original_text=None;
    consumers must report their unavailable typed semantics instead of guessing.
    """
    resolver = _CanonicalSourceResolver(
        project_root=project_root, flow_run_id=flow_run_id
    )
    state = load_source_annotations(project_root=project_root, flow_run_id=flow_run_id)
    projected = []
    unusable = []
    for annotation in state.annotations:
        if (
            annotation.anchor.slot_id not in resolver.slots
            or annotation.anchor.doc_id
            != resolver.slots[annotation.anchor.slot_id].doc_id
        ):
            raise DocumentReadIdentityError(
                "annotation anchor does not match flow participant/document"
            )
        try:
            projected.append(_project_annotation(resolver, annotation))
        except DocumentReadIdentityError:
            raise
        except DocumentReadError:
            unusable.append(annotation.annotation_id)
    if unusable:
        raise CanonicalAnnotationProjectionError(
            flow_run_id=flow_run_id,
            annotations=tuple(projected),
            unusable_annotation_ids=tuple(unusable),
        )
    return tuple(projected)


def _project_annotation(resolver, annotation) -> CanonicalSourceAnnotation:
    source = resolver.resolve(annotation.anchor)
    selected = None
    if annotation.range is not None:
        if source.block_context.kind != "paragraph":
            raise DocumentReadValidationError(
                "ranged annotations require a paragraph block"
            )
        try:
            value = validate_source_text_range(asdict(annotation.range))
        except (ValueError, TypeError) as exc:
            raise DocumentReadValidationError(str(exc)) from exc
        if value["end_offset"] > len(source.original_sentence_text):
            raise DocumentReadValidationError(
                "annotation range exceeds canonical raw sentence"
            )
        selected = source.original_sentence_text[
            value["start_offset"] : value["end_offset"]
        ]
        if not selected:
            raise DocumentReadValidationError(
                "annotation range selects empty raw source"
            )
    elif annotation.kind == "comment":
        selected = source.original_sentence_text
    return CanonicalSourceAnnotation(
        annotation.annotation_id,
        source,
        annotation.kind,
        annotation.range,
        selected,
        annotation.replacement_text,
        annotation.content,
        annotation.created_at,
        annotation.updated_at,
    )
