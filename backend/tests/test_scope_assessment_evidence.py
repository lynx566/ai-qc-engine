"""Tests for Scope assessment evidence (assessment_input 1.1.0, Commit A)."""

# ruff: noqa: RUF059
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import json

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    build_scope_assessment_task_manifest,
    validate_scope_assessment_evidence_cross_artifact,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.llm_input import (
    build_scope_aware_prompt_input,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    ASSESSMENT_INPUT_SCHEMA_VERSION,
    validate_assessment_input,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    build_clinical_safety_aggregate_heading_scope_assessment_zh_messages,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    attach_assessment_evidence_to_heading_scopes,
    build_heading_scopes_from_aggregate_units,
    build_scope_assessment_evidence_text,
    build_scope_candidate_text,
    build_unit_assessment_evidence_text,
    heading_scope_signature,
)
from runtime.io import load_json
from tests.test_assessment_input_compact import (
    _aggregate_unit,
    _compact_assessment_input_from_units,
)


def test_build_scope_candidate_text_single_unit() -> None:
    text = build_scope_candidate_text(
        ordered_unit_ids=["TU0001"],
        unit_candidate_text_by_id={"TU0001": "paragraph one."},
    )
    assert text == "paragraph one."


def test_build_scope_candidate_text_multi_unit_double_newline() -> None:
    text = build_scope_candidate_text(
        ordered_unit_ids=["TU0001", "TU0002"],
        unit_candidate_text_by_id={
            "TU0001": "first paragraph.",
            "TU0002": "second paragraph.",
        },
    )
    assert text == "first paragraph.\n\nsecond paragraph."


def test_build_scope_candidate_text_preserves_internal_newlines() -> None:
    text = build_scope_candidate_text(
        ordered_unit_ids=["TU0001"],
        unit_candidate_text_by_id={"TU0001": "line1\nline2\n\nblock2"},
    )
    assert text == "line1\nline2\n\nblock2"


def test_build_scope_candidate_text_rejects_missing_duplicate_empty() -> None:
    with pytest.raises(ValueError, match="scope_assessment_evidence_missing_unit"):
        build_scope_candidate_text(
            ordered_unit_ids=["TU0001"],
            unit_candidate_text_by_id={},
        )
    with pytest.raises(ValueError, match="scope_assessment_evidence_duplicate_unit"):
        build_scope_candidate_text(
            ordered_unit_ids=["TU0001", "TU0001"],
            unit_candidate_text_by_id={"TU0001": "text"},
        )
    with pytest.raises(ValueError, match="scope_assessment_evidence_empty_unit_text"):
        build_scope_candidate_text(
            ordered_unit_ids=["TU0001"],
            unit_candidate_text_by_id={"TU0001": ""},
        )


def test_assessment_input_schema_requires_evidence_and_rejects_1_0_0() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"]),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    assert assessment_input["schema_version"] == ASSESSMENT_INPUT_SCHEMA_VERSION
    assert (
        assessment_input["assessment_profile_ref"]
        == "clinical_safety_aggregate_heading_scope_assessment_zh"
    )
    assert "tag_profile_ref" not in assessment_input
    validate_assessment_input(assessment_input)

    legacy = copy.deepcopy(assessment_input)
    legacy["schema_version"] = "1.0.0"
    with pytest.raises(ValueError, match="unsupported assessment_input schema_version"):
        validate_assessment_input(legacy)

    missing_evidence = copy.deepcopy(assessment_input)
    del missing_evidence["heading_scopes"][0]["assessment_evidence"]
    with pytest.raises(ValueError, match="assessment_evidence"):
        validate_assessment_input(missing_evidence)

    extra_field = copy.deepcopy(assessment_input)
    extra_field["heading_scopes"][0]["assessment_evidence"]["extra"] = "x"
    with pytest.raises(ValueError, match="forbidden fields"):
        validate_assessment_input(extra_field)


def test_cross_artifact_validation_rejects_mismatch_and_tampering() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["A"],
            context_block_ids=["C0010"],
            sentences=[
                {
                    "sentence_id": "S0001",
                    "text": "alpha",
                    "source_block_id": "C0001",
                }
            ],
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["A"],
            context_block_ids=["C0010"],
            sentences=[
                {
                    "sentence_id": "S0001",
                    "text": "beta",
                    "source_block_id": "C0002",
                }
            ],
        ),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    validate_scope_assessment_evidence_cross_artifact(
        assessment_input,
        runtime_context,
        aggregate_units=units,
    )

    bad_provenance = copy.deepcopy(runtime_context)
    bad_provenance["unit_provenance"]["TU0001"]["candidate_text"] = "tampered"
    with pytest.raises(ValueError, match="scope_assessment_evidence_unit_text_mismatch"):
        validate_scope_assessment_evidence_cross_artifact(
            assessment_input,
            bad_provenance,
            aggregate_units=units,
        )

    tampered_scope = copy.deepcopy(assessment_input)
    tampered_scope["heading_scopes"][0]["assessment_evidence"]["candidate_text"] = "wrong"
    with pytest.raises(
        ValueError,
        match="scope_assessment_evidence_candidate_text_mismatch",
    ):
        validate_scope_assessment_evidence_cross_artifact(
            tampered_scope,
            runtime_context,
            aggregate_units=units,
        )


