"""Focused tests proving the canonical Extract Step is an in-memory boundary."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.doc_identity import DocumentProcessingIdentity
from core.document.docx import extract_docx_document
from core.document.document_schema import DocumentBundle
from steps.extract import run as run_extract_step
from runtime.extract import ExtractDocumentInput, run_extract_operation
from runtime.extract import operations as extract_operations

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_minimal_001.docx"
)
FIXED_DOC_ID = "doc_00000000-0000-4000-8000-000000000001"
ESTABLISHED_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _identity(*, file_name: str = "ib_extract_minimal_001.docx") -> DocumentProcessingIdentity:
    return DocumentProcessingIdentity(
        doc_id=FIXED_DOC_ID,
        file_hash=ESTABLISHED_HASH,
        file_name=file_name,
        display_name=Path(file_name).stem,
        created_at="2026-01-01T00:00:00Z",
    )


def test_step_returns_bundle_from_bytes_and_identity() -> None:
    source_bytes = SAMPLE_DOCX.read_bytes()
    bundle = run_extract_step(
        source_bytes,
        identity=_identity(),
        extract_config_id="docx",
    )
    assert isinstance(bundle, DocumentBundle)
    assert bundle.doc_id == FIXED_DOC_ID
    assert bundle.file_hash == ESTABLISHED_HASH
    assert bundle.source_type == "docx"
    assert bundle.content_blocks


def test_word_strategy_rejects_non_docx_file_name() -> None:
    identity = _identity(file_name="sample.txt")
    with pytest.raises(ValueError, match="Unsupported file type"):
        run_extract_step(
            b"not docx",
            identity=identity,
            extract_config_id="docx",
        )


def test_step_signature_is_in_memory() -> None:
    params = inspect.signature(run_extract_step).parameters
    assert "source_bytes" in params
    assert "identity" in params
    assert "extract_config_id" in params
    assert "source_path" not in params
    assert "file_path" not in params
    assert params["source_bytes"].annotation == "bytes"


def test_step_source_has_no_filesystem_path_handling() -> None:
    source = (BACKEND_ROOT / "steps" / "extract.py").read_text(
        encoding="utf-8"
    )
    for token in (
        "open(",
        "read_bytes",
        "read_text",
        "write_text",
        "write_bytes",
        "mkdir",
        "runs/",
        "Path(",
        "pathlib",
        "save_json",
    ):
        assert token not in source, f"Extract Step source must not contain {token!r}"


def test_word_extractor_parses_in_memory_docx() -> None:
    bundle = extract_docx_document(SAMPLE_DOCX.read_bytes(), identity=_identity())
    assert isinstance(bundle, DocumentBundle)
    assert bundle.source_type == "docx"
    assert bundle.doc_id == FIXED_DOC_ID


def test_word_extractor_rejects_non_docx_file_name() -> None:
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_docx_document(b"not docx", identity=_identity(file_name="sample.txt"))


def test_runtime_reads_source_and_passes_bytes_to_step(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert SAMPLE_DOCX.is_file()
    captured: dict[str, object] = {}

    def _capture_step(source_bytes: bytes, *, identity: DocumentProcessingIdentity, extract_config_id):
        captured["source_bytes"] = source_bytes
        captured["identity"] = identity
        captured["extract_config_id"] = extract_config_id
        from steps.extract import run as real_run

        return real_run(source_bytes, identity=identity, extract_config_id=extract_config_id)

    monkeypatch.setattr(extract_operations, "run_extract_step", _capture_step)
    run_extract_operation(
        project_root=tmp_path,
        document=ExtractDocumentInput(
            source_path=SAMPLE_DOCX,
            identity=_identity(),
        ),
        extract_config_id="docx",
        git_provenance={"git_commit": "abc", "git_dirty": False},
    )

    assert captured["source_bytes"] == SAMPLE_DOCX.read_bytes()
    assert isinstance(captured["source_bytes"], bytes)
    assert captured["identity"] is not None
    assert captured["extract_config_id"] == "docx"
