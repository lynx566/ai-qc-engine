from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.doc_identity import (
    FILE_HASH_PREFIX,
    SHA256_HEX_LENGTH,
    DocumentProcessingIdentity,
    build_display_name,
    build_document_processing_identity,
    compute_file_hash,
    generate_doc_id,
    require_bundle_file_hash,
)
from core.document.docx import extract_docx_document
from tests.extract_test_helpers import build_test_processing_identity, extract_docx_for_test

FIXED_DOC_ID = "doc_00000000-0000-4000-8000-000000000001"
ESTABLISHED_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)
SAMPLE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)


def test_generate_doc_id_prefix() -> None:
    doc_id = generate_doc_id()
    assert doc_id.startswith("doc_")


def test_build_display_name_stem() -> None:
    path = Path("OOJ-VT8802-01 手册 V1.0.docx")
    assert build_display_name(path) == "OOJ-VT8802-01 手册 V1.0"


def test_compute_file_hash_stable_across_calls(tmp_path: Path) -> None:
    docx = tmp_path / "sample.docx"
    docx.write_bytes(b"hello")
    first = compute_file_hash(docx)
    second = compute_file_hash(docx)
    assert first == second


def test_compute_file_hash_changes_when_content_changes(tmp_path: Path) -> None:
    file_a = tmp_path / "a.docx"
    file_b = tmp_path / "b.docx"
    file_a.write_bytes(b"version-a")
    file_b.write_bytes(b"version-b")
    assert compute_file_hash(file_a) != compute_file_hash(file_b)


def test_compute_file_hash_format(tmp_path: Path) -> None:
    docx = tmp_path / "sample.docx"
    docx.write_bytes(b"hello")
    digest = compute_file_hash(docx)
    assert digest.startswith(FILE_HASH_PREFIX)
    hex_part = digest.removeprefix(FILE_HASH_PREFIX)
    assert len(hex_part) == SHA256_HEX_LENGTH
    assert hex_part == hashlib.sha256(b"hello").hexdigest()


def test_require_bundle_file_hash() -> None:
    with pytest.raises(ValueError, match="bundle.file_hash is required"):
        require_bundle_file_hash({}, label="bundle")


def test_build_document_processing_identity_accepts_established_hash() -> None:
    identity = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name="ib_001.docx",
    )
    assert identity.file_hash == ESTABLISHED_HASH


@patch("core.document.doc_identity.generate_doc_id", return_value=FIXED_DOC_ID)
def test_build_document_processing_identity_generates_doc_id(_mock_gen) -> None:
    identity = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name="ib_001.docx",
    )
    assert identity.doc_id == FIXED_DOC_ID


def test_build_document_processing_identity_same_hash_different_doc_id() -> None:
    first = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name="ib_001.docx",
    )
    second = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name="ib_001.docx",
    )
    assert first.file_hash == second.file_hash == ESTABLISHED_HASH
    assert first.doc_id != second.doc_id


def test_build_document_processing_identity_display_name_from_filename() -> None:
    identity = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name="ib_001.docx",
    )
    assert identity.file_name == "ib_001.docx"
    assert identity.display_name == "ib_001"
    assert identity.created_at.endswith("Z")


@patch("core.document.doc_identity.compute_file_hash")
@patch("core.document.doc_identity.generate_doc_id", return_value=FIXED_DOC_ID)
def test_build_document_processing_identity_does_not_hash_or_read_fs(
    _mock_gen,
    mock_hash,
) -> None:
    identity = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name="ib_001.docx",
    )
    mock_hash.assert_not_called()
    assert identity.doc_id == FIXED_DOC_ID


def test_extract_requires_explicit_identity() -> None:
    with pytest.raises(TypeError):
        extract_docx_document(SAMPLE.read_bytes())  # type: ignore[call-arg]


@patch("core.document.doc_identity.generate_doc_id", return_value=FIXED_DOC_ID)
def test_extract_preserves_supplied_doc_id(_mock_gen) -> None:
    identity = build_document_processing_identity(
        file_hash=compute_file_hash(SAMPLE),
        original_file_name=SAMPLE.name,
    )
    bundle = extract_docx_document(SAMPLE.read_bytes(), identity=identity)
    assert bundle.doc_id == FIXED_DOC_ID


def test_extract_preserves_supplied_file_hash() -> None:
    identity = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name=SAMPLE.name,
    )
    bundle = extract_docx_document(SAMPLE.read_bytes(), identity=identity)
    assert bundle.file_hash == ESTABLISHED_HASH


def test_extract_preserves_supplied_name_and_timestamp_metadata() -> None:
    identity = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name="custom_name.docx",
    )
    bundle = extract_docx_document(SAMPLE.read_bytes(), identity=identity)
    assert bundle.file_name == "custom_name.docx"
    assert bundle.display_name == "custom_name"
    assert bundle.created_at == identity.created_at


@patch("core.document.doc_identity.compute_file_hash")
def test_extract_does_not_compute_file_hash(mock_hash) -> None:
    identity = build_document_processing_identity(
        file_hash=ESTABLISHED_HASH,
        original_file_name=SAMPLE.name,
    )
    extract_docx_document(SAMPLE.read_bytes(), identity=identity)
    mock_hash.assert_not_called()


@patch("core.document.doc_identity.generate_doc_id")
def test_extract_does_not_generate_doc_id(mock_gen) -> None:
    identity = DocumentProcessingIdentity(
        doc_id=FIXED_DOC_ID,
        file_hash=ESTABLISHED_HASH,
        file_name=SAMPLE.name,
        display_name=SAMPLE.stem,
        created_at="2026-01-01T00:00:00Z",
    )
    extract_docx_document(SAMPLE.read_bytes(), identity=identity)
    mock_gen.assert_not_called()


def test_extract_retry_reuses_same_identity_fields() -> None:
    identity = build_test_processing_identity(SAMPLE)
    first = extract_docx_document(SAMPLE.read_bytes(), identity=identity)
    second = extract_docx_document(SAMPLE.read_bytes(), identity=identity)
    assert first.doc_id == second.doc_id == identity.doc_id
    assert first.file_hash == second.file_hash == identity.file_hash
    assert first.file_name == second.file_name == identity.file_name
    assert first.display_name == second.display_name == identity.display_name
    assert first.created_at == second.created_at == identity.created_at


def test_two_bootstraps_same_path_different_doc_id() -> None:
    first = build_test_processing_identity(SAMPLE)
    second = build_test_processing_identity(SAMPLE)
    assert first.file_hash == second.file_hash
    assert first.doc_id != second.doc_id


def test_extract_docx_document_doc_id_not_filename() -> None:
    bundle = extract_docx_for_test(SAMPLE)
    assert bundle.doc_id.startswith("doc_")
    assert bundle.doc_id != bundle.file_name
    assert bundle.doc_id != bundle.display_name
    assert bundle.display_name == SAMPLE.stem
    assert bundle.file_name == SAMPLE.name
    assert bundle.file_hash is not None and bundle.file_hash.startswith(FILE_HASH_PREFIX)
    assert bundle.file_hash == compute_file_hash(SAMPLE)
    assert bundle.document_meta.get("bundle_schema_version") == "0.2.1"
    assert bundle.content_blocks[0].block_id == "C0001"
    assert bundle.doc_id not in bundle.content_blocks[0].block_id
