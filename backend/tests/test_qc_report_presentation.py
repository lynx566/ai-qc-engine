"""Renderer-facing behavior over validated report facts, without persistence."""

from __future__ import annotations

# ruff: noqa: E402

from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict
from importlib import import_module
from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.qc_report import build_qc_report
from tests.test_qc_report_artifact import (
    _annotation,
    _available_configuration_selection,
    _document,
    _evidence,
    _finding,
    _report,
)


@pytest.fixture
def project():
    return import_module(
        "application.qc_report.presentation"
    ).build_qc_report_presentation


def payload(*, text="共有 24 例（70.0%）试验参与者发生 ADR。", annotations=()):
    source = _report()
    source["source_evidence"][0]["original_sentence_text"] = text
    source["source_evidence"][0]["heading_path"] = ["18.整体安全性评估"]
    source["source_annotations"] = list(annotations)
    source["source_evidence"][0]["annotation_refs"] = [
        a["annotation_ref"] for a in annotations
    ]
    return source


def edit(ref, text, start, end, replacement, *, independent=False):
    a = _annotation(ref=ref, block="C0008" if independent else "C0002")
    a.update(
        original_sentence_text=text,
        selected_original_text=text[start:end],
        range={"start_offset": start, "end_offset": end},
        replacement_text=replacement,
        related_finding_refs=[] if independent else ["f1"],
        heading_path=["20.结论"] if independent else ["18.整体安全性评估"],
    )
    return a


def comment(ref, text, *, ranged=False, independent=False):
    a = _annotation("comment", ref=ref, block="C0008" if independent else "C0002")
    a.update(
        original_sentence_text=text,
        selected_original_text=text[1:3] if ranged else text,
        related_finding_refs=[] if independent else ["f1"],
        content="请核实此处数据。",
        heading_path=["20.结论"] if independent else ["18.整体安全性评估"],
    )
    if ranged:
        a["range"] = {"start_offset": 1, "end_offset": 3}
    return a


def present(project, source):
    return project(build_qc_report(**source))


@pytest.mark.parametrize(
    "task_id,shared_name,report_name",
    [
        ("internal_dsur_qc", "研发期间安全性更新报告（DSUR）", "DSUR质控"),
        ("internal_ib_qc", "研究者手册（IB）", "IB质控"),
        ("internal_csr_qc", "临床研究报告（CSR）", "CSR质控"),
        ("dsur_updated_ib_qc", "DSUR↔IB", "DSUR↔IB文件间质控"),
    ],
)
def test_report_task_vocabulary_uses_identity_not_shared_display(
    project, task_id, shared_name, report_name
):
    source = payload()
    source["task"].update(task_id=task_id, display_name=shared_name)
    source["contributions"][0]["function_display"] = {
        "name": "Writing Accuracy & Consistency",
        "description": "撰写准确性与一致性核查",
    }
    source["contributions"][0]["content_domains"][0]["display_name"] = "临床安全性"
    before = deepcopy(source)
    p = present(project, source)
    assert p.report_header.title == "质控审查报告"
    assert p.report_header.task.display_name == report_name
    assert p.report_header.task.metadata.task_id == task_id
    assert (
        p.scope_summary.contributions[0].function_display.display_name
        == "撰写准确性与一致性核查"
    )
    assert (
        p.scope_summary.contributions[0].content_domains[0].display_name == "临床安全性"
    )
    assert source == before
    # Negative fixture: stale shared display must never become report body copy.
    source["task"]["display_name"] = "内部一致性核查"
    assert present(project, source).report_header.task.display_name == report_name


def test_unknown_report_task_identity_fails_closed(project):
    source = payload()
    source["task"].update(task_id="unknown_task", display_name="旧产品标题")
    with pytest.raises(ValueError, match="unsupported QC report task identity"):
        present(project, source)


def test_header_counts_and_default_pending_are_renderer_ready(project):
    p = present(project, payload())
    assert p.report_header.title == "质控审查报告"
    assert p.report_header.task.display_name == "DSUR质控"
    assert p.report_header.generated_at == "2026-10-10T00:02:00Z"
    assert p.report_header.documents[0].original_file_name == "source.docx"
    assert p.report_header.documents[0].expected_document_type == "DSUR"
    assert p.result_summary.finding_count == 1
    assert (
        p.result_summary.finding_counts[0].count,
        p.result_summary.finding_counts[1].count,
    ) == (1, 0)
    assert p.result_summary.integrity_status == "complete"
    assert p.result_summary.integrity_notice is None
    f = p.finding_sections[0]
    assert (f.sequence_number, f.sequence_display, f.label_display) == (
        1,
        "问题 01",
        "存在错误",
    )
    assert f.review_display is None
    assert p.independent_review_records == ()
    assert len(p.report_notes) == 2


