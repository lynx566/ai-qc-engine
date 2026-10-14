"""Overview semantic decomposition Filter-output projection tests."""

from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from llm.providers.base import LLMRawResult
from operations.filter_output_projection.contracts import (
    CanonicalSourceRef,
    FilterOutputProjectionInput,
    FilterOutputProjectionStepResult,
    ResolvedFilterOutputProjectionJob,
    SemanticProjectionOutcome,
)
from operations.filter_output_projection.source_materialization import (
    materialize_projection_sources,
)
from steps.project_filter_output import run as run_project_filter_output
from plugins.clinical_trial_doc.filter_output_projection import (
    OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
    build_overview_semantic_decomposition_facade,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.response import (
    extract_json_text,
    parse_overview_assessment_response,
    validate_and_canonicalize_assessments,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.source_items import (
    PreparedOverviewSourceItem,
    build_overview_prompt_input_json,
    prepare_overview_source_items,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.vocabulary import (
    normalize_content_modules,
)
from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)
from tests.test_filter_output_projection_direct import _analysis_bundle_for_zone_match

OVERVIEW_PLUGIN_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "filter_output_projection"
    / "overview"
)

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _sentence_ids(source) -> list[str]:
    return [sentence.sentence_id for sentence in source.sentences]


def _sentence_texts(source) -> list[str]:
    return [sentence.text for sentence in source.sentences]


def _source_block_ids(source) -> list[str]:
    return [sentence.source_block_id for sentence in source.sentences]


def _paragraph_block(
    block_id: str,
    text: str,
    *,
    heading_path: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "block_id": block_id,
        "kind": "paragraph",
        "analysis_text": text,
        "heading_path": heading_path or ["摘要"],
    }


def _table_block(
    block_id: str,
    text: str,
    *,
    heading_path: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "block_id": block_id,
        "kind": "table",
        "analysis_text": text,
        "heading_path": heading_path or ["表格"],
    }


def _materialize_zone(
    zone_match_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any] | None = None,
):
    bundle = analysis_bundle or _analysis_bundle_for_zone_match(zone_match_bundle)
    return materialize_projection_sources(
        zone_match_bundle=zone_match_bundle,
        analysis_bundle=bundle,
    )


def _analysis_bundle_with_sentence_overrides(
    zone_match_bundle: dict[str, Any],
    sentences_by_block: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    from artifacts.prepare_analysis import build_analysis_bundle_artifact

    analysis_bundle = _analysis_bundle_for_zone_match(zone_match_bundle)
    for group_key in ("content_blocks", "table_blocks"):
        for block in analysis_bundle.get(group_key) or []:
            block_id = str(block.get("block_id") or "")
            if block_id in sentences_by_block:
                block["sentences"] = [
                    {
                        "sentence_id": str(sentence["sentence_id"]),
                        "analysis_text": str(sentence["analysis_text"]),
                    }
                    for sentence in sentences_by_block[block_id]
                ]
    return build_analysis_bundle_artifact(analysis_bundle)


def _prepare_from_zone(
    zone_match_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any] | None = None,
    *,
    sentences_by_block: dict[str, list[dict[str, str]]] | None = None,
):
    bundle = analysis_bundle
    if bundle is None and sentences_by_block:
        bundle = _analysis_bundle_with_sentence_overrides(
            zone_match_bundle,
            sentences_by_block,
        )
    elif bundle is None:
        bundle = _analysis_bundle_for_zone_match(zone_match_bundle)
    return prepare_overview_source_items(
        _materialize_zone(zone_match_bundle, bundle)
    )


def _projection_input_with_sources(
    zone_match_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any] | None = None,
) -> FilterOutputProjectionInput:
    bundle = analysis_bundle or _analysis_bundle_for_zone_match(zone_match_bundle)
    base = _projection_input(zone_match_bundle)
    return FilterOutputProjectionInput(
        filter_job_id=base.filter_job_id,
        doc_id=base.doc_id,
        file_hash=base.file_hash,
        zone_key=base.zone_key,
        zone_match_bundle=base.zone_match_bundle,
        projection_sources=materialize_projection_sources(
            zone_match_bundle=zone_match_bundle,
            analysis_bundle=bundle,
        ),
    )


