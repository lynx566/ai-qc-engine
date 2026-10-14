"""Request-time PDF export of one persisted report snapshot; no file output."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from time import perf_counter

from application.clinical_trial_doc_consistency_qc.result_read import (
    ResultReadNotFoundError,
    ResultReadValidationError,
)
from application.document_consistency_qc.document_read import (
    DocumentReadNotFoundError,
    DocumentReadValidationError,
)
from application.document_consistency_qc.finding_review import (
    FindingReviewNotFoundError,
    FindingReviewValidationError,
)
from application.document_consistency_qc.source_annotation import (
    SourceAnnotationNotFoundError,
    SourceAnnotationValidationError,
)
from application.qc_report.presentation import build_qc_report_presentation
from bridge.document_consistency_qc.bridge_runtime import (
    DocumentConsistencyQcBridgeConfig,
)
from bridge.document_consistency_qc.errors import (
    DocumentConsistencyQcBridgeError,
    DocumentConsistencyQcBridgeRuntimeError,
    DocumentConsistencyQcBridgeValidationError,
    map_task_run_read_error,
)
from bridge.document_consistency_qc.qc_report_filename import (
    qc_report_content_disposition,
)
from renderers.qc_report import render_qc_report_pdf
from task.clinical_trial_doc_qc.report_read import (
    QcReportConsistencyError,
    QcReportReadError,
    QcReportUnavailableError,
    load_qc_report,
)
from task.clinical_trial_doc_qc.task_run_read import (
    TaskRunPageReadError,
    load_task_run_page_context,
)

logger = logging.getLogger(__name__)


class QcReportDownloadConflictError(DocumentConsistencyQcBridgeError):
    """Report prerequisites or consistent saved snapshot not yet available."""

    status_code = 409


@dataclass(frozen=True, slots=True)
class QcReportDownload:
    pdf_bytes: bytes
    content_disposition: str


def _unavailable_error(
    exc: QcReportUnavailableError,
) -> DocumentConsistencyQcBridgeError:
    # The composition owner wraps underlying read errors. Preserve their category
    # at transport without querying state again or exposing their raw messages.
    cause = exc.__cause__
    if isinstance(
        cause,
        (
            ResultReadValidationError,
            DocumentReadValidationError,
            FindingReviewValidationError,
            SourceAnnotationValidationError,
            TypeError,
            ValueError,
        ),
    ):
        return DocumentConsistencyQcBridgeValidationError(
            "保存的报告数据不一致，无法生成报告。"
        )
    if cause is None or isinstance(
        cause,
        (
            FileNotFoundError,
            ResultReadNotFoundError,
            DocumentReadNotFoundError,
            FindingReviewNotFoundError,
            SourceAnnotationNotFoundError,
        ),
    ):
        return QcReportDownloadConflictError(
            "报告所需的已保存结果或来源尚不可用，请稍后重试。"
        )
    return DocumentConsistencyQcBridgeRuntimeError("报告生成失败，请稍后重试。")


def _generate(
    *, config: DocumentConsistencyQcBridgeConfig, task_run_id: str
) -> QcReportDownload:
    project_root = config.project_root or config.default_workspace_root
    try:
        context = load_task_run_page_context(
            project_root=project_root, task_run_id=task_run_id
        )
    except TaskRunPageReadError as exc:
        mapped = map_task_run_read_error(exc)
        raise type(mapped)("未找到或无法访问当前核查任务。") from exc
    except (TypeError, ValueError) as exc:
        raise DocumentConsistencyQcBridgeValidationError(
            "核查任务的已保存状态不合法。"
        ) from exc
    if not context.state.result_available:
        raise QcReportDownloadConflictError("核查结果尚未就绪，请稍后重试。")

    try:
        report = load_qc_report(project_root=project_root, task_run_id=task_run_id)
    except QcReportConsistencyError as exc:
        raise QcReportDownloadConflictError(
            "保存状态在读取期间发生变化，请重试下载报告。"
        ) from exc
    except QcReportUnavailableError as exc:
        raise _unavailable_error(exc) from exc
    except QcReportReadError as exc:
        raise DocumentConsistencyQcBridgeValidationError(
            "保存的报告数据不一致，无法生成报告。"
        ) from exc

    try:
        presentation = build_qc_report_presentation(report)
    except (TypeError, ValueError) as exc:
        raise DocumentConsistencyQcBridgeValidationError(
            "保存的报告数据不合法，无法生成报告。"
        ) from exc
    # Presentation and renderer consume this one report; neither rereads live state.
    return QcReportDownload(
        pdf_bytes=render_qc_report_pdf(presentation),
        content_disposition=qc_report_content_disposition(
            presentation.report_header.documents[0].original_file_name,
        ),
    )


def generate_qc_report_download(
    *,
    config: DocumentConsistencyQcBridgeConfig,
    task_run_id: str,
) -> QcReportDownload:
    start = perf_counter()
    try:
        download = _generate(config=config, task_run_id=task_run_id)
    except DocumentConsistencyQcBridgeError as exc:
        logger.warning(
            "QC report download failed task_run_id=%r status=%d elapsed_seconds=%.3f",
            task_run_id,
            exc.status_code,
            perf_counter() - start,
        )
        raise
    except Exception as exc:
        logger.error(
            "QC report download failed task_run_id=%r status=500 elapsed_seconds=%.3f",
            task_run_id,
            perf_counter() - start,
        )
        raise DocumentConsistencyQcBridgeRuntimeError(
            "报告生成失败，请稍后重试。"
        ) from exc
    logger.info(
        "QC report download succeeded task_run_id=%r elapsed_seconds=%.3f pdf_bytes=%d",
        task_run_id,
        perf_counter() - start,
        len(download.pdf_bytes),
    )
    return download
