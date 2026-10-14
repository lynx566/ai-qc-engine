from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.zone_match_bundle import ZONE_MATCH_BUNDLE_FILENAME
from runtime.prepare_analysis import operations as prepare_analysis_operations
from scripts.stage_runners import (
    doc_meta_runner,
    extract_runner,
    filter_runner,
    prepare_analysis_runner,
)
from tests.filter_test_helpers import write_prepare_analysis_filter_input


def _sample_extract_bundle(doc_id: str) -> dict:
    return {
        "doc_id": doc_id,
        "file_name": f"{doc_id}.docx",
        "file_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [{"block_id": "C0001", "kind": "paragraph", "text": "test"}],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def _sample_analysis_bundle(doc_id: str) -> dict:
    bundle = _sample_extract_bundle(doc_id)
    bundle["stage"] = "prepare_analysis"
    bundle["content_blocks"] = [
        {
            "block_id": "h1",
            "kind": "heading",
            "analysis_text": "5.2.1 临床安全性",
            "meta": {"heading_level": 3, "heading_text_stripped": "临床安全性"},
        }
    ]
    return bundle


@pytest.fixture
def mock_git(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (
        extract_runner,
        doc_meta_runner,
        filter_runner,
    ):
        monkeypatch.setattr(
            module,
            "snapshot_git_provenance_before_run",
            lambda **_: {"git_commit": "abc", "git_dirty": False},
        )
    monkeypatch.setattr(
        prepare_analysis_operations,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )


def test_multi_doc_extract_creates_separate_run_dirs(
    tmp_path: Path, mock_git: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import dataclass

    from core.document.doc_identity import DocumentProcessingIdentity

    from execution_flow.document_processing_sequence import (
        DocumentProcessingIntakeLaunchExtractResult,
    )
    from runtime.extract import ExtractDocumentInput, run_extract_operation

    doc_ids = ["alpha_001", "beta_002", "gamma_003"]
    docx_paths: list[Path] = []
    for doc_id in doc_ids:
        docx = tmp_path / "inputs" / f"{doc_id}.docx"
        docx.parent.mkdir(parents=True, exist_ok=True)
        docx.write_bytes(b"docx")
        docx_paths.append(docx)

    def _dev_identity(path: Path | str) -> DocumentProcessingIdentity:
        stem = Path(path).stem
        return DocumentProcessingIdentity(
            doc_id=stem,
            file_hash="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            file_name=Path(path).name,
            display_name=stem,
            created_at="2026-01-01T00:00:00Z",
        )

    @dataclass
    class _FakeBundle:
        doc_id: str
        display_name: str
        file_name: str
        file_hash: str
        source_type: str
        content_blocks: list
        table_blocks: list
        front_matter_blocks: list
        format_blocks: list
        document_meta: dict

    def _fake_extract_step(source_bytes: bytes, *, identity: DocumentProcessingIdentity, extract_config_id):
        return _FakeBundle(
            doc_id=identity.doc_id,
            display_name=identity.display_name,
            file_name=identity.file_name,
            file_hash=identity.file_hash,
            source_type="docx",
            content_blocks=[],
            table_blocks=[],
            front_matter_blocks=[],
            format_blocks=[],
            document_meta={"bundle_schema_version": "0.1.7"},
        )

    def _fake_sequence(
        *,
        project_root: Path,
        source_file: Path | str,
        extract_config_id,
        extract_output_dir=None,
        export_slices=False,
        git_provenance=None,
        **kwargs,
    ) -> DocumentProcessingIntakeLaunchExtractResult:
        _ = kwargs
        path = Path(source_file)
        extract_report = run_extract_operation(
            project_root=project_root,
            document=ExtractDocumentInput(
                source_path=path.resolve(),
                identity=_dev_identity(path),
            ),
            extract_config_id=extract_config_id,
            output_dir=extract_output_dir,
            export_slices=export_slices,
            git_provenance=git_provenance,
        )
        return DocumentProcessingIntakeLaunchExtractResult(
            intake_report=SimpleNamespace(),
            extract_report=extract_report,
        )

    monkeypatch.setattr(extract_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        extract_runner,
        "run_document_processing_intake_launch_extract",
        _fake_sequence,
    )
    monkeypatch.setattr(
        "runtime.extract.operations.run_extract_step",
        _fake_extract_step,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["extract_runner.py", "export", *[item for p in docx_paths for item in ("--file", str(p))]],
    )

    extract_runner.main()

    extract_root = tmp_path / "runs" / "extract"
    session_dirs = sorted(p for p in extract_root.iterdir() if p.is_dir())
    assert len(session_dirs) == len(doc_ids)

    seen_doc_dirs: list[str] = []
    for session_dir in session_dirs:
        assert (session_dir / "index.json").is_file()
        doc_dirs = [p.name for p in session_dir.iterdir() if p.is_dir()]
        assert len(doc_dirs) == 1
        seen_doc_dirs.append(doc_dirs[0])

    assert sorted(seen_doc_dirs) == ["doc_alpha_001", "doc_beta_002", "doc_gamma_003"]


def test_multi_doc_prepare_analysis_single_run_dir(
    tmp_path: Path, mock_git: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle_paths: list[Path] = []
    for doc_id in ("alpha_001", "beta_002", "gamma_003"):
        bundle_dir = tmp_path / "in" / doc_id
        bundle_dir.mkdir(parents=True)
        path = bundle_dir / "bundle.json"
        path.write_text(json.dumps(_sample_extract_bundle(doc_id)), encoding="utf-8")
        bundle_paths.append(path)

    monkeypatch.setattr(prepare_analysis_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_analysis_runner.py",
            "--bundle-dir",
            str(tmp_path / "in"),
            "--language",
            "zh",
            "--clinical-program",
            "clinical_program_001",
        ],
    )

    prepare_analysis_runner.main()

    analysis_root = tmp_path / "runs" / "prepare_analysis"
    session_dirs = [p for p in analysis_root.iterdir() if p.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]
    assert (session_dir / "index.json").is_file()
    index = json.loads((session_dir / "index.json").read_text(encoding="utf-8"))
    assert index["document_count"] == 3
    assert len(index["documents"]) == 3
    assert "run_id" in index


def test_filter_multi_zone_nests_under_doc_dir(
    tmp_path: Path, mock_git: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc_id = "ib_safety_tag_integration_001"
    masked_path = write_prepare_analysis_filter_input(
        tmp_path / doc_id,
        _sample_analysis_bundle(doc_id),
    )

    monkeypatch.setattr(filter_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "filter_runner.py",
            "--analysis-bundle",
            str(masked_path),
            "--filter-job-id",
            "ib_overview",
            "--filter-job-id",
            "ib_clinical_safety",
            "--language",
            "zh",
        ],
    )

    filter_runner.main()

    runs_filter = tmp_path / "runs" / "filter"
    session_dirs = [p for p in runs_filter.iterdir() if p.is_dir()]
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]

    overview = session_dir / f"doc_{doc_id}" / "ib_overview_zh" / ZONE_MATCH_BUNDLE_FILENAME
    safety = session_dir / f"doc_{doc_id}" / "ib_clinical_safety_zh" / ZONE_MATCH_BUNDLE_FILENAME
    assert overview.is_file()
    assert safety.is_file()

    overview_summary = json.loads(overview.parent.joinpath("run_summary.json").read_text())
    safety_summary = json.loads(safety.parent.joinpath("run_summary.json").read_text())
    assert overview_summary["run_id"] == safety_summary["run_id"]
    assert overview_summary["zone_key"] == "ib_overview_zh"
    assert safety_summary["zone_key"] == "ib_clinical_safety_zh"

    index = json.loads((session_dir / "index.json").read_text(encoding="utf-8"))
    assert index["document_count"] == 2
    zone_keys = {entry.get("zone_key") for entry in index["documents"]}
    assert zone_keys == {"ib_overview_zh", "ib_clinical_safety_zh"}