def test_label_partition_is_stable_and_has_continuous_numbers(project):
    s = payload()
    s["findings"] = [
        {**_finding(f"f{i}", f"L00{i}"), "label": label}
        for i, label in [
            (1, "need_review"),
            (2, "fail"),
            (3, "need_review"),
            (4, "fail"),
        ]
    ]
    s["contributions"][0]["content_domains"][0]["finding_refs"] = [
        "f1",
        "f2",
        "f3",
        "f4",
    ]
    p = present(project, s)
    assert [f.metadata.finding_id for f in p.finding_sections] == [
        "L002",
        "L004",
        "L001",
        "L003",
    ]
    assert [f.sequence_display for f in p.finding_sections] == [
        "问题 01",
        "问题 02",
        "问题 03",
        "问题 04",
    ]
    assert [f.label_display for f in p.finding_sections] == [
        "存在错误",
        "存在错误",
        "可能有误",
        "可能有误",
    ]
    assert (
        p.result_summary.finding_counts[0].count,
        p.result_summary.finding_counts[1].count,
    ) == (2, 2)


def test_cross_section_and_shared_evidence_keep_reference_order_and_identity(project):
    text = "A😀B。"
    a = edit("a1", text, 1, 2, "XY")
    a["related_finding_refs"] = ["f1", "f2"]
    s = payload(text=text, annotations=[a])
    s["source_evidence"].append(_evidence("e2", "C0008"))
    s["source_evidence"][1]["heading_path"] = ["20.结论"]
    s["findings"] = [_finding(evidence_refs=["e2", "e1"]), _finding("f2", "L002")]
    s["contributions"][0]["content_domains"][0]["finding_refs"] = ["f1", "f2"]
    r = build_qc_report(**s)
    before = deepcopy(r)
    p = project(r)
    first, second = p.finding_sections
    assert [e.source.location_display for e in first.evidence_items] == [
        "20.结论",
        "18.整体安全性评估",
    ]
    assert first.evidence_items[1] == second.evidence_items[0]
    assert first.evidence_items[1].revisions[0].metadata.annotation_id == "ann_a1"
    assert r == before


@pytest.mark.parametrize(
    "decision,marked,note,updated,display",
    [
        ("confirmed", False, None, "2026-10-10T00:01:00Z", "已确认"),
        ("ignored", False, None, "2026-10-10T00:01:00Z", "已忽略"),
        ("pending", True, "核实中", "2026-10-10T00:01:00Z", None),
        ("pending", False, None, "2026-10-10T00:01:00Z", None),
    ],
)
def test_review_actions_have_secondary_information_without_pending_badge(
    project, decision, marked, note, updated, display
):
    s = payload()
    s["findings"][0]["review_disposition"] = dict(
        decision=decision, marked=marked, note=note, updated_at=updated
    )
    review = present(project, s).finding_sections[0].review_display
    assert review.decision_display == display
    assert review.marked_display == ("已标记" if marked else None)
    assert review.note == note
    assert review.updated_at == updated


def test_detached_immutable_deterministic_model_and_no_file_reads(project, monkeypatch):
    s = payload(text="A😀B。", annotations=[edit("a1", "A😀B。", 1, 2, "XY")])
    s["source_evidence"][0]["table_context"] = {"rows": [["值", "24"]]}
    r = build_qc_report(**s)
    before = deepcopy(r)

    def no_read(*args, **kwargs):
        raise AssertionError("D1 must not read files")

    monkeypatch.setattr("builtins.open", no_read)
    p = project(r)
    assert p == project(deepcopy(r))
    assert r == before
    r["source_evidence"][0]["heading_path"].append("changed")
    r["source_evidence"][0]["table_context"]["rows"][0][0] = "changed"
    e = p.finding_sections[0].evidence_items[0]
    assert e.source.heading_path == ("18.整体安全性评估",)
    assert e.source.table_context.rows == (("值", "24"),)
    with pytest.raises(FrozenInstanceError):
        p.report_header.title = "changed"


