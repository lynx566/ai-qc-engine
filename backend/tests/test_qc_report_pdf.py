"""PDF boundary behavior, typography safety and real report acceptance."""

from __future__ import annotations

# ruff: noqa: E402

import ast
from dataclasses import replace
from importlib import import_module
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import re

import pytest
from pypdf import PdfReader

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from application.qc_report.presentation import build_qc_report_presentation
from application.qc_report.presentation_model import (
    FindingCount,
    IntegrityNotice,
    ReviewDisplay,
)
from artifacts.qc_report import build_qc_report
from tests.qc_report_representative_fixture import REPRESENTATIVE_TASK_RUN_ID
from tests.test_qc_report_presentation import comment, edit, payload, selection


@pytest.fixture
def render():
    return import_module("renderers.qc_report.pdf").render_qc_report_pdf


def presentation(*, source=None):
    source = payload() if source is None else source
    source["contributions"][0]["function_display"] = {
        "name": "Writing Accuracy & Consistency",
        "description": "撰写准确性与一致性核查",
    }
    source["contributions"][0]["content_domains"][0]["display_name"] = "临床安全性"
    return build_qc_report_presentation(build_qc_report(**source))


def pdf_text(data):
    reader = PdfReader(BytesIO(data))
    return reader, "\n".join(page.extract_text() for page in reader.pages)


def compact(text):
    return "".join(text.split())


@pytest.mark.parametrize("value", [{}, "task_run_test", Path("preview.json"), None])
def test_accepts_only_typed_presentation(render, value):
    with pytest.raises(TypeError, match="QcReportPresentation"):
        render(value)


def test_pdf_has_a4_metadata_display_fields_notes_and_no_machine_ids(render):
    p = presentation()
    data = render(p)
    assert isinstance(data, bytes) and data.startswith(b"%PDF-")
    reader, text = pdf_text(data)
    assert float(reader.pages[0].mediabox.width) == pytest.approx(595.28, abs=0.1)
    assert float(reader.pages[0].mediabox.height) == pytest.approx(841.89, abs=0.1)
    assert reader.metadata.title == "质控审查报告"
    assert reader.metadata.subject == "DSUR质控"
    for term in [
        "质控审查报告",
        "DSUR质控",
        "source.docx",
        "DSUR",
        "撰写准确性与一致性核查",
        "临床安全性",
        "问题 01",
    ]:
        assert compact(term) in compact(text)
    for note in p.report_notes:
        assert compact(note) in compact(text)
    for term in [
        "internal_dsur_qc",
        "clinical_safety",
        "scope_local",
        "focus_comparison",
        "C0002",
        p.report_header.task.metadata.task_run_id,
    ]:
        assert term not in text
    assert "其他审阅记录" not in text
    assert "待处理" not in text and "未审阅" not in text
    for number, page in enumerate(reader.pages, 1):
        assert compact(f"第 {number} 页") in compact(page.extract_text())


def test_labels_and_counts_are_consumed_without_translation_or_recount(render):
    p = presentation()
    p = replace(
        p,
        finding_sections=(
            replace(p.finding_sections[0], label_display="自定义问题标签"),
        ),
        result_summary=replace(
            p.result_summary,
            finding_count=18,
            finding_counts=(
                FindingCount("fail", "自定义错误", 12),
                FindingCount("need_review", "自定义复核", 6),
            ),
        ),
    )
    _, text = pdf_text(render(p))
    for term in ["问题总数：18", "自定义错误：12", "自定义复核：6", "自定义问题标签"]:
        assert compact(term) in compact(text)
    assert text.index("自定义错误") < text.index("自定义复核")
    assert "存在错误" not in text and "可能有误" not in text


def test_scope_and_appendix_use_input_order_without_sorting(render):
    s = payload()
    s["contributions"][0]["configuration"] = {
        "availability": "available",
        "persisted_decision_at": "2026-10-10T00:00:00Z",
        "selections": [selection()],
    }
    p = presentation(source=s)
    contribution = p.scope_summary.contributions[0]
    items = tuple(reversed(contribution.configuration_summary.effective_scope_items))
    p = replace(
        p,
        scope_summary=replace(
            p.scope_summary,
            contributions=(
                replace(
                    contribution,
                    configuration_summary=replace(
                        contribution.configuration_summary, effective_scope_items=items
                    ),
                ),
            ),
        ),
    )
    _, text = pdf_text(render(p))
    body, appendix = text.split("附录：核查配置")
    assert body.index("18.整体安全性评估") < body.index("执行概要")
    assert appendix.index("执行概要") < appendix.index("18.整体安全性评估")
    assert "dsur_clinical_safety" not in text


