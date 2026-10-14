"""Unit tests for generic document-type diagnostic state machine."""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.metadata.document_type_diagnostic import (  # noqa: E402
    DocumentTypeDiagnostic,
    diagnose_document_type,
)

DIAGNOSTIC_PATH = (
    BACKEND_ROOT / "core" / "metadata" / "document_type_diagnostic.py"
)

CLINICAL_SUPPORTED_DOCUMENT_TYPES = frozenset({"IB", "CSR", "DSUR"})
LEGAL_SUPPORTED_DOCUMENT_TYPES = frozenset({"Contract", "LegalOpinion"})


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_document_type_diagnostic_accepts_generic_string_token() -> None:
    diagnostic = DocumentTypeDiagnostic(
        status="match",
        expected_document_type="Contract",
        reason="observed_matches_expected",
    )
    assert diagnostic.expected_document_type == "Contract"


def test_diagnose_document_type_signature_uses_primitive_inputs() -> None:
    signature = inspect.signature(diagnose_document_type)
    assert "observed_document_type" in signature.parameters
    assert "warnings" in signature.parameters
    assert "doc_meta_bundle" not in signature.parameters


@pytest.mark.parametrize(
    ("observed", "expected", "status", "reason"),
    [
        ("DSUR", "DSUR", "match", "observed_matches_expected"),
        ("IB", "DSUR", "mismatch", "observed_differs_from_expected"),
        (None, "DSUR", "uncertain", "observed_unavailable"),
        ("", "DSUR", "uncertain", "observed_unavailable"),
        ("   ", "DSUR", "uncertain", "observed_unavailable"),
        ("UNKNOWN", "DSUR", "uncertain", "observed_unavailable"),
    ],
)
def test_diagnose_document_type_state_machine(
    observed: str | None,
    expected: str,
    status: str,
    reason: str,
) -> None:
    diagnostic = diagnose_document_type(
        expected_document_type=expected,
        observed_document_type=observed,
        warnings=[],
        supported_document_types=CLINICAL_SUPPORTED_DOCUMENT_TYPES,
    )
    assert diagnostic.status == status
    assert diagnostic.expected_document_type == expected
    assert diagnostic.reason == reason


@pytest.mark.parametrize(
    ("observed", "expected", "status", "reason"),
    [
        ("Contract", "Contract", "match", "observed_matches_expected"),
        ("LegalOpinion", "Contract", "mismatch", "observed_differs_from_expected"),
        ("SomethingElse", "Contract", "uncertain", "observed_unavailable"),
        (None, "Contract", "uncertain", "observed_unavailable"),
        ("", "Contract", "uncertain", "observed_unavailable"),
    ],
)
def test_diagnose_document_type_supports_non_clinical_tokens(
    observed: str | None,
    expected: str,
    status: str,
    reason: str,
) -> None:
    diagnostic = diagnose_document_type(
        expected_document_type=expected,
        observed_document_type=observed,
        warnings=[],
        supported_document_types=LEGAL_SUPPORTED_DOCUMENT_TYPES,
    )
    assert diagnostic.status == status
    assert diagnostic.expected_document_type == expected
    assert diagnostic.reason == reason


def test_doc_type_conflict_maps_to_uncertain_not_mismatch() -> None:
    diagnostic = diagnose_document_type(
        expected_document_type="DSUR",
        observed_document_type="IB",
        warnings=["doc_type_conflict"],
        supported_document_types=CLINICAL_SUPPORTED_DOCUMENT_TYPES,
    )
    assert diagnostic.status == "uncertain"
    assert diagnostic.reason == "doc_type_conflict"


def test_doc_type_conflict_maps_to_uncertain_for_non_clinical_tokens() -> None:
    diagnostic = diagnose_document_type(
        expected_document_type="Contract",
        observed_document_type="LegalOpinion",
        warnings=["doc_type_conflict"],
        supported_document_types=LEGAL_SUPPORTED_DOCUMENT_TYPES,
    )
    assert diagnostic.status == "uncertain"
    assert diagnostic.reason == "doc_type_conflict"


def test_doc_type_conflict_maps_to_uncertain_even_when_observed_matches_expected() -> None:
    diagnostic = diagnose_document_type(
        expected_document_type="DSUR",
        observed_document_type="DSUR",
        warnings=["doc_type_conflict"],
        supported_document_types=CLINICAL_SUPPORTED_DOCUMENT_TYPES,
    )
    assert diagnostic.status == "uncertain"
    assert diagnostic.reason == "doc_type_conflict"


def test_supported_vocabulary_controls_usability() -> None:
    observed = "LegalOpinion"

    mismatch = diagnose_document_type(
        expected_document_type="Contract",
        observed_document_type=observed,
        warnings=[],
        supported_document_types=LEGAL_SUPPORTED_DOCUMENT_TYPES,
    )
    uncertain = diagnose_document_type(
        expected_document_type="DSUR",
        observed_document_type=observed,
        warnings=[],
        supported_document_types=CLINICAL_SUPPORTED_DOCUMENT_TYPES,
    )

    assert mismatch.status == "mismatch"
    assert mismatch.reason == "observed_differs_from_expected"
    assert uncertain.status == "uncertain"
    assert uncertain.reason == "observed_unavailable"


def test_malformed_runtime_observed_document_type_maps_to_uncertain() -> None:
    diagnostic = diagnose_document_type(
        expected_document_type="DSUR",
        observed_document_type=123,  # type: ignore[arg-type]
        warnings=[],
        supported_document_types=CLINICAL_SUPPORTED_DOCUMENT_TYPES,
    )
    assert diagnostic.status == "uncertain"
    assert diagnostic.reason == "observed_unavailable"


def test_core_document_type_diagnostic_has_zero_forbidden_dependencies() -> None:
    source = DIAGNOSTIC_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(DIAGNOSTIC_PATH))
    imported = _imported_module_names(tree)

    assert not any(
        module == "application"
        or module.startswith("application.")
        or module == "application.clinical_trial_doc_consistency_qc"
        or module.startswith("application.clinical_trial_doc_consistency_qc.")
        or module == "execution_flow"
        or module.startswith("execution_flow.")
        or module == "plugins.clinical_trial_doc"
        or module.startswith("plugins.clinical_trial_doc.")
        for module in imported
    )
    for token in (
        "doc_meta_bundle",
        "doc_meta_report",
        "ClinicalTrialDocumentType",
        "CLINICAL_TRIAL_DOCUMENT_TYPES",
        '"IB"',
        '"CSR"',
        '"DSUR"',
    ):
        assert token not in source