@pytest.mark.parametrize(
    "text,ranges,want",
    [
        (
            "共有 24 例（70.0%）试验参与者发生 ADR。",
            [(8, 13, "80.0%")],
            "共有 24 例（80.0%）试验参与者发生 ADR。",
        ),
        ("A😀B。", [(1, 2, "XY"), (2, 3, "Z")], "AXYZ。"),
        ("abcdef", [(4, 6, "!"), (0, 2, "AB")], "ABcd!"),
        ("abcdef", [(0, 6, "完整修订")], "完整修订"),
    ],
)
def test_revision_reconstructs_whole_sentence_using_original_codepoint_offsets(
    project, text, ranges, want
):
    anns = [
        edit(f"a{i}", text, start, end, replacement)
        for i, (start, end, replacement) in enumerate(ranges)
    ]
    e = (
        present(project, payload(text=text, annotations=anns))
        .finding_sections[0]
        .evidence_items[0]
    )
    assert e.revised_sentence_text == want
    assert e.revision_conflict is False
    assert [r.selected_original_text for r in e.revisions] == [
        text[a:b] for a, b, _ in ranges
    ]
    assert [r.replacement_text for r in e.revisions] == [v for _, _, v in ranges]


@pytest.mark.parametrize(
    "ranges", [[(0, 3), (2, 4)], [(0, 4), (1, 2)], [(1, 3), (1, 3)]]
)
def test_conflicting_edits_keep_individual_revisions_and_integrity(project, ranges):
    anns = [
        edit(f"a{i}", "abcdef", start, end, "X")
        for i, (start, end) in enumerate(ranges)
    ]
    p = present(project, payload(text="abcdef", annotations=anns))
    e = p.finding_sections[0].evidence_items[0]
    assert e.revised_sentence_text is None
    assert e.revision_conflict is True
    assert e.revision_conflict_notice
    assert len(e.revisions) == 2
    assert p.result_summary.integrity_status == "complete"


def test_invalid_selected_slice_is_rejected_before_reconstruction(project):
    s = payload(text="A😀B。", annotations=[edit("a1", "A😀B。", 1, 2, "XY")])
    r = build_qc_report(**s)
    r["source_annotations"][0]["selected_original_text"] = "wrong"
    with pytest.raises(ValueError, match="selected_original_text"):
        project(r)


def test_empty_replacement_remains_invalid_under_current_annotation_contract(project):
    s = payload(text="A😀B。", annotations=[edit("a1", "A😀B。", 1, 2, "XY")])
    r = build_qc_report(**s)
    r["source_annotations"][0]["replacement_text"] = ""
    with pytest.raises(ValueError, match="replacement_text"):
        project(r)


def test_comments_keep_source_order_and_highlights_are_not_report_items(project):
    text = "A😀B。"
    highlight = _annotation("highlight", ref="a2")
    highlight["heading_path"] = ["18.整体安全性评估"]
    s = payload(
        text=text,
        annotations=[comment("a1", text, ranged=True), highlight, comment("a3", text)],
    )
    e = present(project, s).finding_sections[0].evidence_items[0]
    assert [c.selected_original_text for c in e.comments] == ["😀B", text]
    assert [c.metadata.annotation_ref for c in e.comments] == ["a1", "a3"]
    assert e.revisions == ()
    assert e.revised_sentence_text is None
    assert not e.revision_conflict


def selection(job="job", *, adjusted=False, doc="d1", slot="source"):
    return _available_configuration_selection(
        document_ref=doc,
        slot_id=slot,
        filter_job_id=job,
        automatic_anchor_block_ids=["C0001", "C0003"],
        effective_anchor_block_ids=["C0001", "C0004"]
        if adjusted
        else ["C0001", "C0003"],
        added_anchor_block_ids=["C0004"] if adjusted else [],
        removed_anchor_block_ids=["C0003"] if adjusted else [],
        headings={
            "C0001": ["执行概要"],
            "C0003": ["18.整体安全性评估"],
            "C0004": ["20.结论"],
        },
        orders={"C0001": 0, "C0003": 18, "C0004": 20},
    )


def configure(s, selections):
    s["contributions"][0]["configuration"] = dict(
        availability="available",
        persisted_decision_at="2026-10-10T00:00:00Z",
        selections=selections,
    )