def test_full_revision_and_comment_remain_with_evidence(render):
    text = "共有 24 例（70.0%）试验参与者发生 ADR。"
    a = edit("a1", text, text.index("70.0%"), text.index("70.0%") + 5, "80.0%")
    c = comment("a2", text)
    p = presentation(source=payload(text=text, annotations=[a, c]))
    _, extracted = pdf_text(render(p))
    for term in [
        text,
        "共有 24 例（80.0%）试验参与者发生 ADR。",
        "修订后",
        "70.0% → 80.0%",
        "请核实此处数据。",
    ]:
        assert compact(term) in compact(extracted)


def test_conflict_notice_and_individual_revisions_are_not_reconstructed(render):
    text = "共有 24 例（70.0%）试验参与者发生 ADR。"
    p = presentation(
        source=payload(
            text=text,
            annotations=[
                edit("a1", text, 0, 5, "版本一"),
                edit("a2", text, 3, 8, "版本二"),
            ],
        )
    )
    _, extracted = pdf_text(render(p))
    notice = p.finding_sections[0].evidence_items[0].revision_conflict_notice
    assert compact(notice) in compact(extracted)
    assert "版本一" in extracted and "版本二" in extracted
    assert "修订后：" not in extracted


@pytest.mark.parametrize(
    "notice",
    [
        None,
        IntegrityNotice("报告说明", ("完整保留全部结果。",)),
        IntegrityNotice("本报告部分内容不完整", ("缺失结果。",)),
    ],
)
def test_integrity_notice_comes_from_presentation(render, notice):
    p = presentation()
    p = replace(p, result_summary=replace(p.result_summary, integrity_notice=notice))
    _, text = pdf_text(render(p))
    if notice:
        assert notice.display in text
        for limitation in notice.limitations:
            assert limitation in text
    else:
        assert "部分完成" not in text and "不完整" not in text


def test_review_uses_display_fields_and_notes(render):
    p = presentation()
    f = replace(
        p.finding_sections[0],
        review_display=ReviewDisplay(
            "confirmed", "已确认", "已标记", "需更正", "2026-10-10T03:00:00Z"
        ),
    )
    _, text = pdf_text(render(replace(p, finding_sections=(f,))))
    for term in ["审阅：已确认", "标记：已标记", "笔记：需更正"]:
        assert compact(term) in compact(text)


def test_independent_review_section_has_location_and_comment(render):
    c = comment("a1", "独立原文。", independent=True)
    s = payload(annotations=[])
    s["source_annotations"] = [c]
    s["independent_review_record_refs"] = ["a1"]
    p = presentation(source=s)
    _, text = pdf_text(render(p))
    assert "其他审阅记录" in text
    assert "20.结论" in text and "独立原文。" in text and "请核实此处数据。" in text


def test_long_finding_filename_heading_and_xml_text_paginate_without_loss(render):
    p = presentation()
    conclusion = (
        "长结论第一个片段<&>。" + "这是需要完整保留的长结论。" * 1200 + "长结论结束。"
    )
    evidence = p.finding_sections[0].evidence_items[0]
    doc = replace(
        evidence.source.document, original_file_name="longfilename" * 50 + ".docx"
    )
    original = "长证据开始。" + "这是需要完整保留的原文证据。" * 900 + "长证据结束。"
    source = replace(
        evidence.source,
        document=doc,
        location_display="长章节路径" * 180,
        original_sentence_text=original,
    )
    f = replace(
        p.finding_sections[0],
        conclusion=conclusion,
        evidence_items=(replace(evidence, source=source),),
    )
    p = replace(
        p,
        report_header=replace(p.report_header, documents=(doc,)),
        finding_sections=(f,),
    )
    reader, text = pdf_text(render(p))
    assert len(reader.pages) > 5
    body = re.sub(r"第\s*\d+\s*页", "", text.replace("质控审查报告", ""))
    assert compact(conclusion) in compact(body)
    assert compact(original) in compact(body)
    assert compact(doc.original_file_name) in compact(text)
    assert "<&>" in text


