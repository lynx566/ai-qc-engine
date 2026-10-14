"""Tests for canonical Extract runtime operation."""

from __future__ import annotations

import inspect
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.doc_identity import DocumentProcessingIdentity
from runtime.extract import ExtractDocumentInput, run_extract_operation
from runtime.extract import operations as extract_operations
from runtime.io import load_json
from runtime.run_layout import EXTRACT_RUN_DIR_LAYOUT
from tests.extract_test_helpers import build_test_processing_identity

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


def _established_identity(*, doc_id: str = FIXED_DOC_ID) -> DocumentProcessingIdentity:
    return DocumentProcessingIdentity(
        doc_id=doc_id,
        file_hash=ESTABLISHED_HASH,
        file_name="ib_extract_minimal_001.docx",
        display_name="ib_extract_minimal_001",
        created_at="2026-01-01T00:00:00Z",
    )


def _git_prov() -> dict[str, str | bool | None]:
    return {"git_commit": "abc", "git_dirty": False}


def _single_input(
    *,
    source_path: Path = SAMPLE_DOCX,
    identity: DocumentProcessingIdentity | None = None,
) -> ExtractDocumentInput:
    return ExtractDocumentInput(
        source_path=source_path,
        identity=identity or build_test_processing_identity(source_path),
    )


def _run(**kwargs):
    kwargs.setdefault("extract_config_id", "docx")
    return run_extract_operation(**kwargs)


