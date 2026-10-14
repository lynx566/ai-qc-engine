"""Stable aggregate-evidence plugin surface tests."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence import (
    CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.document_type import (
    canonicalize_aggregate_evidence_document_type,
)


@pytest.mark.parametrize(("raw", "expected"), [("IB", "ib"), ("CSR", "csr"), ("DSUR", "dsur")])
def test_document_type_canonicalization_is_plugin_owned(raw: str, expected: str) -> None:
    assert canonicalize_aggregate_evidence_document_type(raw) == expected


def test_document_type_canonicalization_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unsupported aggregate evidence document type"):
        canonicalize_aggregate_evidence_document_type("UNKNOWN")


def test_public_plugin_exports_clinical_safety_semantic_binding() -> None:
    assert (
        CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING.prepare.assessment_profile_ref
        == "clinical_safety_aggregate_heading_scope_assessment_zh"
    )


def test_processor_module_removed() -> None:
    processor_path = (
        BACKEND_ROOT
        / "plugins/clinical_trial_doc/evidence_source_preparation/processor.py"
    )
    assert not processor_path.is_file()


def test_canonical_entry_does_not_import_plugin_at_module_level_for_dispatch() -> None:
    step_path = BACKEND_ROOT / "steps/evidence_source_preparation.py"
    source = step_path.read_text(encoding="utf-8")
    block = source.split("def run_evidence_source_preparation", 1)[1]
    assert "plugins.clinical_trial_doc" not in block