def test_prompt_uses_candidate_text_from_prepared_manifest() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["A", "B"],
            context_block_ids=["C0010"],
            sentences=[
                {
                    "sentence_id": "S0001",
                    "text": "first paragraph.",
                    "source_block_id": "C0001",
                }
            ],
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["A", "B"],
            context_block_ids=["C0010"],
            sentences=[
                {
                    "sentence_id": "S0001",
                    "text": "second paragraph.",
                    "source_block_id": "C0002",
                }
            ],
        ),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    llm_input = build_scope_aware_prompt_input(assessment_input, runtime_context)
    prompt_input = llm_input.prompt_input_bundle
    manifest = build_scope_assessment_task_manifest(assessment_input)
    scope = prompt_input["heading_scopes"][0]
    assert scope["scope_id"] == "S0001"
    assert scope["candidate_text"] == manifest[0]["candidate_text"]
    assert scope["candidate_text"] == "first paragraph.\n\nsecond paragraph."
    assert set(scope.keys()) == {"scope_id", "heading_path", "candidate_text"}
    assert "units" not in scope

    messages = build_clinical_safety_aggregate_heading_scope_assessment_zh_messages(prompt_input)
    user_content = next(message["content"] for message in messages if message["role"] == "user")
    rendered_scopes = json.loads(user_content.split("## Heading scopes\n", 1)[1].strip())
    assert rendered_scopes == prompt_input["heading_scopes"]


def test_runtime_prepare_file_hash_unchanged_with_new_evidence_field(tmp_path: Path) -> None:
    from tests.test_aggregate_evidence_runtime_prepare import _run_route_to_prepare

    refs = _run_route_to_prepare(tmp_path)
    assessment_input = load_json(refs["assessment_input"])
    coverage = load_json(refs["paths"]["coverage"])
    assert assessment_input["file_hash"] == coverage["file_hash"]


def _aggregate_unit_with_semantic_context(
    *,
    unit_id: str,
    heading_path: list[str],
    body_text: str,
    semantic_context_sentences: list[dict[str, str]],
    source_zone_key: str = "example_business_module_zh",
    route_basis: str = "projected_assembled_semantic",
    context_block_ids: list[str] | None = None,
) -> dict:
    unit = _aggregate_unit(
        unit_id=unit_id,
        heading_path=heading_path,
        context_block_ids=context_block_ids or [],
        source_zone_key=source_zone_key,
        sentences=[
            {
                "sentence_id": f"{unit_id}:S001",
                "text": body_text,
                "source_block_id": "C0006",
            }
        ],
    )
    unit["route_basis"] = route_basis
    unit["source_stage"] = "filter_projection"
    if context_block_ids is None and semantic_context_sentences:
        unit["context_block_ids"] = [
            str(sentence.get("source_block_id") or "C0006")
            for sentence in semantic_context_sentences
        ]
    return unit


def test_kind_context_does_not_prepend_scope_assessment_evidence() -> None:
    unit = _aggregate_unit_with_semantic_context(
        unit_id="TU0001",
        heading_path=["Overview"],
        body_text="Substantive ADR summary.",
        semantic_context_sentences=[
            {
                "text": "Legacy shared context sentence.",
                "source_block_id": "C0006",
                "source_item_index": "0",
            }
        ],
    )
    scopes = build_heading_scopes_from_aggregate_units([unit])
    attach_assessment_evidence_to_heading_scopes(scopes, [unit])
    assert scopes[0]["assessment_evidence"]["candidate_text"] == "Substantive ADR summary."


def test_heading_context_not_merged_into_scope_evidence() -> None:
    unit = _aggregate_unit(
        unit_id="TU0001",
        heading_path=["Section A"],
        context_block_ids=["C0010"],
        sentences=[
            {
                "sentence_id": "S0001",
                "text": "Substantive safety summary.",
                "source_block_id": "C0001",
            }
        ],
    )
    scopes = build_heading_scopes_from_aggregate_units([unit])
    attach_assessment_evidence_to_heading_scopes(scopes, [unit])
    assert scopes[0]["assessment_evidence"]["candidate_text"] == "Substantive safety summary."