def _zone_match_bundle(
    *,
    blocks: list[dict[str, Any]] | None = None,
    table_blocks: list[dict[str, Any]] | None = None,
    matched_zones: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if matched_zones is None:
        matched_zones = [
            {
                "zone_id": "ib_overview_zh",
                "blocks": blocks or [],
                "table_blocks": table_blocks or [],
            }
        ]
    return {
        "matched_zones": matched_zones,
        "matched_zone_count": len(matched_zones),
        "zone_config_name": "ib_overview_zh",
        "zone_config_version": "0.2.0",
        "language": "zh",
        "resolved_filter_strategy_id": "heading_zone",
        "doc_id": "doc_test",
    }


def _projection_input(zone_match_bundle: dict[str, Any]) -> FilterOutputProjectionInput:
    return FilterOutputProjectionInput(
        filter_job_id=IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id,
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
        zone_key="ib_overview_zh",
        zone_match_bundle=zone_match_bundle,
    )


def _assessment_response(
    assessments: list[tuple[str, list[str]]],
    *,
    wrap_fence: str | None = None,
) -> str:
    payload = {
        "sentence_assessments": [
            {"source_id": alias, "content_modules": modules}
            for alias, modules in assessments
        ]
    }
    raw = json.dumps(payload, ensure_ascii=False)
    if wrap_fence == "json":
        return f"```json\n{raw}\n```"
    if wrap_fence == "JSON":
        return f"```JSON\n{raw}\n```"
    if wrap_fence == "plain":
        return f"```\n{raw}\n```"
    return raw


@dataclass(frozen=True)
class FakeOverviewProvider:
    response_text: str

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        _ = messages
        return LLMRawResult(
            provider_name="fake",
            model="fake-overview",
            raw_text=self.response_text,
        )


def _run_overview(
    zone_match_bundle: dict[str, Any],
    response_text: str,
    *,
    sentences_by_block: dict[str, list[dict[str, str]]] | None = None,
):
    facade = build_overview_semantic_decomposition_facade(
        llm_provider=FakeOverviewProvider(response_text=response_text),
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    job = composition.resolve_filter_output_projection_job(
        IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id
    )
    if sentences_by_block:
        analysis_bundle = _analysis_bundle_with_sentence_overrides(
            zone_match_bundle,
            sentences_by_block,
        )
    else:
        analysis_bundle = _analysis_bundle_for_zone_match(zone_match_bundle)
    return run_project_filter_output(
        projection_input=_projection_input_with_sources(
            zone_match_bundle,
            analysis_bundle,
        ),
        analysis_bundle=analysis_bundle,
        job=job,
        facade=facade,
    )


def test_source_preparation_uses_canonical_sentences_and_prompt_aliases() -> None:
    bundle = _zone_match_bundle(
        blocks=[
            _paragraph_block(
                "C0001",
                "第一句。第二句！",
                heading_path=["摘要", "背景"],
            )
        ]
    )
    prepared = _prepare_from_zone(
        bundle,
        sentences_by_block={
            "C0001": [
                {"sentence_id": "C0001:S001", "analysis_text": "第一句。"},
                {"sentence_id": "C0001:S002", "analysis_text": "第二句！"},
            ]
        },
    )

    assert [item.prompt_alias for item in prepared.items] == ["O001", "O002"]
    assert [item.sentence_id for item in prepared.items] == [
        "C0001:S001",
        "C0001:S002",
    ]
    assert prepared.items[0].heading_path == ("摘要", "背景")
    assert prepared.items[0].block_id == "C0001"
    assert "local_group_id" not in PreparedOverviewSourceItem.__dataclass_fields__
    assert prepared.items[0].text == "第一句。"
    assert prepared.items[1].text == "第二句！"


def test_source_preparation_includes_table_blocks() -> None:
    bundle = _zone_match_bundle(
        table_blocks=[_table_block("T0001", "表格正文")]
    )
    prepared = _prepare_from_zone(bundle)

    assert len(prepared.items) == 1
    assert prepared.items[0].prompt_alias == "O001"
    assert prepared.items[0].sentence_id == "T0001:S001"
    assert prepared.items[0].source_group == "table_blocks"
    assert prepared.items[0].text == "表格正文"


def test_prompt_scopes_follow_contiguous_zone_and_heading_cohorts() -> None:
    bundle = _zone_match_bundle(
        matched_zones=[
            {
                "zone_id": "Z0001",
                "blocks": [
                    _paragraph_block("C0010", "A", heading_path=["同一标题"]),
                    _paragraph_block("C0011", "B", heading_path=["插入标题"]),
                    _paragraph_block("C0012", "C", heading_path=["同一标题"]),
                ],
                "table_blocks": [],
            },
            {
                "zone_id": "Z0002",
                "blocks": [
                    _paragraph_block("C0013", "D", heading_path=["同一标题"]),
                ],
                "table_blocks": [],
            },
        ]
    )

    payload = json.loads(build_overview_prompt_input_json(_prepare_from_zone(bundle)))

    assert [scope["heading_path"] for scope in payload] == [
        ["同一标题"],
        ["插入标题"],
        ["同一标题"],
        ["同一标题"],
    ]
    assert [
        [item["source_id"] for item in scope["source_items"]]
        for scope in payload
    ] == [["O001"], ["O002"], ["O003"], ["O004"]]


def test_overview_facade_requires_explicit_target_semantic_module_config() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C0014", "安全性。")])
    facade = build_overview_semantic_decomposition_facade(
        llm_provider=FakeOverviewProvider(
            response_text=_assessment_response([("O001", ["clinical_safety"])]),
        )
    )
    job = ResolvedFilterOutputProjectionJob(
        filter_job_id=IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id,
        strategy_id=OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        strategy_config={},
    )

    with pytest.raises(ValueError, match="target_semantic_module_id"):
        facade.project(
            projection_input=_projection_input_with_sources(bundle),
            job=job,
        )


def test_alias_maps_back_without_becoming_canonical_identity() -> None:
    bundle = _zone_match_bundle(
        blocks=[_paragraph_block("C0002", "安全性内容。")]
    )
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    response = _assessment_response([(alias, ["clinical_safety"])])
    result = _run_overview(bundle, response)

    projected = result.projected_sources[0]
    assert projected.source_refs[0].refs["block_id"] == "C0002"
    assert "alias" not in projected.source_refs[0].refs
    assert "source_id" not in projected.source_refs[0].refs
    source_ref = projected.sentences[0]
    assert source_ref.source_block_id == "C0002"
    assert source_ref.sentence_id == prepared.items[0].sentence_id


@pytest.mark.parametrize(
    ("module_id",),
    [
        ("clinical_safety",),
        ("efficacy",),
        ("pharmacokinetics",),
        ("nonclinical",),
        ("drug_information",),
        ("shared_context",),
        ("other",),
    ],
)
def test_target_specific_happy_path_modules(module_id: str) -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C0100", "模块内容。")])
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    result = _run_overview(bundle, _assessment_response([(alias, [module_id])]))

    assert any(
        outcome.semantic_module_id == module_id for outcome in result.semantic_outcomes
    )
    if module_id == "clinical_safety":
        assert [source.semantic_module_id for source in result.projected_sources] == [
            "clinical_safety"
        ]
    else:
        assert result.projected_sources == ()


def test_multi_label_business_modules_emit_target_block_once() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C0200", "双重模块。")])
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    result = _run_overview(
        bundle,
        _assessment_response([(alias, ["clinical_safety", "efficacy"])]),
    )

    assert len(result.projected_sources) == 1
    assert result.projected_sources[0].semantic_module_id == "clinical_safety"
    assert _sentence_ids(result.projected_sources[0]) == ["C0200:S001"]


@pytest.mark.parametrize(
    "modules",
    [
        ["shared_context", "clinical_safety"],
        ["shared_context", "other"],
        ["other", "clinical_safety"],
    ],
)
def test_mixed_exclusive_modules_accepted(modules: list[str]) -> None:
    assert normalize_content_modules(modules) == tuple(modules)


def test_assessment_missing_alias_fails() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C0300", "内容。")])
    with pytest.raises(ValueError, match="missing overview assessments"):
        _run_overview(bundle, _assessment_response([]))


def test_assessment_unknown_alias_fails() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C0301", "内容。")])
    with pytest.raises(ValueError, match="unknown overview assessment alias"):
        _run_overview(bundle, _assessment_response([("O999", ["other"])]))


def test_assessment_duplicate_alias_fails() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C0302", "内容。")])
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    with pytest.raises(ValueError, match="duplicate overview assessment"):
        _run_overview(
            bundle,
            _assessment_response([(alias, ["other"]), (alias, ["other"])]),
        )


def test_renamed_alias_rejected() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C0400", "内容。")])
    with pytest.raises(ValueError, match="unknown overview assessment alias"):
        _run_overview(bundle, _assessment_response([("O999", ["other"])]))


@pytest.mark.parametrize(
    ("modules", "error_match"),
    [
        (["unknown_module"], "unknown content_modules"),
        (["clinical_safety", "clinical_safety"], "duplicate"),
        ([], "non-empty"),
    ],
)
def test_module_validation_failures(modules: list[str], error_match: str) -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C0500", "内容。")])
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    with pytest.raises(ValueError, match=error_match):
        _run_overview(bundle, _assessment_response([(alias, modules)]))


def test_output_ordering_follows_input_source_item_order() -> None:
    bundle = _zone_match_bundle(
        blocks=[_paragraph_block("C0600", "第一句。第二句。")]
    )
    prepared = _prepare_from_zone(bundle)
    aliases = [item.prompt_alias for item in prepared.items]
    shuffled = list(reversed(aliases))
    response = _assessment_response(
        [(alias, ["other"]) for alias in shuffled],
    )
    parsed = parse_overview_assessment_response(response)
    canonical = validate_and_canonicalize_assessments(parsed, prepared)
    assert [item.prompt_alias for item in canonical] == aliases


@pytest.mark.parametrize("wrap_fence", [None, "plain", "json", "JSON"])
def test_json_fence_acceptance(wrap_fence: str | None) -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C0700", "内容。")])
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    result = _run_overview(
        bundle,
        _assessment_response([(alias, ["other"])], wrap_fence=wrap_fence),
    )
    assert result.semantic_outcomes


def test_json_fence_rejects_explanation_prefix() -> None:
    payload = _assessment_response([("O001", ["other"])])
    with pytest.raises(ValueError, match="valid JSON"):
        parse_overview_assessment_response(f"Here is the JSON:\n{payload}")


def test_mixed_block_retains_only_pure_shared_and_target_sentences_in_order() -> None:
    bundle = _zone_match_bundle(
        blocks=[_paragraph_block("C0900", "S1. S2. S3. S4.")]
    )
    prepared = _prepare_from_zone(
        bundle,
        sentences_by_block={
            "C0900": [
                {"sentence_id": "C0900:S001", "analysis_text": "S1"},
                {"sentence_id": "C0900:S002", "analysis_text": "S2"},
                {"sentence_id": "C0900:S003", "analysis_text": "S3"},
                {"sentence_id": "C0900:S004", "analysis_text": "S4"},
            ]
        },
    )
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["shared_context"]),
            (aliases[1], ["clinical_safety"]),
            (aliases[2], ["efficacy"]),
            (aliases[3], ["clinical_safety", "efficacy"]),
        ]
    )
    result = _run_overview(
        bundle,
        response,
        sentences_by_block={
            "C0900": [
                {"sentence_id": "C0900:S001", "analysis_text": "S1"},
                {"sentence_id": "C0900:S002", "analysis_text": "S2"},
                {"sentence_id": "C0900:S003", "analysis_text": "S3"},
                {"sentence_id": "C0900:S004", "analysis_text": "S4"},
            ]
        },
    )

    assert len(result.projected_sources) == 1
    source = result.projected_sources[0]
    assert source.semantic_module_id == "clinical_safety"
    assert _sentence_ids(source) == ["C0900:S001", "C0900:S002", "C0900:S004"]
    assert _sentence_texts(source) == ["S1", "S2", "S4"]
    assert _source_block_ids(source) == ["C0900", "C0900", "C0900"]


