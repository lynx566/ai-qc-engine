"""Integration tests for generic document-type result enrichment."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import (
    build_installed_document_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.expected_document_type_installation import (
    CLINICAL_TRIAL_DOCUMENT_TYPES,
)
from application.document_consistency_qc.document_type_result import (
    build_document_consistency_qc_application_result,
)
from capability import (
    DSUR_UPDATED_IB_CONSISTENCY_QC,
    INTERNAL_DSUR_CONSISTENCY_QC,
)
from execution_flow.document_consistency_qc import (
    DocumentConsistencyQcFlowReport,
    DocumentConsistencyQcFlowResult,
    DocumentConsistencyQcSlotResult,
    FilterJobFlowResult,
)
from runtime.document_source_binding import DocumentIntakeSourceBinding

RESULT_PATH = (
    BACKEND_ROOT
    / "application"
    / "document_consistency_qc"
    / "document_type_result.py"
)


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _doc_meta_report(*, observed: str | None, warnings: list[str] | None = None) -> dict:
    return {
        "output_dir": "/tmp/doc_meta",
        "doc_meta_bundle": {
            "doc_type": {"value": observed, "confidence": "high"},
            "warnings": warnings or [],
        },
        "doc_meta_bundle_path": "/tmp/doc_meta/doc_meta_bundle.json",
        "document_context_preview_path": "/tmp/doc_meta/document_context_preview.json",
        "run_summary_path": "/tmp/doc_meta/run_summary.json",
    }


def _slot_result(
    *,
    slot_id: str,
    observed: str | None,
    warnings: list[str] | None = None,
    filter_job_count: int = 2,
) -> DocumentConsistencyQcSlotResult:
    filter_results = tuple(
        FilterJobFlowResult(
            filter_job_id=f"job_{index}",
            source_language="zh",
            zone_config_name=f"zone_{index}",
            zone_config_version="v0",
            stage_result=SimpleNamespace(output_dir=Path(f"/tmp/filter/{index}")),
        )
        for index in range(filter_job_count)
    )
    return DocumentConsistencyQcSlotResult(
        slot_id=slot_id,
        admitted_source=DocumentIntakeSourceBinding(
            file_hash="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            original_file_name=f"{slot_id}.docx",
            source_path=Path(f"/tmp/{slot_id}.docx"),
        ),
        extract_report=SimpleNamespace(),
        prepare_analysis_report=SimpleNamespace(),
        doc_meta_report=_doc_meta_report(observed=observed, warnings=warnings),
        filter_results=filter_results,
    )


def _flow_report(*, slots: tuple[DocumentConsistencyQcSlotResult, ...]) -> DocumentConsistencyQcFlowReport:
    return DocumentConsistencyQcFlowReport(
        result=DocumentConsistencyQcFlowResult(slots=slots),
        messages=(),
        flow_run_id="document_consistency_qc_test",
        flow_run_summary_path=Path("/tmp/flow_run_summary.json"),
    )


def _build_clinical_application_result(
    *,
    capability_id: str,
    flow_report: DocumentConsistencyQcFlowReport,
):
    composition = build_installed_document_consistency_qc_application_composition()
    return build_document_consistency_qc_application_result(
        capability_id=capability_id,
        flow_report=flow_report,
        expected_document_type_bindings=composition.expected_document_type_bindings,
        supported_document_types=CLINICAL_TRIAL_DOCUMENT_TYPES,
    )


def test_generic_result_enrichment_uses_injected_binding() -> None:
    flow_report = _flow_report(
        slots=(
            _slot_result(slot_id="source", observed="LegalOpinion"),
        )
    )
    enriched = build_document_consistency_qc_application_result(
        capability_id="contract_internal",
        flow_report=flow_report,
        expected_document_type_bindings={
            ("contract_internal", "source"): "Contract",
        },
        supported_document_types={"Contract", "LegalOpinion"},
    )
    diagnostic = enriched.slots[0].document_type_diagnostic
    assert diagnostic.status == "mismatch"
    assert diagnostic.expected_document_type == "Contract"
    assert diagnostic.reason == "observed_differs_from_expected"


def test_internal_capability_slot_diagnostic_mismatch() -> None:
    flow_report = _flow_report(
        slots=(
            _slot_result(slot_id="source", observed="IB"),
        )
    )
    enriched = _build_clinical_application_result(
        capability_id=INTERNAL_DSUR_CONSISTENCY_QC.capability_id,
        flow_report=flow_report,
    )
    assert len(enriched.slots) == 1
    diagnostic = enriched.slots[0].document_type_diagnostic
    assert diagnostic.status == "mismatch"
    assert diagnostic.expected_document_type == "DSUR"
    assert diagnostic.reason == "observed_differs_from_expected"
    assert enriched.slots[0].slot_result.filter_results


def test_cross_file_slots_are_diagnosed_independently() -> None:
    flow_report = _flow_report(
        slots=(
            _slot_result(slot_id="source_a", observed="IB"),
            _slot_result(slot_id="source_b", observed="IB"),
        )
    )
    enriched = _build_clinical_application_result(
        capability_id=DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id,
        flow_report=flow_report,
    )
    source_a, source_b = enriched.slots
    assert source_a.document_type_diagnostic.status == "mismatch"
    assert source_a.document_type_diagnostic.expected_document_type == "DSUR"
    assert source_b.document_type_diagnostic.status == "match"
    assert source_b.document_type_diagnostic.expected_document_type == "IB"


def test_cross_file_conflict_on_one_slot_only() -> None:
    flow_report = _flow_report(
        slots=(
            _slot_result(
                slot_id="source_a",
                observed="DSUR",
                warnings=["doc_type_conflict"],
            ),
            _slot_result(slot_id="source_b", observed="DSUR"),
        )
    )
    enriched = _build_clinical_application_result(
        capability_id=DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id,
        flow_report=flow_report,
    )
    assert enriched.slots[0].document_type_diagnostic.status == "uncertain"
    assert enriched.slots[1].document_type_diagnostic.status == "mismatch"


def test_unsupported_observed_document_type_maps_to_uncertain() -> None:
    flow_report = _flow_report(
        slots=(
            _slot_result(slot_id="source", observed="UNKNOWN"),
        )
    )
    enriched = _build_clinical_application_result(
        capability_id=INTERNAL_DSUR_CONSISTENCY_QC.capability_id,
        flow_report=flow_report,
    )
    diagnostic = enriched.slots[0].document_type_diagnostic
    assert diagnostic.status == "uncertain"
    assert diagnostic.expected_document_type == "DSUR"
    assert diagnostic.reason == "observed_unavailable"


def test_cross_file_unsupported_and_mismatch_cases() -> None:
    flow_report = _flow_report(
        slots=(
            _slot_result(slot_id="source_a", observed="UNKNOWN"),
            _slot_result(slot_id="source_b", observed="DSUR"),
        )
    )
    enriched = _build_clinical_application_result(
        capability_id=DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id,
        flow_report=flow_report,
    )
    assert enriched.slots[0].document_type_diagnostic.status == "uncertain"
    assert enriched.slots[1].document_type_diagnostic.status == "mismatch"
    assert enriched.slots[1].document_type_diagnostic.expected_document_type == "IB"


def test_one_diagnostic_per_slot_not_per_filter_job() -> None:
    flow_report = _flow_report(
        slots=(
            _slot_result(slot_id="source", observed="IB", filter_job_count=2),
        )
    )
    enriched = _build_clinical_application_result(
        capability_id=INTERNAL_DSUR_CONSISTENCY_QC.capability_id,
        flow_report=flow_report,
    )
    diagnostic = enriched.slots[0].document_type_diagnostic
    assert len(enriched.slots[0].slot_result.filter_results) == 2
    assert diagnostic.status == "mismatch"
    assert diagnostic.expected_document_type == "DSUR"


def test_execution_flow_does_not_import_application() -> None:
    flow_dir = BACKEND_ROOT / "execution_flow"
    imported: set[str] = set()
    for path in flow_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        imported.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
    forbidden = sorted(
        module
        for module in imported
        if module == "application" or module.startswith("application.")
    )
    assert forbidden == []


def test_execution_flow_has_no_clinical_document_type_literals() -> None:
    flow_dir = BACKEND_ROOT / "execution_flow"
    source = "\n".join(path.read_text(encoding="utf-8") for path in flow_dir.rglob("*.py"))
    assert "ClinicalTrialDocumentType" not in source
    assert "DocumentTypeDiagnostic" not in source
    assert "doc_type_conflict" not in source
    assert '"DSUR"' not in source
    assert '"IB"' not in source
    assert '"CSR"' not in source


def test_generic_result_module_has_zero_clinical_dependencies() -> None:
    source = RESULT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RESULT_PATH))
    imported = _imported_module_names(tree)

    assert not any(
        module == "application.clinical_trial_doc_consistency_qc"
        or module.startswith("application.clinical_trial_doc_consistency_qc.")
        for module in imported
    )
    for token in (
        "ClinicalTrialDocumentType",
        "CLINICAL_TRIAL_DOCUMENT_TYPES",
        "resolve_expected_document_type",
        '"IB"',
        '"CSR"',
        '"DSUR"',
    ):
        assert token not in source
