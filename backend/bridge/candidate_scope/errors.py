"""Bridge error types mapped to HTTP responses."""

from __future__ import annotations


class CandidateScopeBridgeError(Exception):
    """Base bridge error with HTTP status."""

    status_code: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CandidateScopeValidationError(CandidateScopeBridgeError):
    status_code = 400


class CandidateScopeNotFoundError(CandidateScopeBridgeError):
    status_code = 404


class CandidateScopeRuntimeError(CandidateScopeBridgeError):
    status_code = 500


def map_flow_resume_error(exc: Exception) -> CandidateScopeBridgeError:
    message = str(exc)
    lowered = message.lower()
    if "not found" in lowered or ("missing" in lowered and "flow" in lowered):
        return CandidateScopeNotFoundError(message)
    return CandidateScopeValidationError(message)


def map_document_read_error(exc: Exception) -> CandidateScopeBridgeError:
    from application.document_consistency_qc.document_read import (
        DocumentReadNotFoundError,
        DocumentReadValidationError,
    )

    message = str(exc)
    if isinstance(exc, DocumentReadNotFoundError):
        return CandidateScopeNotFoundError(message)
    if isinstance(exc, DocumentReadValidationError):
        return CandidateScopeValidationError(message)
    return CandidateScopeRuntimeError(message)
