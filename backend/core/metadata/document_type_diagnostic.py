"""Neutral document-type diagnostic contracts and expected-vs-observed evaluation."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

DocumentTypeDiagnosticStatus = Literal[
    "match",
    "mismatch",
    "uncertain",
]

DocumentTypeDiagnosticReason = Literal[
    "observed_matches_expected",
    "observed_differs_from_expected",
    "observed_unavailable",
    "doc_type_conflict",
]

DOC_TYPE_CONFLICT_WARNING = "doc_type_conflict"


@dataclass(frozen=True, slots=True)
class DocumentTypeDiagnostic:
    status: DocumentTypeDiagnosticStatus
    expected_document_type: str
    reason: DocumentTypeDiagnosticReason


def _normalize_observed_document_type(observed_document_type: str | None) -> str | None:
    if not isinstance(observed_document_type, str):
        return None
    stripped = observed_document_type.strip()
    return stripped or None


def diagnose_document_type(
    *,
    expected_document_type: str,
    observed_document_type: str | None,
    warnings: Collection[str],
    supported_document_types: Collection[str],
) -> DocumentTypeDiagnostic:
    """Compare expected document-type token against observed metadata primitives."""

    observed = _normalize_observed_document_type(observed_document_type)

    if observed is None:
        return DocumentTypeDiagnostic(
            status="uncertain",
            expected_document_type=expected_document_type,
            reason="observed_unavailable",
        )

    if DOC_TYPE_CONFLICT_WARNING in warnings:
        return DocumentTypeDiagnostic(
            status="uncertain",
            expected_document_type=expected_document_type,
            reason="doc_type_conflict",
        )

    if observed not in supported_document_types:
        return DocumentTypeDiagnostic(
            status="uncertain",
            expected_document_type=expected_document_type,
            reason="observed_unavailable",
        )

    if observed == expected_document_type:
        return DocumentTypeDiagnostic(
            status="match",
            expected_document_type=expected_document_type,
            reason="observed_matches_expected",
        )

    return DocumentTypeDiagnostic(
        status="mismatch",
        expected_document_type=expected_document_type,
        reason="observed_differs_from_expected",
    )


__all__ = [
    "DOC_TYPE_CONFLICT_WARNING",
    "DocumentTypeDiagnostic",
    "DocumentTypeDiagnosticReason",
    "DocumentTypeDiagnosticStatus",
    "diagnose_document_type",
]
