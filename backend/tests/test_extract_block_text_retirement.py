from __future__ import annotations

import sys
from dataclasses import MISSING, asdict, fields
from pathlib import Path

import pytest
from docx import Document

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.prepare_analysis import validate_prepare_analysis_input
from core.document.document_schema import BUNDLE_SCHEMA_VERSION, Block, SourceRef
from core.document.sentence_index import apply_sentence_index_to_block
from core.document.structure.headings import get_heading_text_for_match
from steps.prepare_analysis import _block_normalized_text
from privacy.document_transform import _get_block_normalized_text
from tests.extract_test_helpers import extract_docx_for_test

_MISSING = object()


def _bundle_block(
    *,
    version: str | None,
    normalized_text: object = _MISSING,
    text: object = _MISSING,
) -> dict:
    block: dict[str, object] = {
        "block_id": "C0001",
        "kind": "paragraph",
        "order": 1,
        "sentences": [],
    }
    if normalized_text is not _MISSING:
        block["normalized_text"] = normalized_text
    if text is not _MISSING:
        block["text"] = text

    document_meta = {}
    if version is not None:
        document_meta["bundle_schema_version"] = version
    return {
        "doc_id": "doc_block_text_retirement",
        "document_meta": document_meta,
        "front_matter_blocks": [],
        "content_blocks": [block],
        "table_blocks": [],
        "format_blocks": [],
    }


def test_block_schema_requires_normalized_text_and_has_no_text_field() -> None:
    block_fields = {item.name: item for item in fields(Block)}

    assert BUNDLE_SCHEMA_VERSION == "0.2.1"
    assert "text" not in block_fields
    assert "normalized_text" in block_fields
    assert block_fields["normalized_text"].default is MISSING


def test_new_extract_persistence_has_raw_and_normalized_text_only(tmp_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("A\u00a0B")
    path = tmp_path / "shape.docx"
    doc.save(path)

    payload = asdict(extract_docx_for_test(path))
    assert payload["document_meta"]["bundle_schema_version"] == "0.2.1"
    blocks = payload["content_blocks"]
    assert blocks
    for block in blocks:
        assert isinstance(block["raw_text"], str)
        assert isinstance(block["normalized_text"], str)
        assert "text" not in block


def test_current_schema_text_cannot_replace_missing_normalized_text() -> None:
    bundle = _bundle_block(version="0.1.9", text="legacy substitute")

    with pytest.raises(ValueError, match="normalized_text must be a string"):
        validate_prepare_analysis_input(bundle)


def test_current_schema_normalized_text_must_be_string() -> None:
    bundle = _bundle_block(
        version="0.1.9",
        normalized_text=None,
        text="legacy substitute",
    )

    with pytest.raises(ValueError, match="normalized_text must be a string"):
        validate_prepare_analysis_input(bundle)


@pytest.mark.parametrize("version", [None, "0.1.7", "0.1.8"])
def test_legacy_bundle_may_fallback_to_text(version: str | None) -> None:
    bundle = _bundle_block(version=version, text="legacy text")

    validate_prepare_analysis_input(bundle)
    block = bundle["content_blocks"][0]
    assert _block_normalized_text(block) == "legacy text"
    assert _get_block_normalized_text(block) == "legacy text"


def test_legacy_bundle_prefers_present_normalized_text() -> None:
    bundle = _bundle_block(
        version="0.1.8",
        normalized_text="canonical normalized text",
        text="legacy duplicate",
    )

    validate_prepare_analysis_input(bundle)
    block = bundle["content_blocks"][0]
    assert _block_normalized_text(block) == "canonical normalized text"
    assert _get_block_normalized_text(block) == "canonical normalized text"


def test_present_empty_normalized_text_never_falls_back_to_legacy_text() -> None:
    bundle = _bundle_block(
        version="0.1.9",
        normalized_text="",
        text="must not be used",
    )

    validate_prepare_analysis_input(bundle)
    block = bundle["content_blocks"][0]
    assert _block_normalized_text(block) == ""
    assert _get_block_normalized_text(block) == ""
    assert get_heading_text_for_match(block) == ""


def test_sentence_index_requires_writer_owned_raw_and_normalized_text() -> None:
    block = Block(
        block_id="C0001",
        kind="paragraph",
        raw_text="visible",
        normalized_text=None,  # type: ignore[arg-type]
        loc="BODY:P1",
        source_ref=SourceRef(
            source_type="docx",
            locator_type="paragraph",
            locator_payload={"paragraph_index": 0},
        ),
    )

    with pytest.raises(TypeError, match="normalized_text must already be str"):
        apply_sentence_index_to_block(block)

    block2 = Block(
        block_id="C0001",
        kind="paragraph",
        raw_text=None,  # type: ignore[arg-type]
        normalized_text="visible",
        loc="BODY:P1",
        source_ref=SourceRef(
            source_type="docx",
            locator_type="paragraph",
            locator_payload={"paragraph_index": 0},
        ),
    )

    with pytest.raises(TypeError, match="raw_text must already be str"):
        apply_sentence_index_to_block(block2)