def test_single_job_summary_sorts_but_appendix_keeps_selection_order(project):
    s = payload()
    row = selection()
    for kind in ("automatic", "effective"):
        row[f"{kind}_anchor_block_ids"].reverse()
        row[f"{kind}_scope_items"].reverse()
    configure(s, [row])
    p = present(project, s)
    assert [
        item.display
        for item in p.scope_summary.contributions[
            0
        ].configuration_summary.effective_scope_items
    ] == ["执行概要", "18.整体安全性评估"]
    assert [
        item.display
        for item in p.configuration_appendix[0].selections[0].effective_scope_items
    ] == ["18.整体安全性评估", "执行概要"]


def test_multi_job_summary_uses_doc_order_and_preserves_all_appendix_facts(project):
    s = payload()
    rows = [selection("late", adjusted=True), selection("early")]
    for row in rows:
        for kind in ("automatic", "effective", "added", "removed"):
            row[f"{kind}_anchor_block_ids"].reverse()
            row[f"{kind}_scope_items"].reverse()
    configure(s, rows)
    p = present(project, s)
    assert [
        item.display
        for item in p.scope_summary.contributions[
            0
        ].configuration_summary.effective_scope_items
    ] == ["执行概要", "18.整体安全性评估", "20.结论"]
    assert [
        [item.metadata.anchor_block_id for item in getattr(row, f"{kind}_scope_items")]
        for row in p.configuration_appendix[0].selections
        for kind in ("automatic", "effective", "added", "removed")
    ] == [
        raw[f"{kind}_anchor_block_ids"]
        for raw in rows
        for kind in ("automatic", "effective", "added", "removed")
    ]


def test_conflicting_heading_order_across_jobs_fails_closed(project):
    s = payload()
    rows = [selection("first"), selection("second")]
    for kind in ("automatic", "effective"):
        rows[1][f"{kind}_scope_items"][0]["doc_order_index"] = 999
    configure(s, rows)
    with pytest.raises(ValueError, match="conflicting.*doc_order_index"):
        present(project, s)


def test_removed_heading_order_conflict_is_not_hidden_by_effective_summary(project):
    s = payload()
    row = selection(adjusted=True)
    row["removed_scope_items"][0]["doc_order_index"] = 999
    configure(s, [row])
    with pytest.raises(ValueError, match="conflicting.*doc_order_index"):
        present(project, s)


def test_summary_counts_are_renderer_ready_and_sum_to_total(project):
    s = payload()
    s["findings"] = [
        {**_finding(f"f{i}", f"L{i:03d}"), "label": "need_review" if i <= 6 else "fail"}
        for i in range(1, 19)
    ]
    s["contributions"][0]["content_domains"][0]["finding_refs"] = [
        f["finding_ref"] for f in s["findings"]
    ]
    p = present(project, s)
    assert [
        (item.label, item.display_name, item.count)
        for item in p.result_summary.finding_counts
    ] == [("fail", "存在错误", 12), ("need_review", "可能有误", 6)]
    assert [
        f"{item.display_name}: {item.count}" for item in p.result_summary.finding_counts
    ] == ["存在错误: 12", "可能有误: 6"]
    assert p.result_summary.finding_count == sum(
        item.count for item in p.result_summary.finding_counts
    )
    assert [f.sequence_number for f in p.finding_sections] == list(range(1, 19))


@pytest.mark.parametrize(
    "adjusted,mode,display",
    [(False, "default", "使用默认范围"), (True, "adjusted", "在默认范围基础上调整")],
)
def test_configuration_has_human_scope_and_keeps_delta(
    project, adjusted, mode, display
):
    s = payload()
    configure(s, [selection(adjusted=adjusted)])
    p = present(project, s)
    config = p.scope_summary.contributions[0].configuration_summary
    assert (config.mode, config.display) == (mode, display)
    assert [v.display for v in config.effective_scope_items] == (
        ["执行概要", "20.结论"] if adjusted else ["执行概要", "18.整体安全性评估"]
    )
    assert [v.display for v in config.added_scope_items] == (
        ["20.结论"] if adjusted else []
    )
    assert [v.display for v in config.removed_scope_items] == (
        ["18.整体安全性评估"] if adjusted else []
    )
    assert p.configuration_appendix[0].selections[0].metadata.filter_job_id == "job"


