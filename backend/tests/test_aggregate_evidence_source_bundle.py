"""Aggregate evidence source bundle 0.3.0 contract tests."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_ARTIFACT_TYPE,
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION,
    build_aggregate_evidence_source_bundle,
    validate_aggregate_evidence_source_bundle,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assemble_aggregate_evidence_source_bundle import (
    assemble_aggregate_evidence_source_bundle,
)
from tests.current_aggregate_assemble_test_helpers import (
    build_current_aggregate_assemble_inputs,
)


def _scope(*, text: str = "exact unit text", block_id: str = "B001") -> dict:
    return {
        "scope_id": "HS0001",
        "scope_order": 0,
        "heading_path": ["Safety"],
        "units": [
            {
                "unit_id": "TU0001",
                "unit_order": 0,
                "text": text,
                "source": {"block_ids": [block_id]},
                "sentences": [
                    {
                        "sentence_id": "S0001",
                        "sentence_order": 0,
                        "text": "sentence one",
                        "source_block_ids": [block_id],
                    }
                ],
            }
        ],
    }


def _bundle(*, doc_id: str = "doc_a", file_hash: str = "sha256:file", scopes: list | None = None) -> dict:
    return build_aggregate_evidence_source_bundle(
        doc_id=doc_id,
        file_hash=file_hash,
        document_type="ib",
        heading_scopes=scopes if scopes is not None else [_scope()],
    )


def test_builds_exact_0_2_shape() -> None:
    bundle = _bundle()
    assert bundle["artifact_type"] == AGGREGATE_EVIDENCE_SOURCE_BUNDLE_ARTIFACT_TYPE
    assert bundle["schema_version"] == AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION == "0.3.0"
    assert set(bundle) == {
        "artifact_type", "schema_version", "aggregate_evidence_source_bundle_id",
        "doc_id", "file_hash", "document_context", "heading_scopes",
    }
    assert bundle["document_context"] == {"document_type": "ib"}
    assert set(bundle["heading_scopes"][0]) == {
        "scope_id", "scope_order", "heading_path", "units",
    }
    assert set(bundle["heading_scopes"][0]["units"][0]["source"]) == {"block_ids"}
    validate_aggregate_evidence_source_bundle(bundle)


@pytest.mark.parametrize(
    ("path", "key"),
    [
        ((), "zone_key"),
        (("document_context",), "source_route"),
        (("heading_scopes", 0), "eligibility"),
        (("heading_scopes", 0, "units", 0), "unit_form"),
        (("heading_scopes", 0, "units", 0, "source"), "stage"),
        (("heading_scopes", 0, "units", 0, "sentences", 0), "extra"),
    ],
)
def test_rejects_unknown_keys_at_every_object_level(path: tuple, key: str) -> None:
    bundle = _bundle()
    target: object = bundle
    for segment in path:
        target = target[segment]  # type: ignore[index]
    assert isinstance(target, dict)
    target[key] = "unexpected"
    with pytest.raises(ValueError, match="keys mismatch"):
        validate_aggregate_evidence_source_bundle(bundle)


@pytest.mark.parametrize("field", ["block_ids", "source_block_ids"])
def test_provenance_lists_are_non_empty_non_empty_strings(field: str) -> None:
    bundle = _bundle()
    unit = bundle["heading_scopes"][0]["units"][0]
    target = unit["source"] if field == "block_ids" else unit["sentences"][0]
    target[field] = []
    with pytest.raises(ValueError, match="non-empty string list"):
        validate_aggregate_evidence_source_bundle(bundle)
    target[field] = [""]
    with pytest.raises(ValueError, match="non-empty strings"):
        validate_aggregate_evidence_source_bundle(bundle)


def test_scope_order_may_have_gaps_but_must_increase() -> None:
    first = _scope()
    second = copy.deepcopy(first)
    second.update(scope_id="HS0003", scope_order=2)
    second["units"][0]["unit_id"] = "TU0003"
    assert [scope["scope_order"] for scope in _bundle(scopes=[first, second])["heading_scopes"]] == [0, 2]


def test_content_id_ignores_doc_id_but_tracks_content_and_provenance() -> None:
    base = _bundle(doc_id="extract_run_a")
    assert _bundle(doc_id="extract_run_b")["aggregate_evidence_source_bundle_id"] == base["aggregate_evidence_source_bundle_id"]
    assert _bundle(file_hash="sha256:other")["aggregate_evidence_source_bundle_id"] != base["aggregate_evidence_source_bundle_id"]
    assert _bundle(scopes=[_scope(text="changed")])["aggregate_evidence_source_bundle_id"] != base["aggregate_evidence_source_bundle_id"]
    assert _bundle(scopes=[_scope(block_id="B999")])["aggregate_evidence_source_bundle_id"] != base["aggregate_evidence_source_bundle_id"]
    assert _bundle(scopes=[])["aggregate_evidence_source_bundle_id"] != base["aggregate_evidence_source_bundle_id"]


def test_current_inputs_preserve_evidence_and_gapped_source_order() -> None:
    assessment_input, runtime_context, scope_assessments, eligibility = (
        build_current_aggregate_assemble_inputs()
    )
    result = assemble_aggregate_evidence_source_bundle(
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
        scope_assessments=scope_assessments,
        heading_scope_eligibility=eligibility,
    )
    artifact = result.aggregate_evidence_source_bundle
    assert [scope["scope_id"] for scope in artifact["heading_scopes"]] == [
        "HS0001",
        "HS0003",
    ]
    assert [scope["scope_order"] for scope in artifact["heading_scopes"]] == [0, 2]
    for scope in artifact["heading_scopes"]:
        for unit in scope["units"]:
            provenance = runtime_context["unit_provenance"][unit["unit_id"]]
            assert unit["text"] == provenance["candidate_text"]
            assert unit["source"]["block_ids"] == provenance["source_block_ids"]
            assert all(sentence["source_block_ids"] for sentence in unit["sentences"])
