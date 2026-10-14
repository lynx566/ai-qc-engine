"""Pure report application qc_report → renderer-ready presentation projection.

No report loading, persistence, graph dedup, source resolution or integrity
aggregation. D2 only lays out this model; machine metadata is not body copy.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from artifacts.qc_report import validate_qc_report
from application.qc_report.configuration_presentation import (
    project_configuration,
    validate_configuration_scope_orders,
)
from application.qc_report.revision_presentation import (
    project_sentence_reviews,
)
from application.qc_report.presentation_model import (
    BlockContextPresentation,
    ConfigurationAppendix,
    ContentDomainMetadata,
    ContentDomainPresentation,
    ContributionMetadata,
    ContributionPresentation,
    DocumentMetadata,
    DocumentPresentation,
    EvidencePresentation,
    ExecutionMetadata,
    FindingMetadata,
    FindingSection,
    FunctionDisplay,
    IndependentReviewRecordPresentation,
    IntegrityMetadata,
    IntegrityNotice,
    FindingCount,
    QcReportPresentation,
    ReportHeader,
    ReportMetadata,
    ResultSummary,
    ReviewDisplay,
    ScopeSummary,
    SourceAnchorMetadata,
    SourceMetadata,
    SourcePresentation,
    TableContextPresentation,
    TaskMetadata,
    TaskPresentation,
)

REPORT_TITLE = "质控审查报告"
# Report-only vocabulary keyed by facts already carried in qc_report. Never
# consult the shared Task/capability display registries or persisted previews.
REPORT_TASK_DISPLAY_BY_ID = MappingProxyType(
    {
        "internal_dsur_qc": "DSUR质控",
        "internal_ib_qc": "IB质控",
        "internal_csr_qc": "CSR质控",
        "dsur_updated_ib_qc": "DSUR↔IB文件间质控",
    }
)
REPORT_NOTES = (
    "本报告记录生成时已保存的质控发现、原文证据、修订、批注及审阅状态。",
    "本报告不会修改或替代上传的受控原文档；最终内容维护仍应在原受控文档中完成。",
)
LABEL_DISPLAYS = {"fail": "存在错误", "need_review": "可能有误"}
INTEGRITY_DISPLAYS = {
    "complete": "报告说明",
    "partial": "本报告部分内容不完整",
    "failed": "本报告所代表的结果形成失败",
    "unavailable": "本报告部分结果不可用",
}
REVIEW_DISPLAYS = {"pending": None, "confirmed": "已确认", "ignored": "已忽略"}


def _integrity_notice(state: Mapping[str, Any]) -> IntegrityNotice | None:
    if state["status"] == "complete" and not state["limitations"]:
        return None
    return IntegrityNotice(
        INTEGRITY_DISPLAYS[state["status"]], tuple(state["limitations"])
    )


def _integrity_metadata(state: Mapping[str, Any]) -> IntegrityMetadata:
    return IntegrityMetadata(
        state.get("finalization_status"),
        tuple(state.get("fallback_comparison_modes", ())),
    )


def _review_display(finding: Mapping[str, Any]) -> ReviewDisplay | None:
    review = finding.get("review_disposition")
    if review is None or (
        review["decision"] == "pending"
        and not review["marked"]
        and review["note"] is None
        and review["updated_at"] is None
    ):
        return None
    return ReviewDisplay(
        review["decision"],
        REVIEW_DISPLAYS[review["decision"]],
        "已标记" if review["marked"] else None,
        review["note"],
        review["updated_at"],
    )


def _source(
    record: Mapping[str, Any], documents: Mapping[str, DocumentPresentation]
) -> SourcePresentation:
    headings = tuple(record["heading_path"])
    block = record.get("block_context")
    table = record.get("table_context")
    anchor = record["anchor"]
    return SourcePresentation(
        documents[record["document_ref"]],
        headings,
        " > ".join(headings),
        record["original_sentence_text"],
        BlockContextPresentation(block["kind"], block.get("original_block_text"))
        if block
        else None,
        TableContextPresentation(tuple(tuple(row) for row in table["rows"]))
        if table
        else None,
        SourceMetadata(
            record["contribution_ref"],
            SourceAnchorMetadata(
                *(
                    anchor[key]
                    for key in ("slot_id", "doc_id", "block_id", "sentence_id")
                )
            ),
            record.get("evidence_ref"),
            record.get("doc_order_index"),
        ),
    )


def _annotation_identity(annotation: Mapping[str, Any]) -> tuple[str, ...]:
    anchor = annotation["anchor"]
    return (
        annotation["contribution_ref"],
        annotation["document_ref"],
        *(anchor[key] for key in ("slot_id", "doc_id", "block_id", "sentence_id")),
    )


def build_qc_report_presentation(report: Mapping[str, object]) -> QcReportPresentation:
    """Validate and detach current report facts into immutable display values.

    Stable label partition changes only display sequence. All graph and source
    identities remain those of the input. Task display uses report-only vocabulary;
    unsupported identities fail closed. No clock, registry lookup or file I/O.
    """
    validate_qc_report(report)
    validate_configuration_scope_orders(
        [contribution["configuration"] for contribution in report["contributions"]]
    )
    task = report["task"]
    try:
        task_display_name = REPORT_TASK_DISPLAY_BY_ID[task["task_id"]]
    except KeyError as exc:
        raise ValueError(
            f"unsupported QC report task identity: {task['task_id']!r}"
        ) from exc
    documents = tuple(
        DocumentPresentation(
            document["original_file_name"],
            document["expected_document_type"],
            document["observed_document_type"],
            DocumentMetadata(
                document["document_ref"], document["doc_id"], document["file_hash"]
            ),
        )
        for document in report["documents"]
    )
    by_document = {document.metadata.document_ref: document for document in documents}
    annotations = {
        annotation["annotation_ref"]: annotation
        for annotation in report["source_annotations"]
    }
    evidence = {}
    for record in report["source_evidence"]:
        review = project_sentence_reviews(
            record["original_sentence_text"],
            [annotations[ref] for ref in record["annotation_refs"]],
        )
        evidence[record["evidence_ref"]] = EvidencePresentation(
            _source(record, by_document),
            review.revisions,
            review.comments,
            review.revised_sentence_text,
            review.revision_conflict,
            review.revision_conflict_notice,
        )
    sections = []
    # Explicit partition preserves product-final order inside each label.
    ordered_findings = [
        finding
        for label in ("fail", "need_review")
        for finding in report["findings"]
        if finding["label"] == label
    ]
    for number, finding in enumerate(ordered_findings, start=1):
        owner = finding["owner_context"]
        sections.append(
            FindingSection(
                number,
                f"问题 {number:02d}",
                finding["label"],
                LABEL_DISPLAYS[finding["label"]],
                finding["conclusion"],
                _review_display(finding),
                tuple(evidence[ref] for ref in finding["evidence_refs"]),
                FindingMetadata(
                    finding["finding_ref"],
                    finding["finding_id"],
                    owner["contribution_ref"],
                    owner["semantic_module_id"],
                    finding.get("comparison_mode_id"),
                    tuple(finding.get("source_finding_ids", ())),
                ),
            )
        )
    contributions, appendix = [], []
    for contribution in report["contributions"]:
        display = contribution["function_display"]
        function = FunctionDisplay(
            display["name"],
            display.get("description"),
            display.get("description", display["name"]),
        )
        metadata = ContributionMetadata(
            *(
                contribution[key]
                for key in (
                    "contribution_ref",
                    "flow_id",
                    "flow_run_id",
                    "capability_id",
                )
            )
        )
        config = contribution["configuration"]
        summary, selections = project_configuration(config, documents)
        execution = contribution["execution"]
        contributions.append(
            ContributionPresentation(
                function,
                tuple(
                    ContentDomainPresentation(
                        domain["display_name"],
                        domain["integrity"]["status"],
                        _integrity_notice(domain["integrity"]),
                        ContentDomainMetadata(domain["semantic_module_id"]),
                        _integrity_metadata(domain["integrity"]),
                    )
                    for domain in contribution["content_domains"]
                ),
                summary,
                contribution["integrity"]["status"],
                _integrity_notice(contribution["integrity"]),
                ExecutionMetadata(
                    execution["outcome"],
                    execution["created_at"],
                    execution["completed_at"],
                ),
                metadata,
                _integrity_metadata(contribution["integrity"]),
            )
        )
        appendix.append(
            ConfigurationAppendix(
                function,
                config["availability"],
                config["persisted_decision_at"],
                selections,
                metadata,
            )
        )
    independent_by_source: dict[tuple[str, ...], list[Mapping[str, Any]]] = {}
    for ref in report["independent_review_record_refs"]:
        record = annotations[ref]
        independent_by_source.setdefault(_annotation_identity(record), []).append(
            record
        )
    independent = []
    for ref in report["independent_review_record_refs"]:
        record = annotations[ref]
        review = project_sentence_reviews(
            record["original_sentence_text"],
            independent_by_source[_annotation_identity(record)],
        )
        revision = next(
            (r for r in review.revisions if r.metadata.annotation_ref == ref), None
        )
        comment = next(
            (c for c in review.comments if c.metadata.annotation_ref == ref), None
        )
        independent.append(
            IndependentReviewRecordPresentation(
                _source(record, by_document),
                revision,
                comment,
                review.revised_sentence_text,
                review.revision_conflict,
                review.revision_conflict_notice,
            )
        )
    return QcReportPresentation(
        ReportHeader(
            REPORT_TITLE,
            report["generated_at"],
            TaskPresentation(
                task_display_name,
                task["created_at"],
                task["updated_at"],
                TaskMetadata(task["task_run_id"], task["task_id"]),
            ),
            documents,
            ReportMetadata(report["report_id"]),
        ),
        ScopeSummary(tuple(contributions)),
        ResultSummary(
            len(ordered_findings),
            tuple(
                FindingCount(
                    label,
                    LABEL_DISPLAYS[label],
                    sum(finding["label"] == label for finding in ordered_findings),
                )
                for label in ("fail", "need_review")
            ),
            report["integrity"]["status"],
            _integrity_notice(report["integrity"]),
        ),
        tuple(sections),
        tuple(independent),
        tuple(appendix),
        REPORT_NOTES,
    )
