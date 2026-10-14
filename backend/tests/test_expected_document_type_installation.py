"""Tests for installed expected-document-type bindings and validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.capabilities import (
    INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
)
from application.clinical_trial_doc_consistency_qc.expected_document_type_installation import (
    CLINICAL_TRIAL_DOCUMENT_TYPES,
    ClinicalTrialDocumentType,
    validate_expected_document_type_installation,
)
from application.document_consistency_qc import (
    validate_capability_slot_bindings,
)


def test_clinical_document_type_vocabulary_owned_by_installation() -> None:
    assert CLINICAL_TRIAL_DOCUMENT_TYPES == frozenset({"IB", "CSR", "DSUR"})
    assert ClinicalTrialDocumentType.__args__ == ("IB", "CSR", "DSUR")  # type: ignore[attr-defined]


def test_installed_expected_document_type_matrix() -> None:
    expected = {
        ("internal_dsur", "source"): "DSUR",
        ("internal_ib", "source"): "IB",
        ("internal_csr", "source"): "CSR",
        ("dsur_updated_ib", "source_a"): "DSUR",
        ("dsur_updated_ib", "source_b"): "IB",
    }
    assert dict(INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS) == expected


def test_composition_carries_expected_document_type_bindings() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    assert (
        composition.expected_document_type_bindings
        is INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS
    )
    assert composition.expected_document_type_bindings[("dsur_updated_ib", "source_a")] == "DSUR"
    assert composition.expected_document_type_bindings[("dsur_updated_ib", "source_b")] == "IB"


def test_binding_validation_requires_expected_document_type_bindings() -> None:
    capabilities = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
    complete_expected = dict(INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS)

    validate_capability_slot_bindings(
        capabilities=capabilities,
        extract_bindings=INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS,
        prepare_analysis_bindings=INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
        filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
        expected_document_type_bindings=complete_expected,
    )

    missing = dict(complete_expected)
    missing.pop(("internal_dsur", "source"))
    with pytest.raises(ValueError, match="missing expected document-type binding"):
        validate_capability_slot_bindings(
            capabilities=capabilities,
            extract_bindings=INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS,
            prepare_analysis_bindings=INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
            filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
            expected_document_type_bindings=missing,
        )


def test_binding_validation_rejects_orphan_expected_document_type_binding() -> None:
    capabilities = INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
    orphan = dict(INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS)
    orphan[("unknown_capability", "source")] = "DSUR"
    with pytest.raises(ValueError, match="unknown capability_id"):
        validate_capability_slot_bindings(
            capabilities=capabilities,
            extract_bindings=INSTALLED_CLINICAL_TRIAL_DOC_EXTRACT_BINDINGS,
            prepare_analysis_bindings=INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
            filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
            expected_document_type_bindings=orphan,
        )


def test_clinical_value_validation_rejects_invalid_expected_document_type() -> None:
    invalid = dict(INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS)
    invalid[("internal_dsur", "source")] = "NOT_A_TYPE"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="invalid document type"):
        validate_expected_document_type_installation(
            expected_document_type_bindings=invalid,
        )


@pytest.mark.parametrize("document_type", ["DSUR", "IB", "CSR"])
def test_clinical_value_validation_accepts_supported_document_types(
    document_type: str,
) -> None:
    validate_expected_document_type_installation(
        expected_document_type_bindings={
            ("internal_dsur", "source"): document_type,
        },
    )
