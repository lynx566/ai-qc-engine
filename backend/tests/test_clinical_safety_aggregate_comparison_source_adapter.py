"""Clinical-safety source adaptation into canonical Aggregate Comparison input."""

from __future__ import annotations

import copy
import importlib
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    build_aggregate_evidence_source_bundle,
)


def _scope(*, sentence_text: str = "Retained sentence") -> dict:
    return {
        "scope_id": "HS0007",
        "scope_order": 4,
        "heading_path": ["Safety", "Adverse events"],
        "units": [
            {
                "unit_id": "TU0021",
                "unit_order": 0,
                "text": "Producer-only aggregate unit text",
                "source": {"block_ids": ["B-1"]},
                "sentences": [
                    {
                        "sentence_id": "C0021:S003",
                        "sentence_order": 0,
                        "text": sentence_text,
                        "source_block_ids": ["B-1"],
                    }
                ],
            }
        ],
    }


def _bundle(*, scopes: list[dict] | None = None) -> dict:
    return build_aggregate_evidence_source_bundle(
        doc_id="doc-7",
        file_hash="sha256:clinical",
        document_type="csr",
        heading_scopes=scopes if scopes is not None else [_scope()],
    )


def _adapt(source_bundle: dict):
    module = importlib.import_module(
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.source_adapter"
    )
    return module.adapt_clinical_safety_aggregate_source_bundle(source_bundle)


def test_valid_clinical_bundle_projects_only_canonical_participant_evidence() -> None:
    source_bundle = _bundle()

    evidence = _adapt(source_bundle)

    assert (
        evidence.source_provenance.source_artifact_id
        == source_bundle["aggregate_evidence_source_bundle_id"]
    )
    assert evidence.source_provenance.doc_id == "doc-7"
    assert evidence.source_provenance.file_hash == "sha256:clinical"
    scope = evidence.scopes[0]
    assert scope.source_scope_id == "HS0007"
    assert scope.semantic_path == ("Safety", "Adverse events")
    assert scope.units[0].source_unit_id == "TU0021"
    assert scope.units[0].sentences[0].source_sentence_id == "C0021:S003"
    assert scope.units[0].sentences[0].text == "Retained sentence"

    canonical_values = repr(asdict(evidence))
    for producer_only_field in (
        "artifact_type",
        "schema_version",
        "document_context",
        "document_type",
        "scope_order",
        "unit_order",
        "sentence_order",
        "source_block_ids",
        "block_ids",
        "Producer-only aggregate unit text",
    ):
        assert producer_only_field not in canonical_values


def test_adapter_reuses_the_formal_clinical_source_validator() -> None:
    invalid = _bundle()
    invalid["schema_version"] = "invalid"

    with pytest.raises(ValueError, match="schema_version"):
        _adapt(invalid)


def test_valid_producer_bundle_with_no_scopes_is_not_comparison_eligible() -> None:
    source_bundle = _bundle(scopes=[])

    with pytest.raises(ValueError, match="comparison-eligible scopes"):
        _adapt(source_bundle)


def test_valid_producer_sentence_with_empty_text_is_not_comparison_eligible() -> None:
    source_bundle = _bundle()
    source_bundle["heading_scopes"][0]["units"][0]["sentences"][0]["text"] = ""
    # Rebuild the bundle ID so the producer artifact remains formally valid.
    rebuilt = build_aggregate_evidence_source_bundle(
        doc_id=source_bundle["doc_id"],
        file_hash=source_bundle["file_hash"],
        document_type=source_bundle["document_context"]["document_type"],
        heading_scopes=copy.deepcopy(source_bundle["heading_scopes"]),
    )

    with pytest.raises(ValueError, match="comparison-eligible sentence text"):
        _adapt(rebuilt)
