"""Generic Application result enrichment for Document Consistency QC."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from core.metadata.document_type_diagnostic import (
    DocumentTypeDiagnostic,
    diagnose_document_type,
)
from execution_flow.document_consistency_qc import (
    DocumentConsistencyQcFlowReport,
    DocumentConsistencyQcSlotResult,
)


@dataclass(frozen=True, slots=True)
class DocumentConsistencyQcApplicationSlotResult:
    slot_result: DocumentConsistencyQcSlotResult
    document_type_diagnostic: DocumentTypeDiagnostic


@dataclass(frozen=True, slots=True)
class DocumentConsistencyQcApplicationResult:
    flow_report: DocumentConsistencyQcFlowReport
    slots: tuple[DocumentConsistencyQcApplicationSlotResult, ...]


def _lookup_expected_document_type(
    *,
    capability_id: str,
    slot_id: str,
    expected_document_type_bindings: Mapping[tuple[str, str], str],
) -> str:
    key = (capability_id, slot_id)
    try:
        return expected_document_type_bindings[key]
    except KeyError as exc:
        raise ValueError(
            "missing expected document-type binding for capability slot "
            f"({capability_id!r}, {slot_id!r})"
        ) from exc


def _observed_document_type_from_doc_meta_bundle(
    doc_meta_bundle: Mapping[str, Any],
) -> str | None:
    doc_type = doc_meta_bundle.get("doc_type")
    if not isinstance(doc_type, Mapping):
        return None
    value = doc_type.get("value")
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _warnings_from_doc_meta_bundle(doc_meta_bundle: Mapping[str, Any]) -> list[str]:
    warnings = doc_meta_bundle.get("warnings")
    if not isinstance(warnings, list):
        return []
    return [warning for warning in warnings if isinstance(warning, str)]


def diagnose_document_type_bundle(
    *,
    expected_document_type: str,
    doc_meta_bundle: Mapping[str, Any],
    supported_document_types: Collection[str],
) -> DocumentTypeDiagnostic:
    """Unpack Application-owned metadata for the existing neutral diagnostic."""
    return diagnose_document_type(
        expected_document_type=expected_document_type,
        observed_document_type=_observed_document_type_from_doc_meta_bundle(
            doc_meta_bundle
        ),
        warnings=_warnings_from_doc_meta_bundle(doc_meta_bundle),
        supported_document_types=supported_document_types,
    )


def build_document_consistency_qc_application_result(
    *,
    capability_id: str,
    flow_report: DocumentConsistencyQcFlowReport,
    expected_document_type_bindings: Mapping[tuple[str, str], str],
    supported_document_types: Collection[str],
) -> DocumentConsistencyQcApplicationResult:
    """Attach per-slot document-type diagnostics to a neutral Flow report."""

    enriched_slots: list[DocumentConsistencyQcApplicationSlotResult] = []
    for slot_result in flow_report.result.slots:
        expected_document_type = _lookup_expected_document_type(
            capability_id=capability_id,
            slot_id=slot_result.slot_id,
            expected_document_type_bindings=expected_document_type_bindings,
        )
        doc_meta_bundle = slot_result.doc_meta_report["doc_meta_bundle"]
        diagnostic = diagnose_document_type_bundle(
            expected_document_type=expected_document_type,
            doc_meta_bundle=doc_meta_bundle,
            supported_document_types=supported_document_types,
        )
        enriched_slots.append(
            DocumentConsistencyQcApplicationSlotResult(
                slot_result=slot_result,
                document_type_diagnostic=diagnostic,
            )
        )

    return DocumentConsistencyQcApplicationResult(
        flow_report=flow_report,
        slots=tuple(enriched_slots),
    )


__all__ = [
    "DocumentConsistencyQcApplicationResult",
    "DocumentConsistencyQcApplicationSlotResult",
    "build_document_consistency_qc_application_result",
    "diagnose_document_type_bundle",
]
