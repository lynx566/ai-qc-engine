"""Slice 2 regressions: Direct/Overview ProjectionSource consumer cutover."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.prepare_analysis import (
    ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
    ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
    build_analysis_bundle_artifact,
)
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionInput,
)
from operations.filter_output_projection.source_materialization import (
    materialize_projection_sources,
)
from steps.project_filter_output import run as run_project_filter_output
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
)
from plugins.clinical_trial_doc.filter_output_projection.direct import (
    project_direct_filter_output,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.assembly import (
    assemble_overview_projection_result,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.response import (
    ValidatedOverviewAssessment,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.source_items import (
    build_overview_prompt_input_json,
    prepare_overview_source_items,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.test_filter_output_projection_direct import (
    LINEAGE_FILE_HASH,
    _analysis_bundle_for_zone_match,
    _filter_artifacts_for_profile,
    _projection_input_for_profile,
    _resolved_direct_job,
)
from tests.test_filter_output_projection_overview import (
    _projection_input,
    _zone_match_bundle,
)

DOC_ID = "doc_test"
ZONE_KEY = "test_zone_zh"


def _analysis_bundle_with_blocks(
    content_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    return build_analysis_bundle_artifact(
        {
            "doc_id": DOC_ID,
            "file_name": "sample.docx",
            "source_type": "docx",
            "file_hash": LINEAGE_FILE_HASH,
            "analysis_bundle_id": "prepare_analysis_cutover_test",
            "analysis_bundle_contract": ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
            "analysis_bundle_schema_version": ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
            "stage": "prepare_analysis",
            "pipeline": ["extract", "prepare_analysis"],
            "privacy_enabled": True,
            "privacy_transforms": {"after_extract": {"applied": True}},
            "front_matter_blocks": [],
            "content_blocks": content_blocks,
            "table_blocks": [],
            "format_blocks": [],
        }
    )


def _zone_with_block(
    block_id: str,
    *,
    analysis_text: str,
    heading_path: list[str] | None = None,
) -> dict[str, Any]:
    return _zone_match_bundle(
        blocks=[
            {
                "block_id": block_id,
                "kind": "paragraph",
                "heading_path": heading_path or ["摘要"],
                "analysis_text": analysis_text,
            }
        ]
    )


def _projection_input_with_sources(
    zone_match_bundle: dict[str, Any],
    analysis_bundle: dict[str, Any],
    *,
    filter_job_id: str = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id,
    zone_key: str = "ib_clinical_safety_zh",
) -> FilterOutputProjectionInput:
    return FilterOutputProjectionInput(
        filter_job_id=filter_job_id,
        doc_id=DOC_ID,
        file_hash=LINEAGE_FILE_HASH,
        zone_key=zone_key,
        zone_match_bundle=zone_match_bundle,
        projection_sources=materialize_projection_sources(
            zone_match_bundle=zone_match_bundle,
            analysis_bundle=analysis_bundle,
        ),
    )


def test_direct_uses_projection_source_text_not_zone_match_copy() -> None:
    zone_match_bundle = _zone_with_block(
        "C0001",
        analysis_text="OLD / DIFFERENT",
    )
    analysis_bundle = _analysis_bundle_with_blocks(
        [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "CANONICAL DOWNSTREAM TEXT",
                "sentences": [
                    {
                        "sentence_id": "C0001:S001",
                        "analysis_text": "CANONICAL DOWNSTREAM TEXT",
                    }
                ],
            }
        ]
    )
    projection_input = _projection_input_with_sources(
        zone_match_bundle,
        analysis_bundle,
    )
    result = project_direct_filter_output(
        projection_input=projection_input,
        job=_resolved_direct_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    source = result.projected_sources[0]
    assert source.sentences[0].text == "CANONICAL DOWNSTREAM TEXT"
    assert "analysis_text" not in source.payload


def test_overview_consumes_canonical_sentences_not_block_resplit() -> None:
    zone_match_bundle = _zone_with_block("C0001", analysis_text="A。B。")
    analysis_bundle = _analysis_bundle_with_blocks(
        [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "A。B。",
                "sentences": [
                    {
                        "sentence_id": "C0001:S001",
                        "analysis_text": "A。B。",
                    }
                ],
            }
        ]
    )
    sources = materialize_projection_sources(
        zone_match_bundle=zone_match_bundle,
        analysis_bundle=analysis_bundle,
    )
    prepared = prepare_overview_source_items(sources)

    assert len(prepared.items) == 1
    assert prepared.items[0].sentence_id == "C0001:S001"
    assert prepared.items[0].text == "A。B。"
    assert prepared.items[0].prompt_alias == "O001"


def test_overview_reverse_mismatch_uses_sentence_boundaries() -> None:
    zone_match_bundle = _zone_with_block("C0001", analysis_text="AB")
    analysis_bundle = _analysis_bundle_with_blocks(
        [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "AB",
                "sentences": [
                    {"sentence_id": "C0001:S001", "analysis_text": "A"},
                    {"sentence_id": "C0001:S002", "analysis_text": "B"},
                ],
            }
        ]
    )
    prepared = prepare_overview_source_items(
        materialize_projection_sources(
            zone_match_bundle=zone_match_bundle,
            analysis_bundle=analysis_bundle,
        )
    )

    assert [item.sentence_id for item in prepared.items] == [
        "C0001:S001",
        "C0001:S002",
    ]
    assert [item.prompt_alias for item in prepared.items] == ["O001", "O002"]


def test_overview_duplicate_text_preserves_distinct_sentence_ids() -> None:
    zone_match_bundle = _zone_with_block("C0001", analysis_text="A。")
    analysis_bundle = _analysis_bundle_with_blocks(
        [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "A。",
                "sentences": [
                    {"sentence_id": "C0001:S001", "analysis_text": "A。"},
                    {"sentence_id": "C0001:S002", "analysis_text": "A。"},
                ],
            }
        ]
    )
    prepared = prepare_overview_source_items(
        materialize_projection_sources(
            zone_match_bundle=zone_match_bundle,
            analysis_bundle=analysis_bundle,
        )
    )

    assert prepared.items[0].sentence_id != prepared.items[1].sentence_id
    assert prepared.items[0].text == prepared.items[1].text == "A。"


def test_overview_whole_unit_sentence_id_passthrough() -> None:
    zone_match_bundle = _zone_match_bundle(
        table_blocks=[
            {
                "block_id": "T0001",
                "kind": "table",
                "heading_path": ["表格"],
                "analysis_text": "表格正文",
            }
        ],
    )
    analysis_bundle = _analysis_bundle_for_zone_match(zone_match_bundle)
    for block in analysis_bundle["table_blocks"]:
        if block["block_id"] == "T0001":
            block["sentences"] = [
                {"sentence_id": "T0001:S001", "analysis_text": "表格正文"},
            ]
    prepared = prepare_overview_source_items(
        materialize_projection_sources(
            zone_match_bundle=zone_match_bundle,
            analysis_bundle=analysis_bundle,
        )
    )

    assert prepared.items[0].sentence_id == "T0001:S001"


def test_overview_prompt_alias_round_trips_to_canonical_sentence_id() -> None:
    zone_match_bundle = _zone_with_block("C0001", analysis_text="安全性。")
    analysis_bundle = _analysis_bundle_with_blocks(
        [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "安全性。",
                "sentences": [
                    {"sentence_id": "C0005:S003", "analysis_text": "安全性。"},
                ],
            }
        ]
    )
    prepared = prepare_overview_source_items(
        materialize_projection_sources(
            zone_match_bundle=zone_match_bundle,
            analysis_bundle=analysis_bundle,
        )
    )
    prompt_json = json.loads(build_overview_prompt_input_json(prepared))
    assert prompt_json[0]["source_items"][0]["source_id"] == "O001"

    projection_input = _projection_input(zone_match_bundle)
    projection_input = FilterOutputProjectionInput(
        filter_job_id=projection_input.filter_job_id,
        doc_id=projection_input.doc_id,
        file_hash=projection_input.file_hash,
        zone_key=projection_input.zone_key,
        zone_match_bundle=projection_input.zone_match_bundle,
        projection_sources=materialize_projection_sources(
            zone_match_bundle=zone_match_bundle,
            analysis_bundle=analysis_bundle,
        ),
    )
    result = assemble_overview_projection_result(
        projection_input=projection_input,
        prepared=prepared,
        assessments=(
            ValidatedOverviewAssessment(
                prompt_alias="O001",
                content_modules=("clinical_safety",),
            ),
        ),
        target_semantic_module_id="clinical_safety",
    )
    source_ref = result.semantic_outcomes[0].source_refs[0].refs
    assert source_ref["sentence_id"] == "C0005:S003"
    assert "char_start" not in source_ref
    assert "source_item_index" not in source_ref


def test_direct_semantic_output_unchanged_for_fixture_profile() -> None:
    profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    zone_match_bundle, _, _, analysis_bundle = _filter_artifacts_for_profile(profile)
    projection_input = _projection_input_for_profile(profile, zone_match_bundle)
    before = run_project_filter_output(
        projection_input=FilterOutputProjectionInput(
            filter_job_id=projection_input.filter_job_id,
            doc_id=projection_input.doc_id,
            file_hash=projection_input.file_hash,
            zone_key=projection_input.zone_key,
            zone_match_bundle=projection_input.zone_match_bundle,
            projection_sources=materialize_projection_sources(
                zone_match_bundle=zone_match_bundle,
                analysis_bundle=analysis_bundle,
            ),
        ),
        analysis_bundle=analysis_bundle,
        job=_resolved_direct_job(profile),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )
    assert before.projected_sources
    assert all(
        source.semantic_module_id == "clinical_safety"
        for source in before.projected_sources
    )