def test_shared_context_retained_across_blocks_in_same_heading_cohort() -> None:
    bundle = _zone_match_bundle(
        blocks=[
            _paragraph_block("C1000", "仅上下文。", heading_path=["执行概要"]),
            _paragraph_block("C1001", "安全性。", heading_path=["执行概要"]),
        ]
    )
    prepared = _prepare_from_zone(bundle)
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["shared_context"]),
            (aliases[1], ["clinical_safety"]),
        ]
    )
    result = _run_overview(bundle, response)

    assert len(result.projected_sources) == 2
    assert [_source_block_ids(source) for source in result.projected_sources] == [
        ["C1000"],
        ["C1001"],
    ]
    assert [source.source_refs[0].refs["block_id"] for source in result.projected_sources] == [
        "C1000",
        "C1001",
    ]


def test_shared_context_not_retained_across_different_heading() -> None:
    bundle = _zone_match_bundle(
        blocks=[
            _paragraph_block("C1010", "仅上下文。", heading_path=["执行概要"]),
            _paragraph_block("C1011", "安全性。", heading_path=["1.前言"]),
        ]
    )
    prepared = _prepare_from_zone(bundle)
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["shared_context"]),
            (aliases[1], ["clinical_safety"]),
        ]
    )
    result = _run_overview(bundle, response)

    safety = result.projected_sources[0]
    assert _source_block_ids(safety) == ["C1011"]
    assert _sentence_texts(safety) == ["安全性。"]