def test_multiple_filter_jobs_deduplicate_display_paths_but_preserve_selections(
    project,
):
    s = payload()
    configure(
        s,
        [selection("dsur_clinical_safety"), selection("dsur_overview", adjusted=True)],
    )
    p = present(project, s)
    config = p.scope_summary.contributions[0].configuration_summary
    assert config.mode == "adjusted"
    assert [v.display for v in config.effective_scope_items] == [
        "执行概要",
        "18.整体安全性评估",
        "20.结论",
    ]
    assert [v.display for v in config.removed_scope_items] == ["18.整体安全性评估"]
    assert len(p.configuration_appendix[0].selections) == 2
    assert len(p.scope_summary.contributions[0].content_domains) == 1


def test_configuration_aggregate_obeys_document_order_without_collapsing_documents(
    project,
):
    s = payload()
    s["documents"].append(_document("d2", "source_b", "doc_two"))
    second = selection("second", doc="d2", slot="source_b")
    for kind in ("automatic", "effective"):
        second[f"{kind}_anchor_block_ids"].reverse()
        second[f"{kind}_scope_items"].reverse()
    configure(s, [second, selection("first")])
    p = present(project, s)
    config = p.scope_summary.contributions[0].configuration_summary
    assert [v.document.metadata.document_ref for v in config.effective_scope_items] == [
        "d1",
        "d1",
        "d2",
        "d2",
    ]
    assert [
        v.metadata.filter_job_id for v in p.configuration_appendix[0].selections
    ] == ["second", "first"]
    assert [v.display for v in config.effective_scope_items] == [
        "执行概要",
        "18.整体安全性评估",
        "执行概要",
        "18.整体安全性评估",
    ]


def test_unavailable_configuration_does_not_invent_scopes_from_coverage(project):
    config = (
        present(project, payload()).scope_summary.contributions[0].configuration_summary
    )
    assert config.mode == "unavailable"
    assert config.effective_scope_items == ()
    assert config.display == "最终核查范围不可用"


@pytest.mark.parametrize(
    "status,notice",
    [
        ("partial", "本报告部分内容不完整"),
        ("failed", "本报告所代表的结果形成失败"),
        ("unavailable", "本报告部分结果不可用"),
    ],
)
def test_integrity_notices_follow_report_integrity(project, status, notice):
    s = payload()
    s["integrity"] = dict(status=status, limitations=["已保存结果未覆盖全部范围。"])
    p = present(project, s)
    assert p.result_summary.integrity_notice.display == notice
    assert p.scope_summary.contributions[0].execution.outcome == "success"
    assert p.result_summary.integrity_notice.limitations == (
        "已保存结果未覆盖全部范围。",
    )


def test_lossless_fallback_keeps_complete_display_despite_partial_execution(project):
    s = payload()
    c = s["contributions"][0]
    c["execution"]["outcome"] = "partial"
    limitation = "部分问题未完成自动合并，已完整保留未合并的问题记录。"
    c["integrity"].update(
        finalization_status="completed_with_fallback",
        fallback_comparison_modes=["scope_local"],
        limitations=[limitation],
    )
    s["integrity"]["limitations"] = [limitation]
    p = present(project, s)
    assert p.result_summary.integrity_status == "complete"
    assert p.result_summary.integrity_notice.display == "报告说明"
    assert p.result_summary.integrity_notice.limitations == (limitation,)
    assert p.scope_summary.contributions[0].execution.outcome == "partial"
    assert "部分完成" not in str(asdict(p.result_summary))
    assert "scope_local" not in str(asdict(p.result_summary))


def test_independent_edits_and_comments_have_source_and_whole_revision(project):
    text = "A😀B。"
    s = payload()
    anns = [
        edit("a1", text, 1, 2, "XY", independent=True),
        comment("a2", text, independent=True),
    ]
    for a in anns:
        a["heading_path"] = ["20.结论"]
    s["source_annotations"] = anns
    s["independent_review_record_refs"] = ["a2", "a1"]
    p = present(project, s)
    first, second = p.independent_review_records
    assert first.source.document.original_file_name == "source.docx"
    assert first.source.location_display == "20.结论"
    assert first.source.original_sentence_text == text
    assert first.comment.content == "请核实此处数据。"
    assert second.revision.replacement_text == "XY"
    assert second.revised_sentence_text == "AXYB。"


def test_independent_record_without_heading_is_rejected(project):
    s = payload()
    s["source_annotations"] = [comment("a1", "A😀B。", independent=True)]
    s["independent_review_record_refs"] = ["a1"]
    s["source_annotations"][0].pop("heading_path", None)
    with pytest.raises(ValueError, match="heading_path"):
        present(project, s)