def test_extra_context_block_ids_do_not_affect_scope_evidence() -> None:
    unit = _aggregate_unit(
        unit_id="TU0001",
        heading_path=["Section A"],
        context_block_ids=["C0010", "C0099"],
        sentences=[
            {
                "sentence_id": "S0001",
                "text": "Substantive text.",
                "source_block_id": "C0001",
            }
        ],
    )
    scopes = build_heading_scopes_from_aggregate_units([unit])
    attach_assessment_evidence_to_heading_scopes(scopes, [unit])
    evidence = scopes[0]["assessment_evidence"]["candidate_text"]
    assert "Section A" not in evidence
    assert evidence == "Substantive text."


def test_no_semantic_context_preserves_prior_scope_evidence_behavior() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["A"],
            context_block_ids=["C0010"],
            sentences=[
                {
                    "sentence_id": "S0001",
                    "text": "first paragraph.",
                    "source_block_id": "C0001",
                }
            ],
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["A"],
            context_block_ids=["C0010"],
            sentences=[
                {
                    "sentence_id": "S0001",
                    "text": "second paragraph.",
                    "source_block_id": "C0002",
                }
            ],
        ),
    ]
    scopes = build_heading_scopes_from_aggregate_units(units)
    attach_assessment_evidence_to_heading_scopes(scopes, units)
    assert scopes[0]["assessment_evidence"]["candidate_text"] == (
        "first paragraph.\n\nsecond paragraph."
    )


def test_semantic_context_does_not_change_heading_scope_identity() -> None:
    base_unit = _aggregate_unit(
        unit_id="TU0001",
        heading_path=["Overview"],
        context_block_ids=["C0006"],
        sentences=[
            {
                "sentence_id": "S0001",
                "text": "Substantive only.",
                "source_block_id": "C0006",
            }
        ],
    )
    enriched_unit = _aggregate_unit_with_semantic_context(
        unit_id="TU0001",
        heading_path=["Overview"],
        context_block_ids=["C0006"],
        source_zone_key="dsur_clinical_safety_zh",
        body_text="Substantive only.",
        semantic_context_sentences=[
            {
                "text": "Exposure denominator context.",
                "source_block_id": "C0006",
                "source_item_index": "0",
            }
        ],
    )
    base_scopes = build_heading_scopes_from_aggregate_units([base_unit])
    enriched_scopes = build_heading_scopes_from_aggregate_units([enriched_unit])
    assert heading_scope_signature(base_unit) == heading_scope_signature(enriched_unit)
    assert [scope["scope_id"] for scope in base_scopes] == [
        scope["scope_id"] for scope in enriched_scopes
    ]
    assert [unit["unit_id"] for unit in base_scopes[0]["units"]] == [
        unit["unit_id"] for unit in enriched_scopes[0]["units"]
    ]


def test_scope_evidence_helper_uses_primary_sentences_only() -> None:
    unit = _aggregate_unit_with_semantic_context(
        unit_id="TU0099",
        heading_path=["Overview"],
        source_zone_key="example_efficacy_zh",
        route_basis="projected_assembled_semantic",
        body_text="Efficacy summary sentence.",
        semantic_context_sentences=[
            {
                "text": "Study cohort context for efficacy reading.",
                "source_block_id": "C0099",
                "source_item_index": "1",
            }
        ],
    )
    text = build_unit_assessment_evidence_text(unit)
    assert text == "Efficacy summary sentence."


def test_scope_evidence_joins_member_unit_body_texts() -> None:
    shared_context = {
        "text": "Shared exposure denominator.",
        "source_block_id": "C0006",
        "source_item_index": "0",
    }
    units = [
        _aggregate_unit_with_semantic_context(
            unit_id="TU0001",
            heading_path=["Overview"],
            context_block_ids=["C0006"],
            body_text="First substantive paragraph.",
            semantic_context_sentences=[shared_context],
        ),
        _aggregate_unit_with_semantic_context(
            unit_id="TU0002",
            heading_path=["Overview"],
            context_block_ids=["C0006"],
            body_text="Second substantive paragraph.",
            semantic_context_sentences=[shared_context],
        ),
    ]
    scopes = build_heading_scopes_from_aggregate_units(units)
    attach_assessment_evidence_to_heading_scopes(scopes, units)
    assert scopes[0]["assessment_evidence"]["candidate_text"] == (
        "First substantive paragraph.\n\nSecond substantive paragraph."
    )
    assert build_scope_assessment_evidence_text(
        ordered_unit_ids=["TU0001", "TU0002"],
        unit_by_id={unit["unit_id"]: unit for unit in units},
    ) == scopes[0]["assessment_evidence"]["candidate_text"]
