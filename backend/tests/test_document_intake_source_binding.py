"""Tests for neutral runtime DocumentIntakeSourceBinding."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.doc_identity import compute_content_hash
from runtime.document_source_binding import (
    DocumentIntakeSourceBinding,
    build_intake_source_binding,
)


def test_document_intake_source_binding_carries_three_fields(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    source.write_bytes(b"binding")
    file_hash = compute_content_hash(b"binding")
    binding = DocumentIntakeSourceBinding(
        file_hash=file_hash,
        original_file_name="sample.docx",
        source_path=source.resolve(),
    )
    assert binding.file_hash == file_hash
    assert binding.original_file_name == "sample.docx"
    assert binding.source_path == source.resolve()


def test_build_intake_source_binding_includes_original_file_name(tmp_path: Path) -> None:
    source = tmp_path / "from_intake.docx"
    source.write_bytes(b"x")
    intake_result = {
        "artifact_type": "request_file_intake_result",
        "schema_version": "0.2.0",
        "document": {
            "file_hash": compute_content_hash(b"x"),
            "original_file_name": "from_intake.docx",
        },
    }
    binding = build_intake_source_binding(
        source_path=source,
        request_file_intake_result=intake_result,
    )
    assert binding.original_file_name == "from_intake.docx"
    assert binding.file_hash == intake_result["document"]["file_hash"]


def test_build_intake_source_binding_requires_original_file_name(tmp_path: Path) -> None:
    source = tmp_path / "missing_name.docx"
    source.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="original_file_name is required"):
        build_intake_source_binding(
            source_path=source,
            request_file_intake_result={
                "artifact_type": "request_file_intake_result",
                "schema_version": "0.2.0",
                "document": {
                    "file_hash": compute_content_hash(b"x"),
                },
            },
        )