@pytest.mark.parametrize("overlap,want", [(False, "AXYZ。"), (True, None)])
def test_independent_edits_reconstruct_together_and_preserve_record_order(
    project, overlap, want
):
    text = "A😀B。"
    s = payload()
    s["source_annotations"] = [
        edit("a1", text, 1, 2, "XY", independent=True),
        edit("a2", text, 1 if overlap else 2, 3, "Z", independent=True),
    ]
    s["independent_review_record_refs"] = ["a2", "a1"]
    p = present(project, s)
    assert [
        record.revision.metadata.annotation_ref
        for record in p.independent_review_records
    ] == ["a2", "a1"]
    assert [
        record.revised_sentence_text for record in p.independent_review_records
    ] == [want, want]
    assert all(
        record.revision_conflict == overlap for record in p.independent_review_records
    )


def test_empty_finding_report_has_zero_counts_without_pass_verdict(project):
    s = payload()
    s["findings"] = []
    s["contributions"][0]["content_domains"][0]["finding_refs"] = []
    p = present(project, s)
    assert p.finding_sections == ()
    assert p.result_summary.finding_count == 0
    assert [item.count for item in p.result_summary.finding_counts] == [0, 0]
    assert p.result_summary.integrity_status == "complete"


def test_invalid_graph_is_rejected(project):
    r = build_qc_report(**payload())
    r["findings"][0]["evidence_refs"] = ["missing"]
    with pytest.raises(ValueError, match="dangling"):
        project(r)


def test_representative_task_run_projects_all_18_findings_and_full_revision(
    project, representative_qc_task_run
):
    from task.clinical_trial_doc_qc.report_read import load_qc_report
    from task.clinical_trial_doc_qc.task_run_read import load_task_run_page_context

    project_root, task_run_id = representative_qc_task_run
    r = load_qc_report(project_root=project_root, task_run_id=task_run_id)
    before = deepcopy(r)
    p = project(r)
    assert (
        load_task_run_page_context(
            project_root=project_root, task_run_id=task_run_id
        ).display_name
        == "研发期间安全性更新报告（DSUR）"
    )
    assert p.report_header.title == "质控审查报告"
    assert p.report_header.task.display_name == "DSUR质控"
    assert (
        p.scope_summary.contributions[0].function_display.display_name
        == "撰写准确性与一致性核查"
    )
    assert [
        d.display_name for d in p.scope_summary.contributions[0].content_domains
    ] == ["临床安全性"]
    assert p.result_summary.finding_count == 18
    assert [
        (item.display_name, item.count) for item in p.result_summary.finding_counts
    ] == [("存在错误", 12), ("可能有误", 6)]
    assert p.result_summary.finding_count == sum(
        item.count for item in p.result_summary.finding_counts
    )
    assert p.report_header.generated_at == r["generated_at"]
    assert (p.report_header.task.created_at, p.report_header.task.updated_at) == (
        r["task"]["created_at"],
        r["task"]["updated_at"],
    )
    execution = p.scope_summary.contributions[0].execution
    assert (execution.created_at, execution.completed_at) == (
        r["contributions"][0]["execution"]["created_at"],
        r["contributions"][0]["execution"]["completed_at"],
    )
    assert len(p.finding_sections) == 18
    revised = [
        e
        for f in p.finding_sections
        for e in f.evidence_items
        if any(
            v.selected_original_text == "70.0%" and v.replacement_text == "80.0%"
            for v in e.revisions
        )
    ]
    assert revised
    assert all(
        e.revised_sentence_text
        == e.source.original_sentence_text.replace("70.0%", "80.0%")
        for e in revised
    )
    config = p.scope_summary.contributions[0].configuration_summary
    assert config.mode == "default"
    assert len(config.effective_scope_items) == 14
    assert [item.display for item in config.effective_scope_items] == [
        "执行概要",
        "1.前言",
        "3.报告周期内因安全性原因而采取的措施",
        "4.安全性参考信息变更",
        "7.行列表和汇总表中的数据",
        "8.报告期内临床试验中有意义的发现",
        "9.非干预性研究的安全性结果",
        "10.其他临床试验/研究的安全性信息",
        "11.上市后的安全性发现",
        "16.区域特有信息",
        "17.最新信息",
        "18.整体安全性评估",
        "19.重要风险总结",
        "20.结论",
    ]
    assert r == before
