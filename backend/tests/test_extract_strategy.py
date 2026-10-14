"""Focused tests for Extract extract_config_id strategy resolution."""

from __future__ import annotations

import ast
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
from core.document.extract.strategies import (
    UnsupportedExtractFormatError,
    resolve_extract_strategy,
)
from steps import extract as extract_step_module
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
EXTRACT_STEP_PATH = BACKEND_ROOT / "steps" / "extract.py"
RUNTIME_OPS_PATH = BACKEND_ROOT / "runtime" / "extract" / "operations.py"
PROCESSING_BLOCKS_ROOT = BACKEND_ROOT / "processing_blocks"


def _identity(*, file_name: str = "ib_extract_minimal_001.docx") -> DocumentProcessingIdentity:
    return DocumentProcessingIdentity(
        doc_id=FIXED_DOC_ID,
        file_hash=ESTABLISHED_HASH,
        file_name=file_name,
        display_name=Path(file_name).stem,
        created_at="2026-01-01T00:00:00Z",
    )


def test_processing_blocks_package_removed() -> None:
    assert not PROCESSING_BLOCKS_ROOT.is_dir()


def test_docx_extract_config_id_resolves_to_word_extractor() -> None:
    extractor = resolve_extract_strategy("docx")
    assert extractor is extract_docx_document


def test_unsupported_extract_config_id_raises() -> None:
    with pytest.raises(UnsupportedExtractFormatError, match="Unsupported extract_config_id"):
        resolve_extract_strategy("pdf")


def test_extract_step_requires_explicit_extract_config_id() -> None:
    params = inspect.signature(run_extract_step).parameters
    assert "extract_config_id" in params
    assert params["extract_config_id"].default is inspect.Parameter.empty


def test_extract_step_does_not_import_docx_extractor() -> None:
    source = EXTRACT_STEP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(EXTRACT_STEP_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "core.document.docx" not in imported
    assert "extract_docx_document" not in source
    assert "processing_blocks" not in source


def test_extract_step_resolves_strategy_from_extract_config_id() -> None:
    source_bytes = SAMPLE_DOCX.read_bytes()
    identity = _identity()
    expected = extract_docx_document(source_bytes, identity=identity)
    actual = run_extract_step(source_bytes, identity=identity, extract_config_id="docx")
    assert actual == expected


def test_runtime_requires_explicit_extract_config_id() -> None:
    signature = inspect.signature(run_extract_operation)
    param = signature.parameters["extract_config_id"]
    assert param.default is inspect.Parameter.empty


def test_runtime_does_not_import_docx_extractor() -> None:
    source = RUNTIME_OPS_PATH.read_text(encoding="utf-8")
    assert "extract_docx_document" not in source
    assert "core.document.docx" not in source
    assert "processing_blocks" not in source


def test_runtime_uses_extract_config_id_for_layout_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    captured: dict[str, str] = {}
    original = extract_operations.build_stage_run_layout

    def _capture_layout(**kwargs):
        captured["context"] = kwargs["context"]
        return original(**kwargs)

    monkeypatch.setattr(extract_operations, "build_stage_run_layout", _capture_layout)
    run_extract_operation(
        project_root=tmp_path,
        document=ExtractDocumentInput(
            source_path=SAMPLE_DOCX,
            identity=_identity(),
        ),
        extract_config_id="docx",
        git_provenance={"git_commit": "abc", "git_dirty": False},
    )
    assert captured["context"] == "docx"


def test_runtime_forwards_extract_config_id_to_step(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def _capture_step(source_bytes: bytes, *, identity: DocumentProcessingIdentity, extract_config_id):
        captured["extract_config_id"] = extract_config_id
        return extract_step_module.run(
            source_bytes,
            identity=identity,
            extract_config_id=extract_config_id,
        )

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
    assert captured["extract_config_id"] == "docx"


def test_unsupported_word_input_fails_at_strategy_boundary(tmp_path: Path) -> None:
    bad_file = tmp_path / "sample.txt"
    bad_file.write_text("not docx", encoding="utf-8")
    identity = _identity(file_name="sample.txt")
    with pytest.raises(ValueError, match="Unsupported file type"):
        run_extract_operation(
            project_root=tmp_path,
            document=ExtractDocumentInput(
                source_path=bad_file,
                identity=identity,
            ),
            extract_config_id="docx",
        )
