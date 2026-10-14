"""HTTP-facing errors for Document Consistency QC bridge transport."""

from __future__ import annotations

from pathlib import Path


class DocumentConsistencyQcBridgeError(Exception):
    """Base class for Document Consistency QC bridge errors."""

    status_code: int = 400

    def __init__(
        self,
        message: str,
        *,
        task_run_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.task_run_id = task_run_id


class DocumentConsistencyQcBridgeValidationError(DocumentConsistencyQcBridgeError):
    """Raised when request input fails application/canonical validation."""

    status_code = 400


class DocumentConsistencyQcBridgeRuntimeError(DocumentConsistencyQcBridgeError):
    """Raised when bridge transport execution fails unexpectedly."""

    status_code = 500

    def __init__(
        self,
        message: str,
        *,
        task_run_id: str | None = None,
        flow_run_id: str | None = None,
        flow_run_summary_path: Path | None = None,
    ) -> None:
        super().__init__(message, task_run_id=task_run_id)
        self.flow_run_id = flow_run_id
        self.flow_run_summary_path = flow_run_summary_path


class ResultNotFoundError(DocumentConsistencyQcBridgeError):
    """Raised when a persisted Result read target cannot be located."""

    status_code = 404


def map_result_read_error(exc: Exception) -> DocumentConsistencyQcBridgeError:
    from application.clinical_trial_doc_consistency_qc.result_read import (
        ResultReadNotFoundError,
        ResultReadUnsupportedCapabilityError,
        ResultReadUnsupportedComparisonModeError,
        ResultReadValidationError,
    )

    message = str(exc)
    if isinstance(exc, ResultReadNotFoundError):
        return ResultNotFoundError(message)
    if isinstance(
        exc,
        (
            ResultReadValidationError,
            ResultReadUnsupportedCapabilityError,
            ResultReadUnsupportedComparisonModeError,
        ),
    ):
        return DocumentConsistencyQcBridgeValidationError(message)
    return DocumentConsistencyQcBridgeRuntimeError(message)


def map_source_annotation_error(exc: Exception) -> DocumentConsistencyQcBridgeError:
    from application.document_consistency_qc.source_annotation import (
        SourceAnnotationConflictError,
        SourceAnnotationNotFoundError,
        SourceAnnotationPersistenceError,
        SourceAnnotationUnknownAnnotationError,
        SourceAnnotationValidationError,
    )

    message = str(exc)
    if isinstance(exc, SourceAnnotationNotFoundError):
        return ResultNotFoundError(message)
    if isinstance(
        exc,
        (
            SourceAnnotationConflictError,
            SourceAnnotationValidationError,
            SourceAnnotationUnknownAnnotationError,
        ),
    ):
        return DocumentConsistencyQcBridgeValidationError(message)
    if isinstance(exc, SourceAnnotationPersistenceError):
        return DocumentConsistencyQcBridgeRuntimeError(message)
    return DocumentConsistencyQcBridgeRuntimeError(message)


def map_task_run_read_error(exc: Exception) -> DocumentConsistencyQcBridgeError:
    from task.clinical_trial_doc_qc.task_run_read import (
        TaskRunPageReadNotFoundError,
        TaskRunPageReadUnknownTaskIdError,
    )

    message = str(exc)
    if isinstance(exc, TaskRunPageReadNotFoundError):
        return ResultNotFoundError(message)
    if isinstance(exc, TaskRunPageReadUnknownTaskIdError):
        return DocumentConsistencyQcBridgeValidationError(message)
    return DocumentConsistencyQcBridgeRuntimeError(message)


def map_finding_review_error(exc: Exception) -> DocumentConsistencyQcBridgeError:
    from application.clinical_trial_doc_consistency_qc.finding_review import (
        FindingReviewFlowNotReadableError,
        FindingReviewNotFoundError,
        FindingReviewUnknownFindingError,
        FindingReviewValidationError,
    )
    from application.document_consistency_qc.finding_review import (
        FindingReviewPersistenceError,
    )

    message = str(exc)
    if isinstance(exc, FindingReviewNotFoundError):
        return ResultNotFoundError(message)
    if isinstance(
        exc,
        (
            FindingReviewValidationError,
            FindingReviewUnknownFindingError,
            FindingReviewFlowNotReadableError,
        ),
    ):
        return DocumentConsistencyQcBridgeValidationError(message)
    if isinstance(exc, FindingReviewPersistenceError):
        return DocumentConsistencyQcBridgeRuntimeError(message)
    return DocumentConsistencyQcBridgeRuntimeError(message)


__all__ = [
    "DocumentConsistencyQcBridgeError",
    "DocumentConsistencyQcBridgeRuntimeError",
    "DocumentConsistencyQcBridgeValidationError",
    "ResultNotFoundError",
    "map_finding_review_error",
    "map_result_read_error",
    "map_source_annotation_error",
    "map_task_run_read_error",
]
