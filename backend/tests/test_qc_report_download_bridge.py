"""On-demand report downloads through the product HTTP boundary."""

from __future__ import annotations

# ruff: noqa: E402

from importlib import import_module
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import sys
from time import perf_counter
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from application.task_run import create_task_run
from application.document_consistency_qc.finding_review import (
    FindingReviewEntryReadModel,
)
from artifacts.finding_review_state import build_finding_review_state_payload
from bridge.clinical_trial_doc_qc.app import create_app
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from runtime.io import load_json, save_json
from task.clinical_trial_doc_qc.report_read import (
    QcReportConsistencyError,
    QcReportReadError,
    QcReportUnavailableError,
    load_qc_report,
)
from task.clinical_trial_doc_qc.task_run_read import TaskRunPageReadUnknownTaskIdError
from tests.test_qc_report_composition import (
    TASK,
    _apply_persisted_partial_execution,
    write_annotations,
    write_fixture,
)


def url(task=TASK):
    return f"/api/clinical-trial-doc-qc/task-runs/{task}/qc-report"


def client_for(root):
    return TestClient(
        create_app(
            bridge_config=DocumentConsistencyQcBridgeConfig(
                default_workspace_root=BACKEND_ROOT,
                project_root=root,
            )
        )
    )


def text(response):
    return "\n".join(
        page.extract_text() for page in PdfReader(BytesIO(response.content)).pages
    )


def compact(value):
    return "".join(value.split())


def filename(response):
    return unquote(
        response.headers["content-disposition"].split("filename*=UTF-8''", 1)[1]
    )


@pytest.fixture
def saved(tmp_path):
    flow, flow_root = write_fixture(tmp_path)
    return tmp_path, flow, flow_root


def test_success_returns_pdf_attachment_from_current_report(saved):
    response = client_for(saved[0]).get(url())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="qc-review-report.pdf";'
    )
    assert filename(response) == "test_质控审查报告.pdf"
    assert TASK not in filename(response) and "internal_dsur" not in filename(response)
    contents = compact(text(response))
    assert "质控审查报告" in contents and "DSUR质控" in contents
    assert "问题01" in contents and "问题02" in contents
    assert "Sharedsource" in contents and "Acrosssections" in contents
    assert response.headers["cache-control"] == "no-store"


def test_cross_origin_client_can_read_download_filename(saved):
    response = client_for(saved[0]).get(
        url(), headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert (
        "content-disposition"
        in response.headers["access-control-expose-headers"].lower()
    )


def test_download_changes_after_persisted_review_and_comment_save(saved):
    root, flow, flow_root = saved
    client = client_for(root)
    first = client.get(url())
    assert first.status_code == 200
    path = flow_root / "finding_review/review_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(
        path,
        build_finding_review_state_payload(
            flow_run_id=flow,
            findings={
                "L001": {
                    "decision": "confirmed",
                    "marked": True,
                    "note": "Saved review delta",
                    "updated_at": "2026-10-10T01:00:00Z",
                },
            },
        ),
    )
    write_annotations(saved, [("ann_download_comment", "C0002", "comment", False)])
    annotation_path = flow_root / "source_annotations/annotations.json"
    annotations = load_json(annotation_path)
    annotations["annotations"]["ann_download_comment"]["content"] = (
        "Saved comment delta"
    )
    save_json(annotation_path, annotations)
    second = client.get(url())
    assert second.status_code == 200
    first_text, second_text = compact(text(first)), compact(text(second))
    assert (
        "Savedreviewdelta" not in first_text and "Savedcommentdelta" not in first_text
    )
    assert "Savedreviewdelta" in second_text and "Savedcommentdelta" in second_text
    assert "已确认" in second_text and "已标记" in second_text
    assert filename(first) == filename(second)


