"""QcReportPresentation → PDF bytes. No readers or business projection."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from html import escape
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate

from application.qc_report.presentation_model import (
    CommentPresentation,
    EvidencePresentation,
    IntegrityNotice,
    QcReportPresentation,
    RevisionPresentation,
    ScopeItemPresentation,
    SourcePresentation,
)
from .styles import FONT, MUTED, RULE, report_styles

BEIJING_TIMEZONE = timezone(timedelta(hours=8))


class _ReportLayout:
    """Build splittable flowables; never keep an entire Finding together."""

    def __init__(self):
        self.styles = report_styles()
        self.story = []

    def text(self, value: str, style: str = "body") -> None:
        # Uploaded content is text, never ReportLab's XML markup.
        markup = (
            escape(value)
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\n", "<br/>")
        )
        self.story.append(Paragraph(markup, self.styles[style]))

    def notice(self, notice: IntegrityNotice | None) -> None:
        if notice is not None:
            self.text(notice.display, "caption")
            for limitation in notice.limitations:
                self.text(limitation, "detail")

    def scopes(self, items: Sequence[ScopeItemPresentation]) -> None:
        for item in items:
            self.text(f"· {item.display}", "scope")

    def source(self, source: SourcePresentation) -> None:
        self.text(f"文件：{source.document.original_file_name}", "source_detail")
        self.text(f"位置：{source.location_display}", "source_detail")
        self.text("原文", "caption")
        self.text(source.original_sentence_text, "evidence")

    def reviews(
        self,
        revisions: Sequence[RevisionPresentation],
        comments: Sequence[CommentPresentation],
        revised_sentence: str | None,
        conflict_notice: str | None,
    ) -> None:
        if conflict_notice:
            self.text(conflict_notice, "detail")
        if revised_sentence is not None:
            self.text("修订后", "caption")
            self.text(revised_sentence, "revision")
        for revision in revisions:
            self.text(
                f"修订记录：{revision.selected_original_text} → {revision.replacement_text}",
                "detail",
            )
        for comment in comments:
            self.text("批注", "caption")
            if comment.selected_original_text:
                self.text(f"选中文字：{comment.selected_original_text}", "detail")
            self.text(f"内容：{comment.content}", "detail")

    def evidence(self, item: EvidencePresentation, number: int) -> None:
        self.text(f"证据 {number}", "caption")
        self.source(item.source)
        self.reviews(
            item.revisions,
            item.comments,
            item.revised_sentence_text,
            item.revision_conflict_notice,
        )


def _time_display(value: str) -> str:
    """Display the same instant in fixed UTC+8, never the host timezone."""
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    offset = timestamp.utcoffset()
    if offset is None:
        return value  # Preserve absence of timezone; never invent one.
    return timestamp.astimezone(BEIJING_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def render_qc_report_pdf(presentation: QcReportPresentation) -> bytes:
    """Render the transient typed model to an A4 PDF, without persistence."""
    if not isinstance(presentation, QcReportPresentation):
        raise TypeError("presentation must be QcReportPresentation")
    layout = _ReportLayout()
    header = presentation.report_header
    layout.text(header.title, "title")
    layout.text(f"任务：{header.task.display_name}")
    for document in header.documents:
        layout.text(f"原始文件：{document.original_file_name}", "detail")
        document_type = (
            document.expected_document_type or document.observed_document_type
        )
        if document_type:
            layout.text(f"文档类型：{document_type}", "detail")
    layout.text(f"报告生成时间：{_time_display(header.generated_at)}", "detail")
    layout.text("时间均为北京时间（UTC+8）", "detail")

    layout.text("本次核查内容与范围", "section")
    for contribution in presentation.scope_summary.contributions:
        layout.text(contribution.function_display.display_name, "caption")
        for domain in contribution.content_domains:
            layout.text(domain.display_name)
            layout.notice(domain.integrity_notice)
        if contribution.execution.created_at:
            layout.text(
                f"核查开始时间：{_time_display(contribution.execution.created_at)}",
                "detail",
            )
        if contribution.execution.completed_at:
            layout.text(
                f"核查完成时间：{_time_display(contribution.execution.completed_at)}",
                "detail",
            )
        configuration = contribution.configuration_summary
        layout.text(configuration.display, "caption")
        layout.scopes(configuration.effective_scope_items)
        layout.notice(contribution.integrity_notice)

    layout.text("核查结果概览", "section")
    summary = presentation.result_summary
    layout.text(f"问题总数：{summary.finding_count}")
    for count in summary.finding_counts:
        layout.text(f"{count.display_name}：{count.count}")
    layout.notice(summary.integrity_notice)

    if presentation.finding_sections:
        layout.story.append(PageBreak())
        layout.text("详细核查结果", "section")
        for finding in presentation.finding_sections:
            layout.story.append(
                HRFlowable(width="100%", color=RULE, thickness=0.5, spaceBefore=6)
            )
            layout.text(
                f"{finding.sequence_display}  |  {finding.label_display}", "finding"
            )
            layout.text("结论", "caption")
            layout.text(finding.conclusion)
            review = finding.review_display
            if review is not None:
                if review.decision_display:
                    layout.text(f"审阅：{review.decision_display}", "detail")
                if review.marked_display:
                    layout.text(f"标记：{review.marked_display}", "detail")
                if review.note:
                    layout.text(f"笔记：{review.note}", "detail")
            for number, evidence in enumerate(finding.evidence_items, 1):
                layout.evidence(evidence, number)

    if presentation.independent_review_records:
        layout.text("其他审阅记录", "section")
        for number, record in enumerate(presentation.independent_review_records, 1):
            layout.text(f"审阅记录 {number}", "caption")
            layout.source(record.source)
            layout.reviews(
                (record.revision,) if record.revision else (),
                (record.comment,) if record.comment else (),
                record.revised_sentence_text,
                record.revision_conflict_notice,
            )

    if presentation.configuration_appendix:
        layout.text("附录：核查配置", "section")
        for appendix in presentation.configuration_appendix:
            layout.text(appendix.function_display.display_name, "caption")
            if appendix.persisted_decision_at:
                layout.text(
                    f"配置保存时间：{_time_display(appendix.persisted_decision_at)}",
                    "detail",
                )
            for number, selection in enumerate(appendix.selections, 1):
                layout.text(f"配置 {number}：{selection.display}", "caption")
                layout.text(f"文件：{selection.document.original_file_name}", "detail")
                for caption, items in (
                    ("默认推荐范围", selection.automatic_scope_items),
                    ("最终核查范围", selection.effective_scope_items),
                    ("新增范围", selection.added_scope_items),
                    ("移除范围", selection.removed_scope_items),
                ):
                    if items:
                        layout.text(caption, "caption")
                        layout.scopes(items)

    if presentation.report_notes:
        layout.text("报告说明", "section")
        for note in presentation.report_notes:
            layout.text(note, "detail")

    def page_decoration(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc.leftMargin, A4[1] - 25, header.title)
        canvas.setStrokeColor(RULE)
        canvas.line(doc.leftMargin, A4[1] - 32, A4[0] - doc.rightMargin, A4[1] - 32)
        canvas.drawCentredString(A4[0] / 2, 23, f"第 {doc.page} 页")
        canvas.restoreState()

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=48,
        rightMargin=48,
        topMargin=45,
        bottomMargin=42,
        title=header.title,
        subject=header.task.display_name,
        author="",
        pageCompression=1,
    )
    document.build(
        layout.story, onFirstPage=page_decoration, onLaterPages=page_decoration
    )
    return output.getvalue()