def test_shared_context_not_retained_for_non_contiguous_same_heading() -> None:
    bundle = _zone_match_bundle(
        blocks=[
            _paragraph_block("C1020", "仅上下文。", heading_path=["执行概要"]),
            _paragraph_block("C1021", "其他内容。", heading_path=["1.前言"]),
            _paragraph_block("C1022", "安全性。", heading_path=["执行概要"]),
        ]
    )
    prepared = _prepare_from_zone(bundle)
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["shared_context"]),
            (aliases[1], ["other"]),
            (aliases[2], ["clinical_safety"]),
        ]
    )
    result = _run_overview(bundle, response)

    safety = result.projected_sources[0]
    assert _source_block_ids(safety) == ["C1022"]
    assert _sentence_texts(safety) == ["安全性。"]


def test_shared_context_not_retained_across_zone_id() -> None:
    bundle = _zone_match_bundle(
        matched_zones=[
            {
                "zone_id": "Z0001",
                "blocks": [
                    _paragraph_block("C1030", "仅上下文。", heading_path=["执行概要"]),
                ],
                "table_blocks": [],
            },
            {
                "zone_id": "Z0002",
                "blocks": [
                    _paragraph_block("C1031", "安全性。", heading_path=["执行概要"]),
                ],
                "table_blocks": [],
            },
        ]
    )
    prepared = _prepare_from_zone(bundle)
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["shared_context"]),
            (aliases[1], ["clinical_safety"]),
        ]
    )
    result = _run_overview(bundle, response)

    safety = result.projected_sources[0]
    assert _source_block_ids(safety) == ["C1031"]
    assert _sentence_texts(safety) == ["安全性。"]


