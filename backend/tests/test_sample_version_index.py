from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.doc_identity import compute_file_hash
from core.samples.sample_version_index import (
    SAMPLE_VERSION_INDEX_KIND,
    SAMPLE_VERSION_INDEX_SCHEMA_VERSION,
    file_hash_to_snapshot_dir_name,
    load_snapshot_record,
    register_sample,
    resolve_snapshot_path,
    snapshot_index_abs_path,
    snapshot_rel_path,
)
from scripts.tools import register_sample as register_sample_cli


def _write_sample(
    samples_root: Path,
    *,
    rel_dir: str,
    file_name: str,
    content: bytes,
) -> Path:
    source_dir = samples_root / Path(rel_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / file_name
    source_file.write_bytes(content)
    return source_file


def test_file_hash_to_snapshot_dir_name() -> None:
    file_hash = (
        "sha256:0d22ef58655ccfe6fd739a8f0165dda24d8ad81f99d190f9ac0bacfc5baaa7d8"
    )
    assert file_hash_to_snapshot_dir_name(file_hash) == "sha256_0d22ef58655ccfe6"


def test_snapshot_rel_path() -> None:
    file_hash = (
        "sha256:0d22ef58655ccfe6fd739a8f0165dda24d8ad81f99d190f9ac0bacfc5baaa7d8"
    )
    rel = snapshot_rel_path(
        file_hash=file_hash,
        file_name="VT8802 IB.docx",
        source_rel_path="docx/zh/clinical_program_001_vt8802/VT8802 IB.docx",
    )
    assert rel == (
        "snapshots/docx/zh/clinical_program_001_vt8802/"
        "sha256_0d22ef58655ccfe6/VT8802 IB.docx"
    )


def test_register_creates_snapshot_and_per_dir_index(tmp_path: Path) -> None:
    samples_root = tmp_path / "clinical_trial_doc"
    source_file = _write_sample(
        samples_root,
        rel_dir="docx/zh/clinical_program_001_vt8802",
        file_name="sample.docx",
        content=b"version-a",
    )

    result = register_sample(source_file, samples_root, git_root=None)

    assert result.skipped is False
    assert result.file_hash == compute_file_hash(source_file)
    assert result.snapshot_path.is_file()
    assert result.snapshot_path.read_bytes() == b"version-a"

    # per-snapshot index is inside the sha256_xxx/ directory
    assert result.index_path == snapshot_index_abs_path(
        file_hash=result.file_hash,
        source_rel_path="docx/zh/clinical_program_001_vt8802/sample.docx",
        samples_root=samples_root,
    )
    assert result.index_path.is_file()

    record = load_snapshot_record(result.file_hash, samples_root=samples_root)
    assert record is not None
    assert record["schema_version"] == SAMPLE_VERSION_INDEX_SCHEMA_VERSION
    assert record["kind"] == SAMPLE_VERSION_INDEX_KIND
    assert record["file_hash"] == result.file_hash
    assert record["file_name"] == "sample.docx"
    assert record["source_path_at_registration"] == (
        "docx/zh/clinical_program_001_vt8802/sample.docx"
    )
    assert record["source_file_git_status"] == "outside_repo"
    assert "note" not in record


def test_register_with_note(tmp_path: Path) -> None:
    samples_root = tmp_path / "clinical_trial_doc"
    source_file = _write_sample(
        samples_root,
        rel_dir="docx/zh/extract",
        file_name="ib.docx",
        content=b"noted",
    )
    result = register_sample(source_file, samples_root, note="test note", git_root=None)
    assert result.record.get("note") == "test note"


def test_register_skips_existing_hash(tmp_path: Path) -> None:
    samples_root = tmp_path / "clinical_trial_doc"
    source_file = _write_sample(
        samples_root,
        rel_dir="docx/zh/extract",
        file_name="ib.docx",
        content=b"same-bytes",
    )
    first = register_sample(source_file, samples_root, git_root=None)
    second = register_sample(source_file, samples_root, git_root=None)

    assert first.skipped is False
    assert second.skipped is True
    assert second.file_hash == first.file_hash
    # only one index file written
    assert first.index_path.is_file()


def test_register_new_hash_after_content_change(tmp_path: Path) -> None:
    samples_root = tmp_path / "clinical_trial_doc"
    source_file = _write_sample(
        samples_root,
        rel_dir="docx/zh/extract",
        file_name="ib.docx",
        content=b"version-a",
    )
    first = register_sample(source_file, samples_root, git_root=None)

    source_file.write_bytes(b"version-b")
    second = register_sample(source_file, samples_root, git_root=None)

    assert second.skipped is False
    assert second.file_hash != first.file_hash
    # both index files exist, in separate sha256_xxx dirs
    assert first.index_path.is_file()
    assert second.index_path.is_file()
    assert first.index_path != second.index_path


def test_resolve_snapshot_path(tmp_path: Path) -> None:
    samples_root = tmp_path / "clinical_trial_doc"
    source_file = _write_sample(
        samples_root,
        rel_dir="docx/zh/extract",
        file_name="ib.docx",
        content=b"lookup-me",
    )
    result = register_sample(source_file, samples_root, git_root=None)
    resolved = resolve_snapshot_path(result.file_hash, samples_root=samples_root)
    assert resolved == result.snapshot_path


def test_cli_register(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    samples_root = tmp_path / "clinical_trial_doc"
    source_file = _write_sample(
        samples_root,
        rel_dir="docx/zh/extract",
        file_name="ib.docx",
        content=b"cli-register",
    )
    monkeypatch.setattr(register_sample_cli, "DEFAULT_SAMPLES_ROOT", samples_root)
    monkeypatch.setattr(register_sample_cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", [
        "register_sample.py", "register", "--file", str(source_file),
    ])
    assert register_sample_cli.main() == 0

    # per-snapshot index written inside sha256_xxx/
    result_hash = compute_file_hash(source_file)
    idx = snapshot_index_abs_path(
        file_hash=result_hash,
        source_rel_path="docx/zh/extract/ib.docx",
        samples_root=samples_root,
    )
    assert idx.is_file()


def test_extract_run_summary_includes_file_hash() -> None:
    from runtime.run_summaries import build_extract_run_summary_dict

    class _Bundle:
        doc_id = "doc_test"
        file_name = "ib.docx"
        file_hash = "sha256:abc123"
        source_type = "docx"
        document_meta = {}

    summary = build_extract_run_summary_dict(
        run_id="extract_test",
        bundle=_Bundle(),
        export_slices=False,
        source_docx=Path("samples/docx/zh/extract/ib.docx"),
        git_root=BACKEND_ROOT,
    )
    assert summary["file_hash"] == "sha256:abc123"