def test_download_reads_no_previews_and_writes_no_files(saved, monkeypatch):
    root = saved[0]
    original_open = Path.open
    reads = []

    def read_only(path, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            raise AssertionError(f"download attempted a write: {path}")
        if (
            any(part in {"renders", "output", ".tmp"} for part in path.parts)
            or "preview" in path.name
        ):
            raise AssertionError(f"download attempted a preview read: {path}")
        reads.append(path)
        return original_open(path, mode, *args, **kwargs)

    before = {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    monkeypatch.setattr(Path, "open", read_only)
    response = client_for(root).get(url())
    assert response.status_code == 200 and reads
    after = {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    assert after == before
    assert (
        not (root / "renders").exists()
        and not (root / "output").exists()
        and not (root / ".tmp").exists()
    )


def test_unknown_task_run_uses_existing_not_found_envelope(tmp_path):
    response = client_for(tmp_path).get(url("task_run_missing"))
    assert response.status_code == 404
    assert response.json()["status"] == "failed" and response.json()["message"]


def test_not_ready_task_does_not_enter_composition(tmp_path, monkeypatch):
    create_task_run(project_root=tmp_path, task_run_id=TASK, task_id="internal_dsur_qc")
    service = import_module("bridge.document_consistency_qc.qc_report_service")
    monkeypatch.setattr(
        service,
        "load_qc_report",
        lambda **kwargs: pytest.fail("not-ready task composed"),
    )
    response = client_for(tmp_path).get(url())
    assert response.status_code == 409 and response.json()["status"] == "failed"


@pytest.mark.parametrize("zero,fallback", [(True, False), (False, True)])
def test_zero_findings_and_lossless_partial_fallback_are_downloadable(
    tmp_path, zero, fallback
):
    _, flow_root = write_fixture(tmp_path, zero=zero, fallback=fallback)
    if fallback:
        _apply_persisted_partial_execution(flow_root)
    report = load_qc_report(project_root=tmp_path, task_run_id=TASK)
    assert report["integrity"]["status"] == "complete"
    if fallback:
        assert report["contributions"][0]["execution"]["outcome"] == "partial"
    response = client_for(tmp_path).get(url())
    assert response.status_code == 200
    assert (
        "0" in text(response) if zero else "Acrosssections" in compact(text(response))
    )


@pytest.mark.parametrize(
    "error,status",
    [
        (QcReportConsistencyError("SECRET C:/private/state traceback"), 409),
        (QcReportUnavailableError("SECRET C:/private/state traceback"), 409),
        (QcReportReadError("SECRET C:/private/state traceback"), 400),
    ],
)
def test_composition_errors_are_sanitized_and_stop_before_rendering(
    saved, monkeypatch, error, status
):
    service = import_module("bridge.document_consistency_qc.qc_report_service")
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise error

    monkeypatch.setattr(service, "load_qc_report", fail)
    monkeypatch.setattr(
        service,
        "build_qc_report_presentation",
        lambda value: pytest.fail("failed report projected"),
    )
    monkeypatch.setattr(
        service,
        "render_qc_report_pdf",
        lambda value: pytest.fail("failed report rendered"),
    )
    response = client_for(saved[0]).get(url())
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    assert response.json()["status"] == "failed" and response.json()["message"]
    assert (
        "SECRET" not in response.text
        and "private" not in response.text
        and "traceback" not in response.text
    )
    assert calls == [{"project_root": saved[0], "task_run_id": TASK}]


@pytest.mark.parametrize(
    "stage", ["build_qc_report_presentation", "render_qc_report_pdf"]
)
def test_unexpected_presentation_or_renderer_failure_is_sanitized(
    saved, monkeypatch, stage
):
    service = import_module("bridge.document_consistency_qc.qc_report_service")

    def fail(value):
        raise RuntimeError("SECRET C:/private/font.ttf traceback")

    monkeypatch.setattr(service, stage, fail)
    if stage == "build_qc_report_presentation":
        monkeypatch.setattr(
            service,
            "render_qc_report_pdf",
            lambda value: pytest.fail("failed presentation rendered"),
        )
    response = client_for(saved[0]).get(url())
    assert response.status_code == 500 and response.json()["status"] == "failed"
    assert not response.content.startswith(b"%PDF-")
    assert (
        "SECRET" not in response.text
        and "private" not in response.text
        and "traceback" not in response.text
    )


def test_actual_persisted_identity_failure_uses_domain_status(saved):
    path = saved[2] / "flow_run_summary.json"
    summary = load_json(path)
    summary["evidence_comparison"]["participants"][0]["semantic_module_id"] = (
        "wrong_module"
    )
    save_json(path, summary)
    response = client_for(saved[0]).get(url())
    assert response.status_code == 400 and response.json()["status"] == "failed"
    assert "wrong_module" not in response.text


def test_actual_invalid_annotation_state_uses_domain_status(saved):
    write_annotations(saved, [("ann_download_comment", "C0002", "comment", False)])
    path = saved[2] / "source_annotations/annotations.json"
    state = load_json(path)
    state["flow_run_id"] = "document_consistency_qc_other"
    save_json(path, state)
    response = client_for(saved[0]).get(url())
    assert response.status_code == 400 and response.json()["status"] == "failed"
    assert "document_consistency_qc_other" not in response.text


def test_existing_unknown_task_access_error_blocks_composition(saved, monkeypatch):
    service = import_module("bridge.document_consistency_qc.qc_report_service")

    def fail(**kwargs):
        raise TaskRunPageReadUnknownTaskIdError("SECRET internal capability")

    monkeypatch.setattr(service, "load_task_run_page_context", fail)
    monkeypatch.setattr(
        service,
        "load_qc_report",
        lambda **kwargs: pytest.fail("unavailable task composed"),
    )
    response = client_for(saved[0]).get(url())
    assert response.status_code == 400 and "SECRET" not in response.text


def test_actual_snapshot_change_returns_retryable_conflict_without_renderer(
    saved, monkeypatch
):
    owner = import_module("task.clinical_trial_doc_qc.report_read")
    service = import_module("bridge.document_consistency_qc.qc_report_service")
    actual = owner.load_finding_review_state
    calls = []

    def changing(**kwargs):
        value = actual(**kwargs)
        calls.append(kwargs)
        return (
            value
            if len(calls) == 1
            else replace(
                value,
                findings=(
                    FindingReviewEntryReadModel(
                        "L001", "confirmed", True, "changed", "2026-10-10T01:00:00Z"
                    ),
                ),
            )
        )

    monkeypatch.setattr(owner, "load_finding_review_state", changing)
    monkeypatch.setattr(
        service,
        "render_qc_report_pdf",
        lambda value: pytest.fail("inconsistent snapshot rendered"),
    )
    response = client_for(saved[0]).get(url())
    # Both states must be individually valid to reach the owner's snapshot check.
    assert response.status_code == 409
    assert response.json()["status"] == "failed"
    assert len(calls) == 2


@pytest.mark.parametrize(
    "cause,status",
    [
        (ValueError("SECRET invalid state"), 400),
        (RuntimeError("SECRET reader bug"), 500),
    ],
)
def test_wrapped_read_errors_preserve_domain_vs_unexpected_category(
    saved, monkeypatch, cause, status
):
    service = import_module("bridge.document_consistency_qc.qc_report_service")

    def fail(**kwargs):
        raise QcReportUnavailableError("SECRET wrapper") from cause

    monkeypatch.setattr(service, "load_qc_report", fail)
    response = client_for(saved[0]).get(url())
    assert response.status_code == status and "SECRET" not in response.text


def test_loads_one_snapshot_per_request(saved, monkeypatch):
    service = import_module("bridge.document_consistency_qc.qc_report_service")
    actual = service.load_qc_report
    calls = []

    def load(**kwargs):
        calls.append(kwargs)
        return actual(**kwargs)

    monkeypatch.setattr(service, "load_qc_report", load)
    response = client_for(saved[0]).get(url())
    assert response.status_code == 200
    assert calls == [{"project_root": saved[0], "task_run_id": TASK}]


@pytest.mark.parametrize(
    "original,expected",
    [
        (
            "艾美妥珠单抗 研发期间安全性更新报告#2_fe_stub.docx",
            "艾美妥珠单抗 研发期间安全性更新报告#2_fe_stub_质控审查报告.pdf",
        ),
        ("Report.doc", "Report_质控审查报告.pdf"),
        ('a/b\\c:d*e?f"g<h>i|j.docx', "a_b_c_d_e_f_g_h_i_j_质控审查报告.pdf"),
        ("原文\r\nInjected: header\x00.docx", "原文Injected_ header_质控审查报告.pdf"),
        ("", "质控审查报告.pdf"),
        (".docx", "质控审查报告.pdf"),
        ("\x00\x01 . ", "质控审查报告.pdf"),
    ],
)
def test_download_filename_is_safe_and_user_facing(original, expected):
    module = import_module("bridge.document_consistency_qc.qc_report_filename")
    assert module.qc_report_download_filename(original) == expected
    header = module.qc_report_content_disposition(original)
    assert header.startswith(
        "attachment; filename=\"qc-review-report.pdf\"; filename*=UTF-8''"
    )
    assert unquote(header.split("filename*=UTF-8''", 1)[1]) == expected
    assert "\r" not in header and "\n" not in header
    header.encode("ascii")


def test_extreme_filename_keeps_report_suffix_and_utf8_length_limit():
    module = import_module("bridge.document_consistency_qc.qc_report_filename")
    value = module.qc_report_download_filename("医" * 1000 + ".docx")
    assert value.endswith("_质控审查报告.pdf")
    assert len(value.encode("utf-8")) <= 240
    assert "医" in value


def test_http_download_integration_records_duration_and_bytes(
    tmp_path, record_property
):
    write_fixture(tmp_path)
    start = perf_counter()
    response = client_for(tmp_path).get(url(TASK))
    elapsed = perf_counter() - start
    assert response.status_code == 200
    reader = PdfReader(BytesIO(response.content))
    contents = compact("\n".join(page.extract_text() for page in reader.pages))
    assert "质控审查报告" in contents and "DSUR质控" in contents
    assert "问题01" in contents and "问题02" in contents
    assert filename(response) == "test_质控审查报告.pdf"
    record_property("elapsed_seconds", round(elapsed, 3))
    record_property("pdf_bytes", len(response.content))
    print(
        f"HTTP export: {elapsed:.3f}s, {len(response.content)} bytes, {len(reader.pages)} pages"
    )