def test_shared_context_retained_once_without_business_module_fan_out() -> None:
    bundle = _zone_match_bundle(
        blocks=[
            _paragraph_block("C1040", "仅上下文。", heading_path=["执行概要"]),
            _paragraph_block("C1041", "安全性。", heading_path=["执行概要"]),
            _paragraph_block("C1042", "有效性。", heading_path=["执行概要"]),
        ]
    )
    prepared = _prepare_from_zone(bundle)
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["shared_context"]),
            (aliases[1], ["clinical_safety"]),
            (aliases[2], ["efficacy"]),
        ]
    )
    result = _run_overview(bundle, response)

    assert len(result.projected_sources) == 2
    assert [_source_block_ids(source) for source in result.projected_sources] == [
        ["C1040"],
        ["C1041"],
    ]
    assert all(
        source.semantic_module_id == "clinical_safety"
        for source in result.projected_sources
    )


def test_mixed_shared_context_and_business_module_not_added_as_context() -> None:
    bundle = _zone_match_bundle(
        blocks=[
            _paragraph_block("C1050", "上下文兼有效性。", heading_path=["执行概要"]),
            _paragraph_block("C1051", "安全性。", heading_path=["执行概要"]),
        ]
    )
    prepared = _prepare_from_zone(bundle)
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["shared_context", "efficacy"]),
            (aliases[1], ["clinical_safety"]),
        ]
    )
    result = _run_overview(bundle, response)

    assert len(result.projected_sources) == 1
    safety = result.projected_sources[0]
    assert _source_block_ids(safety) == ["C1051"]