def test_execution_time_never_uses_task_updated_at(render):
    p = presentation()
    p = replace(
        p,
        report_header=replace(
            p.report_header,
            task=replace(p.report_header.task, updated_at="TASK-UPDATED-SENTINEL"),
        ),
    )
    _, text = pdf_text(render(p))
    assert "TASK-UPDATED-SENTINEL" not in text


def test_production_renderer_imports_without_business_readers():
    # A forbidden transitive import breaks renderer isolation even if AST looks clean.
    code = """
import sys, importlib.abc
sys.path.insert(0, sys.argv[1])
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, name, *args):
        if name in ('task', 'artifacts', 'pypdf', 'pymupdf', 'fitz') or name.startswith(('task.', 'artifacts.', 'application.document_consistency_qc', 'application.qc_report.presentation.', 'pypdf.', 'pymupdf.')):
            raise RuntimeError('forbidden business import: ' + name)
sys.meta_path.insert(0, Guard())
from renderers.qc_report.pdf import render_qc_report_pdf
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(BACKEND_ROOT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    for file in (BACKEND_ROOT / "renderers/qc_report").glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "application."
            ):
                assert node.module == "application.qc_report.presentation_model"


@pytest.fixture(scope="module")
def real_presentation(tmp_path_factory):
    from task.clinical_trial_doc_qc.report_read import load_qc_report
    from tests.qc_report_representative_fixture import install_representative_qc_task_run

    project_root = tmp_path_factory.mktemp("qc_report_representative_pdf")
    task_run_id = install_representative_qc_task_run(project_root)
    return build_qc_report_presentation(
        load_qc_report(project_root=project_root, task_run_id=task_run_id)
    )


def test_real_18_finding_pdf_acceptance(render, real_presentation):
    p = real_presentation
    reader, text = pdf_text(render(p))
    normalized = compact(text)
    for term in [
        "问题总数：18",
        "存在错误：12",
        "可能有误：6",
        "已更正",
        "已确认",
        "已忽略",
        "已标记",
        "70.0% → 80.0%",
    ]:
        assert compact(term) in normalized
    for f in p.finding_sections:
        assert compact(f.sequence_display) in normalized
        assert compact(f.conclusion) in normalized
        for e in f.evidence_items:
            assert compact(e.source.original_sentence_text) in normalized
            if e.revised_sentence_text:
                assert compact(e.revised_sentence_text) in normalized
    summary = text.split("详细核查结果")[0]
    scopes = p.scope_summary.contributions[
        0
    ].configuration_summary.effective_scope_items
    positions = [compact(summary).index(compact(item.display)) for item in scopes]
    assert len(positions) == 14 and positions == sorted(positions)
    assert "其他审阅记录" not in text
    assert "部分完成" not in text
    for term in [
        "internal_dsur_qc",
        "clinical_safety",
        "scope_local",
        "focus_comparison",
        "C0006",
        REPRESENTATIVE_TASK_RUN_ID,
        p.scope_summary.contributions[0].metadata.flow_run_id,
    ]:
        assert term not in text
    assert len(reader.pages) == 14
    assert normalized.count("时间均为北京时间（UTC+8）") == 1
    assert text.count("UTC") == 1
    for expected in [
        "核查开始时间：2026-10-04 18:21:53",
        "核查完成时间：2026-10-04 18:30:04",
        "配置保存时间：2026-10-04 18:21:55",
    ]:
        assert compact(expected) in normalized


def test_real_evidence_header_stays_with_original_sentence_start(
    render, real_presentation
):
    reader, _ = pdf_text(render(real_presentation))
    for page in reader.pages:
        text = page.extract_text()
        for match in re.finditer(r"证据\s+\d+", text):
            following = text[match.end() :]
            assert "原文" in following, "Evidence introduction stranded at page bottom"


def test_cjk_font_is_embedded_and_covers_required_glyphs(render, monkeypatch, tmp_path):
    p = presentation()
    probe = "中文医学 ADR ALT VT8802 24 80.0% Ⅰ Ⅱ ≥ ↔ （），；。"
    p = replace(p, finding_sections=(replace(p.finding_sections[0], conclusion=probe),))
    monkeypatch.chdir(tmp_path)
    reader, text = pdf_text(render(p))
    assert compact(probe) in compact(text)
    embedded = []
    for page in reader.pages:
        for resource in page["/Resources"]["/Font"].values():
            font = resource.get_object()
            if "NotoSansSC" in font.get("/BaseFont", ""):
                assert font["/FontDescriptor"]["/FontFile2"].get_data()
                assert font["/ToUnicode"].get_data()
                embedded.append(font)
    assert embedded, "CJK font must have an embedded TrueType font program"
    from reportlab.pdfbase import pdfmetrics
    from renderers.qc_report.styles import FONT

    face = pdfmetrics.getFont(FONT).face
    assert all(
        face.charToGlyph.get(ord(char), 0) != 0 for char in probe if not char.isspace()
    )


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        ("2026-10-10T09:18:23Z", "2026-10-10 17:18:23"),
        ("2026-10-10T09:18:23.123456+00:00", "2026-10-10 17:18:23"),
        ("2026-10-10T17:18:23+08:00", "2026-10-10 17:18:23"),
        ("2026-10-10T04:18:23-05:00", "2026-10-10 17:18:23"),
        ("2026-10-10T14:48:23+05:30", "2026-10-10 17:18:23"),
    ],
)
def test_timestamp_formatter_converts_instant_to_beijing_time(timestamp, expected):
    from renderers.qc_report.pdf import _time_display

    assert _time_display(timestamp) == expected


def test_pdf_all_visible_times_use_beijing_time_and_correct_facts(render):
    s = payload()
    s["contributions"][0]["configuration"] = {
        "availability": "available",
        "persisted_decision_at": "2026-10-08T22:11:12-05:00",
        "selections": [selection()],
    }
    p = presentation(source=s)
    contribution = p.scope_summary.contributions[0]
    contribution = replace(
        contribution,
        execution=replace(
            contribution.execution,
            created_at="2026-10-09T17:18:23+08:00",
            completed_at="2026-10-09T18:19:24+08:00",
        ),
    )
    p = replace(
        p,
        report_header=replace(
            p.report_header,
            generated_at="2026-10-10T09:18:23Z",
            task=replace(p.report_header.task, updated_at="NOT-COMPLETION"),
        ),
        scope_summary=replace(p.scope_summary, contributions=(contribution,)),
    )
    _, text = pdf_text(render(p))
    for expected in [
        "报告生成时间：2026-10-10 17:18:23",
        "核查开始时间：2026-10-09 17:18:23",
        "核查完成时间：2026-10-09 18:19:24",
        "配置保存时间：2026-10-09 11:11:12",
    ]:
        assert compact(expected) in compact(text)
    assert "NOT-COMPLETION" not in text
    assert compact(text).count("时间均为北京时间（UTC+8）") == 1
    assert text.count("UTC") == 1
    assert "UTC+08:00" not in text and "UTC-05:00" not in text
    assert p.report_header.generated_at == "2026-10-10T09:18:23Z"
    assert p.configuration_appendix[0].persisted_decision_at == "2026-10-08T22:11:12-05:00"


@pytest.mark.parametrize("host_timezone", ["UTC", "America/New_York", "Asia/Tokyo"])
def test_timestamp_conversion_never_uses_system_local_timezone(monkeypatch, host_timezone):
    from datetime import datetime
    from renderers.qc_report import pdf

    class ExplicitTimezoneDatetime(datetime):
        def astimezone(self, tz=None):
            assert tz is not None, "Conversion must never default to host timezone"
            return super().astimezone(tz)

    monkeypatch.setenv("TZ", host_timezone)
    monkeypatch.setattr(pdf, "datetime", ExplicitTimezoneDatetime)
    assert pdf._time_display("2026-10-10T20:18:23Z") == "2026-10-11 04:18:23"
