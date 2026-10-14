"""Runtime and runner tests for Request File Intake (Step 0B)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.request_file_intake import (
    REQUEST_FILE_INTAKE_RESULT_FILENAME,
    validate_request_file_intake_result,
)
from core.document.doc_identity import compute_content_hash
from steps.request_file_intake import RequestFileIntakeStepResult
from runtime.document_source_binding import DocumentIntakeSourceBinding
from runtime.io import load_json
from runtime.request_file_intake import operations as request_file_intake_operations
from runtime.request_file_intake import run_request_file_intake_operation
from scripts.stage_runners import request_file_intake_runner


def _mock_git_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        request_file_intake_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "test", "git_dirty": False},
    )


def test_runtime_one_valid_file_persists_result(tmp_path: Path) -> None:
    source = tmp_path / "DSUR.docx"
    source.write_bytes(b"doc-content")
    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
        output_dir=tmp_path / "out",
    )
    result = report.result
    assert result.request_file_intake_result_path.is_file()
    assert result.run_summary_path.is_file()
    payload = load_json(result.request_file_intake_result_path)
    validate_request_file_intake_result(payload)
    assert payload["document"]["file_hash"] == compute_content_hash(b"doc-content")
    assert "source_path" not in json.dumps(payload)


def test_runtime_rejects_batch_source_files_argument(tmp_path: Path) -> None:
    first = tmp_path / "a.docx"
    second = tmp_path / "b.docx"
    first.write_bytes(b"alpha")
    second.write_bytes(b"beta")
    with pytest.raises(TypeError, match="source_file"):
        run_request_file_intake_operation(
            project_root=tmp_path,
            source_files=[first, second],
            output_dir=tmp_path / "multi",
        )


def test_runtime_same_bytes_twice_are_independent_invocations(tmp_path: Path) -> None:
    first = tmp_path / "IB.docx"
    second = tmp_path / "IB_copy.docx"
    first.write_bytes(b"same-bytes")
    second.write_bytes(b"same-bytes")
    first_report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=first,
        output_dir=tmp_path / "dup_a",
    )
    second_report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=second,
        output_dir=tmp_path / "dup_b",
    )
    assert first_report.result.request_file_intake_result["document"]["file_hash"] == (
        second_report.result.request_file_intake_result["document"]["file_hash"]
    )
    assert first_report.result.request_file_intake_result["document"]["original_file_name"] == (
        "IB.docx"
    )
    assert second_report.result.request_file_intake_result["document"]["original_file_name"] == (
        "IB_copy.docx"
    )


def test_runtime_missing_file_fails(tmp_path: Path) -> None:
    missing = tmp_path / "missing.docx"
    with pytest.raises(ValueError, match="must be a regular file"):
        run_request_file_intake_operation(
            project_root=tmp_path,
            source_file=missing,
            output_dir=tmp_path / "fail",
        )


def test_runtime_does_not_generate_doc_id(tmp_path: Path) -> None:
    source = tmp_path / "one.docx"
    source.write_bytes(b"x")
    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
        output_dir=tmp_path / "no_doc",
    )
    payload = load_json(report.result.request_file_intake_result_path)
    summary = load_json(report.result.run_summary_path)
    assert "doc_id" not in payload
    assert summary.get("doc_id") is None


def test_runtime_calls_canonical_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "one.docx"
    source.write_bytes(b"canonical-boundary")
    captured: dict[str, object] = {}

    def _fake_step(input_record):
        captured["input"] = input_record
        formal = {
            "artifact_type": "request_file_intake_result",
            "schema_version": "0.2.0",
            "document": {
                "file_hash": "sha256:" + "a" * 64,
                "original_file_name": input_record.original_file_name,
            },
        }
        return RequestFileIntakeStepResult(
            request_file_intake_result=formal,
        )

    monkeypatch.setattr(request_file_intake_operations, "run_request_file_intake_step", _fake_step)
    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
        output_dir=tmp_path / "step_boundary",
    )
    input_record = captured["input"]
    assert input_record.content == b"canonical-boundary"
    assert input_record.original_file_name == "one.docx"
    payload = load_json(report.result.request_file_intake_result_path)
    assert payload["document"]["file_hash"] == "sha256:" + "a" * 64


def test_persisted_result_matches_step_output(tmp_path: Path) -> None:
    source = tmp_path / "roundtrip.docx"
    source.write_bytes(b"roundtrip")
    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
        output_dir=tmp_path / "roundtrip",
    )
    assert (
        load_json(report.result.request_file_intake_result_path)
        == report.result.request_file_intake_result
    )


def test_persisted_artifact_filename(tmp_path: Path) -> None:
    source = tmp_path / "one.docx"
    source.write_bytes(b"x")
    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
        output_dir=tmp_path / "names",
    )
    assert (
        report.result.request_file_intake_result_path.name
        == REQUEST_FILE_INTAKE_RESULT_FILENAME
    )


def test_index_written_when_using_default_layout(tmp_path: Path) -> None:
    source = tmp_path / "one.docx"
    source.write_bytes(b"x")
    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
    )
    assert report.result.index_path is not None
    assert report.result.index_path.is_file()
    index = load_json(report.result.index_path)
    assert index["step"] == "request_file_intake"
    assert index["run_id"] == report.result.run_id
    assert "doc_id" not in index["documents"][0]


def test_runner_single_file_delegates_to_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_git_provenance(monkeypatch)
    source = tmp_path / "runner.docx"
    source.write_bytes(b"runner")
    captured: dict[str, object] = {}

    def _fake_operation(**kwargs):
        captured.update(kwargs)
        out_dir = Path(kwargs["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        result_path = out_dir / REQUEST_FILE_INTAKE_RESULT_FILENAME
        payload = {
            "artifact_type": "request_file_intake_result",
            "schema_version": "0.2.0",
            "document": {
                "file_hash": "sha256:" + "b" * 64,
                "original_file_name": "runner.docx",
            },
        }
        result_path.write_text(json.dumps(payload), encoding="utf-8")
        from runtime.request_file_intake.operations import (
            RequestFileIntakeOperationReport,
            RequestFileIntakeOperationResult,
        )

        operation_result = RequestFileIntakeOperationResult(
            run_id="request_file_intake_test",
            output_dir=out_dir,
            request_file_intake_result=payload,
            source_binding=DocumentIntakeSourceBinding(
                file_hash="sha256:" + "b" * 64,
                original_file_name="runner.docx",
                source_path=source.resolve(),
            ),
            request_file_intake_result_path=result_path,
            run_summary_path=out_dir / "run_summary.json",
            index_path=None,
        )
        return RequestFileIntakeOperationReport(
            result=operation_result,
            messages=("ok",),
        )

    monkeypatch.setattr(
        request_file_intake_runner,
        "run_request_file_intake_operation",
        _fake_operation,
    )
    monkeypatch.setattr(request_file_intake_runner, "PROJECT_ROOT", tmp_path)
    request_file_intake_runner.main(
        ["--file", str(source), "--output-dir", str(tmp_path / "runner_out")]
    )
    assert captured["source_file"] == source.resolve()


def test_runner_rejects_multiple_file_args(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_git_provenance(monkeypatch)
    first = tmp_path / "a.docx"
    second = tmp_path / "b.docx"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    monkeypatch.setattr(request_file_intake_runner, "PROJECT_ROOT", tmp_path)
    with pytest.raises(SystemExit, match="only one --file is supported"):
        request_file_intake_runner.main(
            [
                "--file",
                str(first),
                "--file",
                str(second),
            ]
        )


def test_runner_missing_file_arg_fails() -> None:
    with pytest.raises(SystemExit):
        request_file_intake_runner.parse_args([])


def test_runtime_single_source_binding(tmp_path: Path) -> None:
    source = tmp_path / "one.docx"
    source.write_bytes(b"single")
    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
        output_dir=tmp_path / "bind_one",
    )
    binding = report.result.source_binding
    assert binding.file_hash == compute_content_hash(b"single")
    assert binding.original_file_name == "one.docx"
    assert binding.source_path == source.resolve()


def test_runtime_binding_matches_formal_intake_hash(tmp_path: Path) -> None:
    source = tmp_path / "a.docx"
    source.write_bytes(b"a")
    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
        output_dir=tmp_path / "bind_formal",
    )
    formal_hash = report.result.request_file_intake_result["document"]["file_hash"]
    assert report.result.source_binding.file_hash == formal_hash


def test_runtime_operation_result_exposes_binding(tmp_path: Path) -> None:
    source = tmp_path / "one.docx"
    source.write_bytes(b"x")
    report = run_request_file_intake_operation(
        project_root=tmp_path,
        source_file=source,
        output_dir=tmp_path / "bind_exposed",
    )
    assert isinstance(report.result.source_binding, DocumentIntakeSourceBinding)


def test_runtime_binding_join_failure_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "one.docx"
    source.write_bytes(b"x")

    def _bad_step(_input_record):
        return RequestFileIntakeStepResult(
            request_file_intake_result={
                "artifact_type": "request_file_intake_result",
                "schema_version": "0.2.0",
            },
        )

    monkeypatch.setattr(request_file_intake_operations, "run_request_file_intake_step", _bad_step)
    with pytest.raises(RuntimeError, match="document must be a mapping"):
        run_request_file_intake_operation(
            project_root=tmp_path,
            source_file=source,
            output_dir=tmp_path / "bind_fail",
        )


def test_runtime_source_binding_module_boundary() -> None:
    binding_source = Path(
        __import__("runtime.document_source_binding", fromlist=["__file__"]).__file__
    ).read_text(encoding="utf-8")
    operations_source = Path(request_file_intake_operations.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "consistency_qc",
        "mode_selection",
        "extract_docx",
        "run_extract",
    ):
        assert forbidden not in binding_source
        assert forbidden not in operations_source