def test_heading_cohort_retention_preserves_projected_source_granularity() -> None:
    bundle = _zone_match_bundle(
        blocks=[
            _paragraph_block("C1060", "仅上下文。", heading_path=["执行概要"]),
            _paragraph_block("C1061", "安全性一。", heading_path=["执行概要"]),
            _paragraph_block("C1062", "安全性二。", heading_path=["执行概要"]),
        ]
    )
    prepared = _prepare_from_zone(bundle)
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["shared_context"]),
            (aliases[1], ["clinical_safety"]),
            (aliases[2], ["clinical_safety"]),
        ]
    )
    result = _run_overview(bundle, response)

    safety_sources = [
        source
        for source in result.projected_sources
        if source.semantic_module_id == "clinical_safety"
    ]
    assert len(safety_sources) == 3
    assert [_source_block_ids(source) for source in safety_sources] == [
        ["C1060"],
        ["C1061"],
        ["C1062"],
    ]
    assert all("local_group_id" not in source.lineage for source in safety_sources)


def test_context_only_group_retains_outcome_without_projected_source() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C1100", "上下文。")])
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    result = _run_overview(
        bundle,
        _assessment_response([(alias, ["shared_context"])]),
    )

    assert result.projected_sources == ()
    assert len(result.semantic_outcomes) == 1
    assert result.semantic_outcomes[0].semantic_module_id == "shared_context"


def test_other_only_retains_outcome_without_projected_source() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C1200", "其他。")])
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    result = _run_overview(
        bundle,
        _assessment_response([(alias, ["other"])]),
    )

    assert result.projected_sources == ()
    assert result.semantic_outcomes[0].semantic_module_id == "other"


def test_step_integration_via_application_binding() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    job = composition.resolve_filter_output_projection_job(
        IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id
    )
    assert job.strategy_id == OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID

    bundle = _zone_match_bundle(blocks=[_paragraph_block("C1300", "安全性。")])
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    facade = build_overview_semantic_decomposition_facade(
        llm_provider=FakeOverviewProvider(
            response_text=_assessment_response([(alias, ["clinical_safety"])])
        )
    )
    result = run_project_filter_output(
        projection_input=_projection_input(bundle),
        analysis_bundle=_analysis_bundle_for_zone_match(bundle),
        job=job,
        facade=facade,
    )
    assert result.projected_sources[0].semantic_module_id == "clinical_safety"


def test_overview_plugin_has_no_forbidden_production_dependencies() -> None:
    forbidden = (
        "llm_experiments",
        "scripts",
        "runtime",
        "steps.route",
        "operations.flow",
        "coverage_bundle",
        "openai",
        "bailian",
    )
    for path in OVERVIEW_PLUGIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for token in forbidden:
                        assert token not in alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                for token in forbidden:
                    assert token not in node.module


def test_extract_json_text_matches_narrow_contract() -> None:
    raw = '{"sentence_assessments": []}'
    assert extract_json_text(raw) == raw
    assert extract_json_text(f"```json\n{raw}\n```") == raw


def _safety_outcomes(
    result: FilterOutputProjectionStepResult,
) -> list[SemanticProjectionOutcome]:
    return [
        outcome
        for outcome in result.semantic_outcomes
        if outcome.semantic_module_id == "clinical_safety"
    ]


