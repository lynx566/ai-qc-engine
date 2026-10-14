from __future__ import annotations

from io import BytesIO

from core.document.doc_identity import DocumentProcessingIdentity
from core.document.docx.handlers import (
    DOCX_HANDLERS_VERSION,
    DOCX_PARSER_NAME,
    build_document_meta,
    extract_body_blocks_ordered,
    extract_format_blocks,
)
from core.document.docx.revision_text import RevisionTextObserver
from core.document.document_schema import BUNDLE_SCHEMA_VERSION, DocumentBundle
from core.document.sentence_index import (
    SENTENCE_INDEX_POLICY,
    SENTENCE_INDEX_VERSION,
    apply_sentence_index,
)

from docx import Document



def extract_docx_document(
    source_bytes: bytes,
    *,
    identity: DocumentProcessingIdentity,
) -> DocumentBundle:
    """
    Extract in-memory DOCX bytes into a normalized DocumentBundle.

    Scope matches the implementation generation in DOCX_HANDLERS_VERSION:
    - docx only
    - basic paragraph / table / header / footer extraction
    - lightweight front matter classification
    - Final / No Markup revision-aware body text (w:ins/moveTo include; w:del/moveFrom exclude)
    - comments do not enter body text

    The source is received as immutable bytes; the caller owns physical file
    access. DOCX compatibility is validated from ``identity.file_name``.
    """
    file_name = (identity.file_name or "").strip().lower()
    if not file_name.endswith(".docx"):
        raise ValueError(f"Unsupported file type for docx extractor: {identity.file_name}")

    doc = Document(BytesIO(source_bytes))

    revision_observer = RevisionTextObserver()
    parse_warnings: list[str] = []

    front_matter_blocks, content_blocks, table_blocks = extract_body_blocks_ordered(
        doc=doc,
        revision_observer=revision_observer,
    )
    format_blocks = extract_format_blocks(
        doc=doc,
        revision_observer=revision_observer,
    )
    parse_warnings.extend(revision_observer.to_parse_warnings())

    for group in (front_matter_blocks, content_blocks, table_blocks, format_blocks):
        for i, block in enumerate(group):
            block.order = i + 1

    bundle = DocumentBundle(
        doc_id=identity.doc_id,
        file_name=identity.file_name,
        display_name=identity.display_name,
        file_hash=identity.file_hash,
        created_at=identity.created_at,
        source_type="docx",
        front_matter_blocks=front_matter_blocks,
        content_blocks=content_blocks,
        table_blocks=table_blocks,
        format_blocks=format_blocks,
        document_meta={},
    )
    apply_sentence_index(bundle)

    document_meta = build_document_meta(
        doc=doc,
        front_matter_blocks=front_matter_blocks,
        table_blocks=table_blocks,
        format_blocks=format_blocks,
        parse_warnings=parse_warnings,
        parser_type=DOCX_PARSER_NAME,
        parser_version=DOCX_HANDLERS_VERSION,
        bundle_schema_version=BUNDLE_SCHEMA_VERSION,
    )

    document_meta["sentence_index_version"] = SENTENCE_INDEX_VERSION
    document_meta["sentence_index_policy"] = SENTENCE_INDEX_POLICY
    bundle.document_meta = document_meta
    return bundle
