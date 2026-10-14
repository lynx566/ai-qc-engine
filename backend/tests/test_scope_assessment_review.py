"""Scope assessment review artifact contract tests."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    build_assessment_runtime_context_envelope,
    build_assessment_runtime_context_id,
    validate_scope_assessment_evidence_cross_artifact,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    ASSESSMENT_INPUT_SCHEMA_VERSION,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessment_review import (
    SCOPE_ASSESSMENT_REVIEW_SCHEMA_VERSION,
    build_scope_assessment_review_envelope,
    build_scope_review_source_units,
    validate_scope_assessment_review_envelope,
    write_scope_assessment_review,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    SCOPE_ASSESSMENTS_SCHEMA_VERSION,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    attach_assessment_evidence_to_heading_scopes,
    build_heading_scopes_from_aggregate_units,
    build_unit_provenance_map,
)
from tests.test_assessment_input_compact import _aggregate_unit


def _runtime_context_for_units(
    *,
    units: list[dict],
    assessment_input: dict,
) -> dict:
    llm_input_bundle_id = str(assessment_input["llm_input_bundle_id"])
    runtime_context_id = build_assessment_runtime_context_id(
        llm_input_bundle_id=llm_input_bundle_id,
    )
    return build_assessment_runtime_context_envelope(
        llm_input_bundle_id=llm_input_bundle_id,
        runtime_context_id=runtime_context_id,
        doc_id=str(assessment_input["doc_id"]),
        file_hash=str(assessment_input["file_hash"]),
        route_stats={"unit_count": len(units)},
        unit_provenance=build_unit_provenance_map(units),
        source_routed_unit_bundle_ref={
            "routed_unit_bundle_id": "routed_test",
            "path": "routed_units_aggregate.json",
        },
        source_routing_manifest_ref={
            "routing_manifest_id": "route_test",
            "path": "routing_manifest.json",
        },
    )


def _assessment_input_from_units(units: list[dict]) -> tuple[dict[str, Any], dict[str, Any]]:
    heading_scopes = build_heading_scopes_from_aggregate_units(units)
    attach_assessment_evidence_to_heading_scopes(heading_scopes, units)
    assessment_input: dict[str, Any] = {
        "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
        "stage": "evidence_source_preparation",
        "phase": "prepare",
        "source_stage": "route",
        "llm_input_bundle_id": "llm_input_abc",
        "route": "aggregate",
        "doc_id": "doc_test",
        "zone_key": "dsur_clinical_safety_zh",
        "file_hash": "sha256:test",
        "doc_meta": {"doc_type": "DSUR"},
        "instructions": "test",
        "assessment_profile_ref": "clinical_safety_aggregate_heading_scope_assessment_zh",
        "heading_scopes": heading_scopes,
        "runtime_context_ref": {"runtime_context_id": "assessment_runtime_abc"},
    }
    runtime_context = _runtime_context_for_units(units=units, assessment_input=assessment_input)
    assessment_input["runtime_context_ref"]["runtime_context_id"] = runtime_context[
        "runtime_context_id"
    ]
    return assessment_input, runtime_context


def _scope_assessments_from_input_fixed(
    assessment_input: dict[str, Any],
    runtime_context: dict[str, Any],
    *,
    extra_scopes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scope_assessments = [
        {
            "scope_id": scope["scope_id"],
            "heading_path": scope["heading_path"],
            "source_unit_ids": [unit["unit_id"] for unit in scope["units"]],
            "product_context_role": "unknown",
            "unit_form": "aggregate",
            "safety_role": "unknown",
            "route_qc": {"route_mismatch": False, "suggested_route": None, "reason": None},
            "post_llm_validation_flags": ["f1", "f2"],
        }
        for scope in assessment_input["heading_scopes"]
    ]
    if extra_scopes:
        scope_assessments.extend(extra_scopes)
    return {
        "artifact_type": "scope_assessments",
        "schema_version": SCOPE_ASSESSMENTS_SCHEMA_VERSION,
        "doc_id": "doc_test",
        "assessment_profile_name": "clinical_safety_aggregate_heading_scope_assessment_zh",
        "source_assessment_input_ref": {
            "llm_input_bundle_id": "llm_input_abc",
            "path": "assessment_input.json",
        },
        "source_assessment_runtime_context_ref": {
            "assessment_runtime_context_id": runtime_context["runtime_context_id"],
            "path": "assessment_runtime_context.json",
        },
        "scope_assessments": scope_assessments,
    }


def _scope_trace_from_input(assessment_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope_processing": [
            {
                "scope_id": scope["scope_id"],
                "source_sentence_ids": [
                    sentence["sentence_id"]
                    for unit in scope["units"]
                    for sentence in unit["sentences"]
                ],
                "source_block_ids": [],
                "scope_evidence_view": {
                    "candidate_text": scope["assessment_evidence"]["candidate_text"],
                    "candidate_sentences": [
                        {"sentence_id": sentence["sentence_id"], "text": sentence["text"]}
                        for unit in scope["units"]
                        for sentence in unit["sentences"]
                    ],
                },
            }
            for scope in assessment_input["heading_scopes"]
        ]
    }


def _default_fixtures_fixed() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["A", "B"],
            context_block_ids=["C0010"],
            candidate_text="s1",
            sentences=[{"sentence_id": "S0001", "kind": "content", "text": "s1"}],
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["A", "B"],
            context_block_ids=["C0010"],
            candidate_text="s2",
            sentences=[{"sentence_id": "S0002", "kind": "content", "text": "s2"}],
        ),
    ]
    assessment_input, runtime_context = _assessment_input_from_units(units)
    scope_assessments = _scope_assessments_from_input_fixed(assessment_input, runtime_context)
    trace = _scope_trace_from_input(assessment_input)
    return scope_assessments, trace, assessment_input, runtime_context


def _build_review(**overrides: Any) -> dict[str, Any]:
    scope_assessments, trace, assessment_input, runtime_context = _default_fixtures_fixed()
    kwargs = {
        "scope_assessments": scope_assessments,
        "scope_assessment_trace": trace,
        "scope_assessments_path": "scope_assessments.json",
        "assessment_input": assessment_input,
        "assessment_runtime_context": runtime_context,
    }
    kwargs.update(overrides)
    return build_scope_assessment_review_envelope(**kwargs)


def test_build_and_validate_scope_assessment_review_envelope() -> None:
    payload = _build_review()
    validate_scope_assessment_review_envelope(payload)
    assert payload["schema_version"] == SCOPE_ASSESSMENT_REVIEW_SCHEMA_VERSION
    item = payload["items"][0]
    assert item["evidence"]["text"] == item["evidence"]["source_units"][0]["text"] + "\n\n" + item["evidence"]["source_units"][1]["text"]
    assert item["evidence"]["source_units"][0]["sentences"][0]["sentence_id"] == "S0001"
    assert item["source_block_ids"] == ["C0001", "C0002"]
    assert item["review_signals"]["post_llm_validation_flags"] == ["f1", "f2"]
    assert set(item["assessment"]) == {
        "product_context_role",
        "unit_form",
        "safety_role",
        "route_qc",
    }
    assert "source_sentence_ids" not in item
    assert "sentences" not in item["evidence"]


def test_multi_tu_duplicate_sentence_ids() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section"],
            context_block_ids=["C0010"],
            candidate_text="alpha one\nalpha two",
            sentences=[
                {"sentence_id": "S0001", "kind": "content", "text": "alpha one"},
                {"sentence_id": "S0002", "kind": "content", "text": "alpha two"},
            ],
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["Section"],
            context_block_ids=["C0010"],
            candidate_text="beta one\nbeta two",
            sentences=[
                {"sentence_id": "S0001", "kind": "content", "text": "beta one"},
                {"sentence_id": "S0002", "kind": "content", "text": "beta two"},
            ],
        ),
    ]
    assessment_input, runtime_context = _assessment_input_from_units(units)
    payload = build_scope_assessment_review_envelope(
        scope_assessments=_scope_assessments_from_input_fixed(assessment_input, runtime_context),
        scope_assessment_trace=_scope_trace_from_input(assessment_input),
        scope_assessments_path="scope_assessments.json",
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
    )
    item = payload["items"][0]
    assert item["evidence"]["source_units"][0]["unit_id"] == "TU0001"
    assert [s["sentence_id"] for s in item["evidence"]["source_units"][0]["sentences"]] == [
        "S0001",
        "S0002",
    ]
    assert item["evidence"]["source_units"][1]["unit_id"] == "TU0002"
    assert [s["sentence_id"] for s in item["evidence"]["source_units"][1]["sentences"]] == [
        "S0001",
        "S0002",
    ]
    assert "source_sentence_ids" not in item
    assert "sentences" not in item["evidence"]


def test_scope_unit_text_is_derived_from_canonical_sentences() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section"],
            context_block_ids=["C0010"],
            sentences=[
                {"sentence_id": "S0001", "kind": "content", "text": "line one"},
                {"sentence_id": "S0002", "kind": "content", "text": "line two"},
            ],
        ),
    ]
    assessment_input, runtime_context = _assessment_input_from_units(units)
    payload = build_scope_assessment_review_envelope(
        scope_assessments=_scope_assessments_from_input_fixed(assessment_input, runtime_context),
        scope_assessment_trace=_scope_trace_from_input(assessment_input),
        scope_assessments_path="scope_assessments.json",
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
    )
    item = payload["items"][0]
    source_unit = item["evidence"]["source_units"][0]
    assert units[0]["sentences"] == [
        {"sentence_id": "S0001", "kind": "content", "text": "line one"},
        {"sentence_id": "S0002", "kind": "content", "text": "line two"},
    ]
    assert [sentence["sentence_id"] for sentence in source_unit["sentences"]] == [
        sentence["sentence_id"] for sentence in units[0]["sentences"]
    ]
    assert [sentence["text"] for sentence in source_unit["sentences"]] == [
        sentence["text"] for sentence in units[0]["sentences"]
    ]
    assert source_unit["text"] == "line oneline two"
    assert item["evidence"]["text"] == "line oneline two"
    assert (
        item["evidence"]["text"]
        == assessment_input["heading_scopes"][0]["assessment_evidence"]["candidate_text"]
    )


def test_source_block_ids_order_and_dedup() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0003",
            heading_path=["Section"],
            context_block_ids=["C0010"],
            candidate_text="u3",
        ),
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section"],
            context_block_ids=["C0010"],
            candidate_text="u1",
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["Section"],
            context_block_ids=["C0010"],
            candidate_text="u2",
        ),
    ]
    heading_scopes = build_heading_scopes_from_aggregate_units(units)
    assert len(heading_scopes) == 1
    attach_assessment_evidence_to_heading_scopes(heading_scopes, units)
    assessment_input: dict[str, Any] = {
        "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
        "stage": "evidence_source_preparation",
        "phase": "prepare",
        "source_stage": "route",
        "llm_input_bundle_id": "llm_input_abc",
        "route": "aggregate",
        "doc_id": "doc_test",
        "zone_key": "dsur_clinical_safety_zh",
        "file_hash": "sha256:test",
        "doc_meta": {"doc_type": "DSUR"},
        "instructions": "test",
        "assessment_profile_ref": "clinical_safety_aggregate_heading_scope_assessment_zh",
        "heading_scopes": heading_scopes,
        "runtime_context_ref": {"runtime_context_id": "assessment_runtime_abc"},
    }
    runtime_context = _runtime_context_for_units(units=units, assessment_input=assessment_input)
    assessment_input["runtime_context_ref"]["runtime_context_id"] = runtime_context[
        "runtime_context_id"
    ]
    provenance = runtime_context["unit_provenance"]
    provenance["TU0001"]["source_block_ids"] = ["C0015", "C0016"]
    provenance["TU0002"]["source_block_ids"] = ["C0016", "C0017"]
    provenance["TU0003"]["source_block_ids"] = ["C0018"]

    payload = build_scope_assessment_review_envelope(
        scope_assessments=_scope_assessments_from_input_fixed(assessment_input, runtime_context),
        scope_assessment_trace=_scope_trace_from_input(assessment_input),
        scope_assessments_path="scope_assessments.json",
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
    )
    item = payload["items"][0]
    assert [unit["unit_id"] for unit in item["evidence"]["source_units"]] == [
        "TU0003",
        "TU0001",
        "TU0002",
    ]
    assert item["source_block_ids"] == ["C0018", "C0015", "C0016", "C0017"]


def test_single_tu_scope_still_nested() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Only"],
            context_block_ids=["C0010"],
            candidate_text="solo",
        ),
    ]
    assessment_input, runtime_context = _assessment_input_from_units(units)
    payload = build_scope_assessment_review_envelope(
        scope_assessments=_scope_assessments_from_input_fixed(assessment_input, runtime_context),
        scope_assessment_trace=_scope_trace_from_input(assessment_input),
        scope_assessments_path="scope_assessments.json",
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
    )
    item = payload["items"][0]
    assert len(item["evidence"]["source_units"]) == 1
    assert item["source_unit_ids"] == ["TU0001"]
    assert item["evidence"]["source_units"][0]["sentences"][0]["sentence_id"] == "S0001"


def test_overview_manual_sentence_id_preserved() -> None:
    manual_id = "OVC_MANUAL_001__C0006:S0001"
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Overview"],
            context_block_ids=["C0010"],
            candidate_text="overview sentence",
            sentences=[
                {"sentence_id": manual_id, "kind": "content", "text": "overview sentence"},
            ],
        ),
    ]
    assessment_input, runtime_context = _assessment_input_from_units(units)
    payload = build_scope_assessment_review_envelope(
        scope_assessments=_scope_assessments_from_input_fixed(assessment_input, runtime_context),
        scope_assessment_trace=_scope_trace_from_input(assessment_input),
        scope_assessments_path="scope_assessments.json",
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
    )
    assert payload["items"][0]["evidence"]["source_units"][0]["sentences"][0]["sentence_id"] == manual_id


@pytest.mark.parametrize(
    ("field_path", "mutator", "error_match"),
    [
        (
            "runtime candidate_text",
            lambda ai, rc: rc["unit_provenance"]["TU0001"].update({"candidate_text": "tampered"}),
            "scope_assessment_evidence_unit_text_mismatch",
        ),
        (
            "assessment_input unit order",
            lambda ai, rc: ai["heading_scopes"][0]["units"].reverse(),
            "scope_assessment_evidence_candidate_text_mismatch",
        ),
        (
            "scope evidence.text",
            lambda ai, rc: ai["heading_scopes"][0]["assessment_evidence"].update(
                {"candidate_text": "tampered scope"}
            ),
            "scope_assessment_evidence_candidate_text_mismatch",
        ),
    ],
)
def test_cross_artifact_tampering_fail_fast(
    field_path: str,
    mutator: Any,
    error_match: str,
) -> None:
    del field_path
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["A", "B"],
            context_block_ids=["C0010"],
            candidate_text="s1",
            sentences=[{"sentence_id": "S0001", "kind": "content", "text": "s1"}],
        ),
        _aggregate_unit(
            unit_id="TU0002",
            heading_path=["A", "B"],
            context_block_ids=["C0010"],
            candidate_text="s2",
            sentences=[{"sentence_id": "S0002", "kind": "content", "text": "s2"}],
        ),
    ]
    _, _, assessment_input, runtime_context = _default_fixtures_fixed()
    mutator(assessment_input, runtime_context)
    with pytest.raises(ValueError, match=error_match):
        validate_scope_assessment_evidence_cross_artifact(
            assessment_input,
            runtime_context,
            aggregate_units=units,
        )


def test_cross_artifact_tampering_sentences_fail_fast() -> None:
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessment_review import (
        validate_scope_review_projection,
    )

    scope_assessments, trace, assessment_input, runtime_context = _default_fixtures_fixed()
    payload = build_scope_assessment_review_envelope(
        scope_assessments=scope_assessments,
        scope_assessment_trace=trace,
        scope_assessments_path="scope_assessments.json",
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
    )
    review_item = payload["items"][0]
    assessment_scope = assessment_input["heading_scopes"][0]
    provenance_map = runtime_context["unit_provenance"]
    tampered_scope = copy.deepcopy(assessment_scope)
    tampered_scope["units"][0]["sentences"][0]["text"] = "tampered sentence"
    with pytest.raises(ValueError, match="scope_review_source_unit_sentences_mismatch"):
        validate_scope_review_projection(
            review_item=review_item,
            assessment_scope=tampered_scope,
            runtime_unit_provenance_by_id=provenance_map,
        )


def test_cross_artifact_tampering_blocks_fail_fast() -> None:
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessment_review import (
        validate_scope_review_projection,
    )

    scope_assessments, trace, assessment_input, runtime_context = _default_fixtures_fixed()
    payload = build_scope_assessment_review_envelope(
        scope_assessments=scope_assessments,
        scope_assessment_trace=trace,
        scope_assessments_path="scope_assessments.json",
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
    )
    review_item = copy.deepcopy(payload["items"][0])
    review_item["evidence"]["source_units"][0]["source_block_ids"] = ["C9999"]
    review_item["source_block_ids"] = ["C9999", "C0002"]
    with pytest.raises(ValueError, match="scope_review_source_block_ids_mismatch"):
        validate_scope_review_projection(
            review_item=review_item,
            assessment_scope=assessment_input["heading_scopes"][0],
            runtime_unit_provenance_by_id=runtime_context["unit_provenance"],
        )


def test_build_scope_review_source_units_rejects_empty_blocks() -> None:
    scope = {
        "scope_id": "HS0001",
        "units": [{"unit_id": "TU0001", "sentences": [{"sentence_id": "S0001", "text": "x"}]}],
    }
    with pytest.raises(ValueError, match="scope_review_source_unit_blocks_mismatch"):
        build_scope_review_source_units(
            assessment_scope=scope,
            runtime_unit_provenance_by_id={
                "TU0001": {"candidate_text": "x", "source_block_ids": []},
            },
        )


def test_schema_rejects_legacy_0_1_0_shape() -> None:
    payload = _build_review()
    payload["schema_version"] = "0.1.0"
    with pytest.raises(ValueError, match="schema_version"):
        validate_scope_assessment_review_envelope(payload)


def test_schema_rejects_source_sentence_ids() -> None:
    payload = _build_review()
    payload["items"][0]["source_sentence_ids"] = ["S0001"]
    with pytest.raises(ValueError, match="invalid fields"):
        validate_scope_assessment_review_envelope(payload)


def test_schema_rejects_flat_evidence_sentences() -> None:
    payload = _build_review()
    payload["items"][0]["evidence"]["sentences"] = [{"sentence_id": "S0001", "text": "x"}]
    with pytest.raises(ValueError, match="invalid fields"):
        validate_scope_assessment_review_envelope(payload)


def test_schema_rejects_source_unit_missing_required_field() -> None:
    payload = _build_review()
    del payload["items"][0]["evidence"]["source_units"][0]["text"]
    with pytest.raises(ValueError, match="invalid fields"):
        validate_scope_assessment_review_envelope(payload)


def test_schema_rejects_extra_item_field() -> None:
    payload = _build_review()
    payload["items"][0]["extra"] = 1
    with pytest.raises(ValueError, match="invalid fields"):
        validate_scope_assessment_review_envelope(payload)


def test_assessment_and_review_signals_unchanged_from_trace_only_projection() -> None:
    payload = _build_review()
    item = payload["items"][0]
    assert item["assessment"]["unit_form"] == "aggregate"
    assert item["assessment"]["route_qc"]["route_mismatch"] is False
    assert item["review_signals"] == {
        "post_llm_validation_flags": ["f1", "f2"],
        "route_mismatch": False,
    }
    assert item["heading_path"] == ["A", "B"]


def test_scope_assessment_review_rejects_invalid_artifact_type() -> None:
    payload = _build_review()
    payload["artifact_type"] = "bad"
    with pytest.raises(ValueError, match="artifact_type"):
        validate_scope_assessment_review_envelope(payload)


def test_scope_assessment_review_rejects_invalid_schema_version() -> None:
    payload = _build_review()
    payload["schema_version"] = "9.9.9"
    with pytest.raises(ValueError, match="schema_version"):
        validate_scope_assessment_review_envelope(payload)


def test_scope_assessment_review_rejects_missing_source_refs() -> None:
    scope_assessments, trace, assessment_input, runtime_context = _default_fixtures_fixed()
    del scope_assessments["source_assessment_input_ref"]
    with pytest.raises(ValueError, match="source_assessment_input_ref"):
        build_scope_assessment_review_envelope(
            scope_assessments=scope_assessments,
            scope_assessment_trace=trace,
            scope_assessments_path="scope_assessments.json",
            assessment_input=assessment_input,
            assessment_runtime_context=runtime_context,
        )


def test_scope_assessment_review_rejects_bad_sentence_shape() -> None:
    scope_assessments, trace, assessment_input, runtime_context = _default_fixtures_fixed()
    assessment_input["heading_scopes"][0]["units"][0]["sentences"][0]["sentence_id"] = ""
    with pytest.raises(ValueError, match="sentence_id"):
        build_scope_assessment_review_envelope(
            scope_assessments=scope_assessments,
            scope_assessment_trace=trace,
            scope_assessments_path="scope_assessments.json",
            assessment_input=assessment_input,
            assessment_runtime_context=runtime_context,
        )


def test_scope_assessment_review_rejects_flags_non_list() -> None:
    scope_assessments, trace, assessment_input, runtime_context = _default_fixtures_fixed()
    scope_assessments["scope_assessments"][0]["post_llm_validation_flags"] = "bad"
    with pytest.raises(ValueError, match="post_llm_validation_flags"):
        build_scope_assessment_review_envelope(
            scope_assessments=scope_assessments,
            scope_assessment_trace=trace,
            scope_assessments_path="scope_assessments.json",
            assessment_input=assessment_input,
            assessment_runtime_context=runtime_context,
        )


def test_scope_assessment_review_rejects_route_mismatch_non_bool() -> None:
    scope_assessments, trace, assessment_input, runtime_context = _default_fixtures_fixed()
    scope_assessments["scope_assessments"][0]["route_qc"]["route_mismatch"] = "no"
    with pytest.raises(ValueError, match="route_mismatch"):
        build_scope_assessment_review_envelope(
            scope_assessments=scope_assessments,
            scope_assessment_trace=trace,
            scope_assessments_path="scope_assessments.json",
            assessment_input=assessment_input,
            assessment_runtime_context=runtime_context,
        )


def test_scope_assessment_review_rejects_assessment_shape_extra_field() -> None:
    payload = _build_review()
    payload["items"][0]["assessment"]["extra"] = 1
    with pytest.raises(ValueError, match="assessment"):
        validate_scope_assessment_review_envelope(payload)


def test_scope_assessment_review_preserves_item_order_and_ids() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"]),
        _aggregate_unit(unit_id="TU0002", heading_path=["B"], context_block_ids=["C0011"]),
    ]
    assessment_input, runtime_context = _assessment_input_from_units(units)
    scope_assessments = _scope_assessments_from_input_fixed(assessment_input, runtime_context)
    trace = _scope_trace_from_input(assessment_input)
    payload = build_scope_assessment_review_envelope(
        scope_assessments=scope_assessments,
        scope_assessment_trace=trace,
        scope_assessments_path="scope_assessments.json",
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
    )
    assert [item["scope_id"] for item in payload["items"]] == ["HS0001", "HS0002"]


def test_scope_assessment_review_rejects_scope_id_order_mismatch() -> None:
    scope_assessments, trace, assessment_input, runtime_context = _default_fixtures_fixed()
    trace["scope_processing"][0]["scope_id"] = "HS9999"
    with pytest.raises(ValueError, match="scope_id order mismatch"):
        build_scope_assessment_review_envelope(
            scope_assessments=scope_assessments,
            scope_assessment_trace=trace,
            scope_assessments_path="scope_assessments.json",
            assessment_input=assessment_input,
            assessment_runtime_context=runtime_context,
        )


def test_scope_assessment_review_has_no_raw_or_provider_fields() -> None:
    payload = _build_review()
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in (
        "raw_scope_assessment",
        "llm_messages",
        "provider_request",
        "span_map",
        "changed_fields",
    ):
        assert forbidden not in serialized


def test_write_scope_assessment_review_writes_schema_0_3_0(tmp_path: Path) -> None:
    payload = _build_review()
    out_path = write_scope_assessment_review(tmp_path, payload)
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "0.3.0"


def test_build_scope_review_source_units_missing_provenance() -> None:
    scope = {
        "scope_id": "HS0001",
        "units": [{"unit_id": "TU0001", "sentences": [{"sentence_id": "S0001", "text": "x"}]}],
    }
    with pytest.raises(ValueError, match="scope_review_source_unit_missing"):
        build_scope_review_source_units(
            assessment_scope=scope,
            runtime_unit_provenance_by_id={},
        )