def test_same_block_same_module_different_items_have_distinct_outcome_refs() -> None:
    bundle = _zone_match_bundle(
        blocks=[_paragraph_block("C2000", "第一句安全。第二句安全。")]
    )
    prepared = _prepare_from_zone(
        bundle,
        sentences_by_block={
            "C2000": [
                {"sentence_id": "C2000:S001", "analysis_text": "第一句安全。"},
                {"sentence_id": "C2000:S002", "analysis_text": "第二句安全。"},
            ]
        },
    )
    aliases = [item.prompt_alias for item in prepared.items]
    assert len(aliases) >= 2
    response = _assessment_response(
        [
            (aliases[0], ["clinical_safety"]),
            (aliases[1], ["clinical_safety"]),
        ]
    )
    result = _run_overview(
        bundle,
        response,
        sentences_by_block={
            "C2000": [
                {"sentence_id": "C2000:S001", "analysis_text": "第一句安全。"},
                {"sentence_id": "C2000:S002", "analysis_text": "第二句安全。"},
            ]
        },
    )

    safety_outcomes = _safety_outcomes(result)
    assert len(safety_outcomes) == 2
    ref_a = safety_outcomes[0].source_refs[0].refs
    ref_b = safety_outcomes[1].source_refs[0].refs
    assert ref_a != ref_b
    assert ref_a["block_id"] == ref_b["block_id"] == "C2000"
    assert ref_a["sentence_id"] != ref_b["sentence_id"]


def test_same_item_different_modules_share_precise_source_ref() -> None:
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C2100", "双重模块。")])
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    result = _run_overview(
        bundle,
        _assessment_response([(alias, ["clinical_safety", "efficacy"])]),
    )

    module_outcomes = [
        outcome
        for outcome in result.semantic_outcomes
        if outcome.semantic_module_id in {"clinical_safety", "efficacy"}
    ]
    assert len(module_outcomes) == 2
    assert (
        module_outcomes[0].source_refs[0].refs
        == module_outcomes[1].source_refs[0].refs
    )
    assert module_outcomes[0].semantic_module_id != module_outcomes[1].semantic_module_id


@dataclass(frozen=True)
class _DuplicateOutcomeFacade:
    job: ResolvedFilterOutputProjectionJob

    def project(
        self,
        *,
        projection_input: FilterOutputProjectionInput,
        job: ResolvedFilterOutputProjectionJob,
    ) -> FilterOutputProjectionStepResult:
        _ = job
        precise_ref = CanonicalSourceRef(
            refs={
                "block_id": "C2200",
                "source_group": "blocks",
                "sentence_id": "C2200:S001",
            }
        )
        duplicate = SemanticProjectionOutcome(
            semantic_module_id="clinical_safety",
            source_refs=(precise_ref,),
        )
        return FilterOutputProjectionStepResult(
            filter_job_id=projection_input.filter_job_id,
            doc_id=projection_input.doc_id,
            file_hash=projection_input.file_hash,
            zone_key=projection_input.zone_key,
            projected_sources=(),
            semantic_outcomes=(duplicate, duplicate),
        )


def test_exact_duplicate_semantic_outcome_rejected_by_step() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    job = composition.resolve_filter_output_projection_job(
        IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id
    )
    bundle = _zone_match_bundle(blocks=[_paragraph_block("C2200", "内容。")])
    with pytest.raises(ValueError, match="duplicate semantic outcome identity"):
        run_project_filter_output(
            projection_input=_projection_input(bundle),
            analysis_bundle=_analysis_bundle_for_zone_match(bundle),
            job=job,
            facade=_DuplicateOutcomeFacade(job=job),
        )


def test_prompt_alias_not_used_in_canonical_identity_fields() -> None:
    bundle = _zone_match_bundle(
        blocks=[_paragraph_block("C2300", "第一句。第二句。")]
    )
    prepared = _prepare_from_zone(
        bundle,
        sentences_by_block={
            "C2300": [
                {"sentence_id": "C2300:S001", "analysis_text": "第一句。"},
                {"sentence_id": "C2300:S002", "analysis_text": "第二句。"},
            ]
        },
    )
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [(alias, ["clinical_safety"]) for alias in aliases]
    )
    result = _run_overview(
        bundle,
        response,
        sentences_by_block={
            "C2300": [
                {"sentence_id": "C2300:S001", "analysis_text": "第一句。"},
                {"sentence_id": "C2300:S002", "analysis_text": "第二句。"},
            ]
        },
    )

    identity_keys = (
        "block_id",
        "source_group",
        "sentence_id",
    )
    for outcome in result.semantic_outcomes:
        refs = outcome.source_refs[0].refs
        assert refs["block_id"] == "C2300"
        assert ":" not in refs["block_id"]
        for key in refs:
            assert key in identity_keys
        assert "alias" not in refs
        assert "source_id" not in refs
        assert not refs["sentence_id"].startswith("O")
    for source in result.projected_sources:
        for sentence in source.sentences:
            assert ":" not in sentence.source_block_id
            assert not sentence.sentence_id.startswith("O")
            assert sentence.sentence_id


