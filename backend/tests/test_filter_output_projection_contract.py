"""Slice 3 Filter-output projection canonical sentence contract tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dataclasses import fields

from artifacts.filter_output_projection_bundle import (
    FILTER_OUTPUT_PROJECTION_SCHEMA_VERSION,
    build_filter_output_projection_bundle,
    validate_filter_output_projection_bundle,
)
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionInput,
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.projected_sentence import (
    reject_legacy_projected_source_payload,
)
from steps.project_filter_output import run as run_project_filter_output
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.test_filter_output_projection_direct import (
    _analysis_bundle_for_zone_match,
    _filter_artifacts_for_profile,
    _projection_input_for_profile,
    _resolved_direct_job,
    _safety_analysis_bundle,
)
from tests.test_filter_output_projection_overview import (
    _assessment_response,
    _paragraph_block,
    _run_overview,
    _sentence_ids,
    _sentence_texts,
    _zone_match_bundle,
)


def test_schema_version_is_0_4_0() -> None:
    assert FILTER_OUTPUT_PROJECTION_SCHEMA_VERSION == "0.4.0"


def test_direct_emits_canonical_sentences_without_analysis_text() -> None:
    profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    zone_match_bundle, _, _, analysis_bundle = _filter_artifacts_for_profile(profile)
    result = run_project_filter_output(
        projection_input=_projection_input_for_profile(profile, zone_match_bundle),
        analysis_bundle=analysis_bundle,
        job=_resolved_direct_job(profile),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )
    paragraph = next(
        source
        for source in result.projected_sources
        if source.source_refs[0].refs.get("block_id") == "C0001"
    )
    assert paragraph.sentences
    assert paragraph.sentences[0].sentence_id == "C0001:S001"
    assert "analysis_text" not in paragraph.payload


def test_direct_multi_sentence_block_emits_all_sentences() -> None:
    from core.document.sentence_index import build_sentences

    text = "A。B。"
    built = build_sentences("B002", "paragraph", raw_text=text, normalized_text=text)
    zone_match = _zone_match_bundle(
        blocks=[
            {
                "block_id": "B002",
                "kind": "paragraph",
                "analysis_text": text,
            }
        ]
    )
    zone_match["file_hash"] = (
        "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    analysis_bundle = _analysis_bundle_for_zone_match(zone_match)
    for block in analysis_bundle["content_blocks"]:
        if block["block_id"] == "B002":
            block["sentences"] = [
                {"sentence_id": sentence.sentence_id, "analysis_text": sentence.normalized_text}
                for sentence in built
            ]
    projection_input = FilterOutputProjectionInput(
        filter_job_id="test_job",
        doc_id=zone_match["doc_id"],
        file_hash=zone_match["file_hash"],
        zone_key=zone_match["zone_config_name"],
        zone_match_bundle=zone_match,
    )
    job = ResolvedFilterOutputProjectionJob(
        filter_job_id="test_job",
        strategy_id=DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        strategy_config={"semantic_module_id": "clinical_safety"},
    )
    result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=analysis_bundle,
        job=job,
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )
    source = result.projected_sources[0]
    assert [sentence.sentence_id for sentence in source.sentences] == [
        "B002:S001",
        "B002:S002",
    ]
    assert [sentence.text for sentence in source.sentences] == ["A。", "B。"]
    assert all(sentence.source_block_id == "B002" for sentence in source.sentences)


def test_heading_block_preserves_block_kind_without_sentence_kind() -> None:
    analysis_bundle = _safety_analysis_bundle()
    zone_match, _, _, _ = _filter_artifacts_for_profile(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH)
    result = run_project_filter_output(
        projection_input=_projection_input_for_profile(
            IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
            zone_match,
        ),
        analysis_bundle=analysis_bundle,
        job=_resolved_direct_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )
    heading = next(
        source
        for source in result.projected_sources
        if source.source_refs[0].refs.get("block_id") == "H0001"
    )
    assert heading.source_refs[0].refs.get("block_kind") == "heading"
    assert heading.payload.get("block_kind") == "heading"
    assert heading.sentences[0].sentence_id == "H0001:S001"
    assert heading.sentences[0].source_block_id == "H0001"
    assert not hasattr(heading.sentences[0], "kind")


def test_overview_target_specific_block_assembly_order() -> None:
    bundle = _zone_match_bundle(
        blocks=[_paragraph_block("C0900", "上下文。安全性。有效性。")]
    )
    prepared_sentences = {
        "C0900": [
            {"sentence_id": "C0900:S001", "analysis_text": "上下文。"},
            {"sentence_id": "C0900:S002", "analysis_text": "安全性。"},
            {"sentence_id": "C0900:S003", "analysis_text": "有效性。"},
        ]
    }
    result = _run_overview(
        bundle,
        _assessment_response(
            [
                ("O001", ["shared_context"]),
                ("O002", ["clinical_safety"]),
                ("O003", ["efficacy"]),
            ]
        ),
        sentences_by_block=prepared_sentences,
    )
    safety = next(
        source for source in result.projected_sources if source.semantic_module_id == "clinical_safety"
    )
    assert _sentence_ids(safety) == ["C0900:S001", "C0900:S002"]
    assert len(result.projected_sources) == 1


def test_overview_no_role_or_kind_on_sentences() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C3000", "内容。")])
    result = _run_overview(
        bundle,
        _assessment_response([("O001", ["clinical_safety"])]),
    )
    for source in result.projected_sources:
        assert "substantive_items" not in source.payload
        assert "context_items" not in source.payload
        for sentence in source.sentences:
            assert {field.name for field in fields(sentence)} == {
                "sentence_id",
                "text",
                "source_block_id",
            }


def test_duplicate_text_distinct_sentence_ids() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C3100", "A。A。")])
    result = _run_overview(
        bundle,
        _assessment_response(
            [
                ("O001", ["shared_context"]),
                ("O002", ["clinical_safety"]),
            ]
        ),
        sentences_by_block={
            "C3100": [
                {"sentence_id": "C3100:S001", "analysis_text": "A。"},
                {"sentence_id": "C3100:S002", "analysis_text": "A。"},
            ]
        },
    )
    safety = result.projected_sources[0]
    assert _sentence_texts(safety) == ["A。", "A。"]
    assert _sentence_ids(safety) == ["C3100:S001", "C3100:S002"]


def test_target_specific_shared_context_does_not_fan_out_across_block_sources() -> None:
    bundle = _zone_match_bundle(
        blocks=[
            _paragraph_block("C3200", "上下文。"),
            _paragraph_block("C3201", "安全性。"),
            _paragraph_block("C3202", "有效性。"),
        ]
    )
    result = _run_overview(
        bundle,
        _assessment_response(
            [
                ("O001", ["shared_context"]),
                ("O002", ["clinical_safety"]),
                ("O003", ["efficacy"]),
            ]
        ),
    )
    assert len(result.projected_sources) == 2
    sentence_ids = [
        sentence.sentence_id
        for source in result.projected_sources
        for sentence in source.sentences
    ]
    assert sentence_ids == ["C3200:S001", "C3201:S001"]
    assert len(sentence_ids) == len(set(sentence_ids))


def test_persisted_bundle_rejects_legacy_payload_keys() -> None:
    with pytest.raises(ValueError, match="legacy body keys"):
        reject_legacy_projected_source_payload({"analysis_text": "legacy"}, label="payload")


def test_bundle_round_trip_preserves_sentences() -> None:
    zone_match = _zone_match_bundle(blocks=[_paragraph_block("C3300", "概述内容。")])
    result = _run_overview(
        zone_match,
        _assessment_response([("O001", ["clinical_safety"])]),
    )
    bundle = build_filter_output_projection_bundle(
        step_result=result,
        run_id="contract_test",
    )
    validate_filter_output_projection_bundle(bundle)
    assert bundle["schema_version"] == "0.4.0"
    assert bundle["projected_sources"][0]["sentences"]