def test_single_document_extract_succeeds(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run(
        project_root=tmp_path,
        document=_single_input(),
        git_provenance=_git_prov(),
    )
    doc_result = report.result.document
    assert doc_result.bundle_path.is_file()
    assert doc_result.run_summary_path.is_file()
    assert report.result.index_path.is_file()


def test_separate_extract_calls_create_separate_runs(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    second_docx = tmp_path / "inputs" / "copy.docx"
    second_docx.parent.mkdir(parents=True)
    second_docx.write_bytes(SAMPLE_DOCX.read_bytes())

    first_report = _run(
        project_root=tmp_path,
        document=_single_input(identity=_established_identity(doc_id="doc_alpha_001")),
        git_provenance=_git_prov(),
    )
    second_report = _run(
        project_root=tmp_path,
        document=_single_input(
            source_path=second_docx,
            identity=_established_identity(doc_id="doc_beta_002"),
        ),
        git_provenance=_git_prov(),
    )

    session_dirs = [p for p in (tmp_path / "runs" / "extract").iterdir() if p.is_dir()]
    assert len(session_dirs) == 2
    assert first_report.result.run_id != second_report.result.run_id
    assert first_report.result.document.output_dir.parent == first_report.result.output_dir
    assert second_report.result.document.output_dir.parent == second_report.result.output_dir


def test_one_doc_leaf_per_run(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run(
        project_root=tmp_path,
        document=_single_input(identity=_established_identity(doc_id="doc_alpha_001")),
        git_provenance=_git_prov(),
    )
    doc_dirs = sorted(
        path.name
        for path in report.result.output_dir.iterdir()
        if path.is_dir()
    )
    assert doc_dirs == ["doc_alpha_001"]


def test_root_index_written_for_single_document(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run(
        project_root=tmp_path,
        document=_single_input(identity=_established_identity(doc_id="doc_alpha_001")),
        git_provenance=_git_prov(),
    )
    index_data = load_json(report.result.index_path)
    assert index_data["step"] == "extract"
    assert len(index_data["documents"]) == 1


def test_bundle_and_summary_persisted(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run(
        project_root=tmp_path,
        document=_single_input(),
        git_provenance=_git_prov(),
    )
    doc_result = report.result.document
    assert doc_result.bundle_path.name == "bundle.json"
    assert doc_result.run_summary_path.name == "run_summary.json"
    bundle = load_json(doc_result.bundle_path)
    summary = load_json(doc_result.run_summary_path)
    assert bundle["doc_id"] == summary["doc_id"]
    assert summary["run_dir_layout"] == EXTRACT_RUN_DIR_LAYOUT


def test_export_slices_false_writes_no_slices_directory(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run(
        project_root=tmp_path,
        document=_single_input(),
        export_slices=False,
        git_provenance=_git_prov(),
    )
    assert not (report.result.document.output_dir / "slices").exists()


def test_export_slices_true_writes_all_slice_files(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run(
        project_root=tmp_path,
        document=_single_input(),
        export_slices=True,
        git_provenance=_git_prov(),
    )
    slices_dir = report.result.document.output_dir / "slices"
    assert slices_dir.is_dir()
    for name in (
        "content_blocks.json",
        "table_blocks.json",
        "front_matter_blocks.json",
        "format_blocks.json",
        "document_meta.json",
    ):
        assert (slices_dir / name).is_file()


def test_runtime_returns_live_document_bundle(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run(
        project_root=tmp_path,
        document=_single_input(),
        git_provenance=_git_prov(),
    )
    doc_result = report.result.document
    assert doc_result.bundle.doc_id == doc_result.identity.doc_id


def test_persisted_bundle_matches_asdict_result(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    report = _run(
        project_root=tmp_path,
        document=_single_input(),
        git_provenance=_git_prov(),
    )
    doc_result = report.result.document
    persisted = load_json(doc_result.bundle_path)
    assert persisted == asdict(doc_result.bundle)


@patch("core.document.doc_identity.generate_doc_id", return_value=FIXED_DOC_ID)
def test_supplied_doc_id_propagates_unchanged(_mock_gen, tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    identity = DocumentProcessingIdentity(
        doc_id=FIXED_DOC_ID,
        file_hash=ESTABLISHED_HASH,
        file_name="ib_extract_minimal_001.docx",
        display_name="ib_extract_minimal_001",
        created_at="2026-01-01T00:00:00Z",
    )
    report = _run(
        project_root=tmp_path,
        document=ExtractDocumentInput(source_path=SAMPLE_DOCX, identity=identity),
        git_provenance=_git_prov(),
    )
    doc_result = report.result.document
    assert doc_result.bundle.doc_id == FIXED_DOC_ID
    assert load_json(doc_result.bundle_path)["doc_id"] == FIXED_DOC_ID


def test_supplied_file_hash_propagates_unchanged(tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    identity = _established_identity()
    report = _run(
        project_root=tmp_path,
        document=ExtractDocumentInput(source_path=SAMPLE_DOCX, identity=identity),
        git_provenance=_git_prov(),
    )
    doc_result = report.result.document
    assert doc_result.bundle.file_hash == ESTABLISHED_HASH
    assert load_json(doc_result.bundle_path)["file_hash"] == ESTABLISHED_HASH


@patch("core.document.doc_identity.generate_doc_id")
def test_runtime_does_not_create_doc_id(mock_generate, tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    identity = _established_identity()
    _run(
        project_root=tmp_path,
        document=ExtractDocumentInput(source_path=SAMPLE_DOCX, identity=identity),
        git_provenance=_git_prov(),
    )
    mock_generate.assert_not_called()


@patch("core.document.doc_identity.compute_file_hash")
@patch("core.document.doc_identity.compute_content_hash")
def test_runtime_does_not_recompute_file_hash(
    mock_content_hash,
    mock_file_hash,
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    identity = _established_identity()
    _run(
        project_root=tmp_path,
        document=ExtractDocumentInput(source_path=SAMPLE_DOCX, identity=identity),
        git_provenance=_git_prov(),
    )
    mock_file_hash.assert_not_called()
    mock_content_hash.assert_not_called()


@patch("runtime.document_processing_bootstrap.bootstrap_processing_identity_from_path")
def test_runtime_does_not_call_bootstrap(mock_bootstrap, tmp_path: Path) -> None:
    assert SAMPLE_DOCX.is_file()
    identity = _established_identity()
    _run(
        project_root=tmp_path,
        document=ExtractDocumentInput(source_path=SAMPLE_DOCX, identity=identity),
        git_provenance=_git_prov(),
    )
    mock_bootstrap.assert_not_called()


def test_missing_source_path_fails_clearly(tmp_path: Path) -> None:
    missing = tmp_path / "missing.docx"
    with pytest.raises(ValueError, match="must be a regular file"):
        _run(
            project_root=tmp_path,
            document=ExtractDocumentInput(
                source_path=missing,
                identity=_established_identity(),
            ),
        )


def test_unsupported_extension_fails_through_word_block(tmp_path: Path) -> None:
    bad_file = tmp_path / "sample.txt"
    bad_file.write_text("not docx", encoding="utf-8")
    identity = DocumentProcessingIdentity(
        doc_id=FIXED_DOC_ID,
        file_hash=ESTABLISHED_HASH,
        file_name="sample.txt",
        display_name="sample",
        created_at="2026-01-01T00:00:00Z",
    )
    with pytest.raises(ValueError, match="Unsupported file type"):
        _run(
            project_root=tmp_path,
            document=ExtractDocumentInput(
                source_path=bad_file,
                identity=identity,
            ),
        )


def test_batch_documents_kwarg_not_supported() -> None:
    signature = inspect.signature(run_extract_operation)
    assert "document" in signature.parameters
    assert "documents" not in signature.parameters
    assert "extract_config_id" in signature.parameters


def test_runtime_calls_extract_step_not_core_extractor_directly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert SAMPLE_DOCX.is_file()
    calls: list[str] = []

    def _fake_step(source_bytes: bytes, *, identity: DocumentProcessingIdentity, extract_config_id):
        calls.append("step")
        from steps.extract import run as real_run

        return real_run(source_bytes, identity=identity, extract_config_id=extract_config_id)

    def _fake_extractor(*args, **kwargs):
        calls.append("core")
        raise AssertionError("runtime must not call core extractor directly")

    monkeypatch.setattr(extract_operations, "run_extract_step", _fake_step)
    monkeypatch.setattr(
        "core.document.docx.extractor.extract_docx_document",
        _fake_extractor,
    )
    _run(
        project_root=tmp_path,
        document=_single_input(),
        git_provenance=_git_prov(),
    )
    assert calls == ["step"]