def test_shared_context_outcome_and_payload_reference_precise_item() -> None:
    bundle = _zone_match_bundle(
        blocks=[_paragraph_block("C2400", "上下文。安全性。")]
    )
    prepared = _prepare_from_zone(
        bundle,
        sentences_by_block={
            "C2400": [
                {"sentence_id": "C2400:S001", "analysis_text": "上下文。"},
                {"sentence_id": "C2400:S002", "analysis_text": "安全性。"},
            ]
        },
    )
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["shared_context"]),
            (aliases[1], ["clinical_safety"]),
        ]
    )
    result = _run_overview(
        bundle,
        response,
        sentences_by_block={
            "C2400": [
                {"sentence_id": "C2400:S001", "analysis_text": "上下文。"},
                {"sentence_id": "C2400:S002", "analysis_text": "安全性。"},
            ]
        },
    )
    context_outcome = next(
        outcome
        for outcome in result.semantic_outcomes
        if outcome.semantic_module_id == "shared_context"
    )
    context_ref = context_outcome.source_refs[0].refs
    safety = result.projected_sources[0]
    assert _sentence_ids(safety) == [
        prepared.items[0].sentence_id,
        prepared.items[1].sentence_id,
    ]
    assert context_ref["sentence_id"] == prepared.items[0].sentence_id
    assert safety.sentences[1].sentence_id == prepared.items[1].sentence_id


def test_other_outcome_has_precise_source_item_provenance() -> None:
    bundle = _zone_match_bundle(
        blocks=[_paragraph_block("C2500", "其他。有效性。")]
    )
    prepared = _prepare_from_zone(
        bundle,
        sentences_by_block={
            "C2500": [
                {"sentence_id": "C2500:S001", "analysis_text": "其他。"},
                {"sentence_id": "C2500:S002", "analysis_text": "有效性。"},
            ]
        },
    )
    aliases = [item.prompt_alias for item in prepared.items]
    response = _assessment_response(
        [
            (aliases[0], ["other"]),
            (aliases[1], ["efficacy"]),
        ]
    )
    result = _run_overview(
        bundle,
        response,
        sentences_by_block={
            "C2500": [
                {"sentence_id": "C2500:S001", "analysis_text": "其他。"},
                {"sentence_id": "C2500:S002", "analysis_text": "有效性。"},
            ]
        },
    )

    other_outcome = next(
        outcome
        for outcome in result.semantic_outcomes
        if outcome.semantic_module_id == "other"
    )
    assert other_outcome.source_refs[0].refs["sentence_id"] == prepared.items[0].sentence_id
    efficacy_outcome = next(
        outcome
        for outcome in result.semantic_outcomes
        if outcome.semantic_module_id == "efficacy"
    )
    assert efficacy_outcome.source_refs[0].refs["sentence_id"] == prepared.items[1].sentence_id
    assert result.projected_sources == ()


def test_table_source_item_preserves_canonical_whole_unit_sentence_id() -> None:
    bundle = _zone_match_bundle(
        table_blocks=[_table_block("T2500", "表格正文")]
    )
    prepared = _prepare_from_zone(bundle)
    alias = prepared.items[0].prompt_alias
    result = _run_overview(
        bundle,
        _assessment_response([(alias, ["clinical_safety"])]),
    )

    item = prepared.items[0]
    assert item.sentence_id == "T2500:S001"
    outcome_ref = result.semantic_outcomes[0].source_refs[0].refs
    assert outcome_ref["sentence_id"] == "T2500:S001"
    assert "char_start" not in outcome_ref
    assert "source_item_index" not in outcome_ref
