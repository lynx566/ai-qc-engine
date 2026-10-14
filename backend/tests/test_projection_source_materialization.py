"""Projection source materialization from Filter selection + Prepare analysis."""

from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

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
    FilterOutputProjectionStepResult,
    ProjectionSourceBlock,
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.source_materialization import (
    materialize_projection_sources,
)
from steps.project_filter_output import run as run_project_filter_output
from tests.test_filter_output_projection_direct import (
    LINEAGE_FILE_HASH,
    _analysis_bundle_for_zone_match,
)

DOC_ID = "doc_test"
ZONE_KEY = "test_zone_zh"
FILTER_JOB_ID = "test_filter_job"


def _zone_match_bundle(
    *,
    blocks: list[dict[str, Any]] | None = None,
    table_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "doc_id": DOC_ID,
        "file_hash": LINEAGE_FILE_HASH,
        "zone_config_name": ZONE_KEY,
        "zone_config_version": "0.2.0",
        "language": "zh",
        "resolved_filter_strategy_id": "heading_zone",
        "matched_zone_count": 1,
        "matched_zones": [
            {
                "zone_id": "Z0001",
                "match": {"match_type": "heading_contains"},
                "blocks": blocks or [],
                "table_blocks": table_blocks or [],
            }
        ],
    }


def _analysis_bundle(
    *,
    content_blocks: list[dict[str, Any]],
    table_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_analysis_bundle_artifact(
        {
            "doc_id": DOC_ID,
            "file_name": "sample.docx",
            "source_type": "docx",
            "file_hash": LINEAGE_FILE_HASH,
            "analysis_bundle_id": "prepare_analysis_materialization_test",
            "analysis_bundle_contract": ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
            "analysis_bundle_schema_version": ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
            "stage": "prepare_analysis",
            "pipeline": ["extract", "prepare_analysis"],
            "privacy_enabled": True,
            "privacy_transforms": {"after_extract": {"applied": True}},
            "front_matter_blocks": [],
            "content_blocks": content_blocks,
            "table_blocks": table_blocks or [],
            "format_blocks": [],
        }
    )


def test_basic_fan_in_materializes_selected_blocks() -> None:
    zone_match_bundle = _zone_match_bundle(
        blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "heading_path": ["安全性"],
                "analysis_text": "zone fallback text",
            },
            {
                "block_id": "C0002",
                "kind": "paragraph",
                "heading_path": ["安全性", "概述"],
                "analysis_text": "ignored",
            },
        ]
    )
    analysis_bundle = _analysis_bundle(
        content_blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "canonical block one",
                "sentences": [
                    {
                        "sentence_id": "C0001:S001",
                        "analysis_text": "canonical sentence one",
                    }
                ],
            },
            {
                "block_id": "C0002",
                "kind": "paragraph",
                "analysis_text": "canonical block two",
                "sentences": [
                    {
                        "sentence_id": "C0002:S001",
                        "analysis_text": "canonical sentence two",
                    }
                ],
            },
        ]
    )

    sources = materialize_projection_sources(
        zone_match_bundle=zone_match_bundle,
        analysis_bundle=analysis_bundle,
    )

    assert len(sources) == 2
    assert sources[0].block_id == "C0001"
    assert sources[1].block_id == "C0002"
    assert sources[0].zone_id == "Z0001"
    assert sources[0].source_group == "blocks"
    assert sources[0].heading_path == ("安全性",)


def test_analysis_text_renamed_to_text_without_dual_authority() -> None:
    zone_match_bundle = _zone_match_bundle(
        blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "heading_path": ["摘要"],
                "analysis_text": "zone text",
            }
        ]
    )
    analysis_bundle = _analysis_bundle(
        content_blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "prepare block text",
                "sentences": [
                    {
                        "sentence_id": "C0001:S001",
                        "analysis_text": "prepare sentence text",
                    }
                ],
            }
        ]
    )

    source = materialize_projection_sources(
        zone_match_bundle=zone_match_bundle,
        analysis_bundle=analysis_bundle,
    )[0]

    assert source.text == "prepare block text"
    assert source.sentences[0].text == "prepare sentence text"
    assert "analysis_text" not in fields(source)
    assert "analysis_text" not in fields(source.sentences[0])


def test_sentence_id_exact_passthrough() -> None:
    zone_match_bundle = _zone_match_bundle(
        blocks=[{"block_id": "C0005", "kind": "paragraph", "analysis_text": "x"}]
    )
    analysis_bundle = _analysis_bundle(
        content_blocks=[
            {
                "block_id": "C0005",
                "kind": "paragraph",
                "analysis_text": "whole unit",
                "sentences": [
                    {"sentence_id": "C0005:S001", "analysis_text": "whole unit"}
                ],
            }
        ]
    )

    source = materialize_projection_sources(
        zone_match_bundle=zone_match_bundle,
        analysis_bundle=analysis_bundle,
    )[0]

    assert source.sentences[0].sentence_id == "C0005:S001"


def test_block_and_sentence_ordering_preserved() -> None:
    zone_match_bundle = _zone_match_bundle(
        blocks=[
            {"block_id": "C0003", "kind": "paragraph", "analysis_text": "third"},
            {"block_id": "C0001", "kind": "paragraph", "analysis_text": "first"},
            {"block_id": "C0002", "kind": "paragraph", "analysis_text": "second"},
        ]
    )
    analysis_bundle = _analysis_bundle(
        content_blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "first",
                "sentences": [
                    {"sentence_id": "C0001:S001", "analysis_text": "first"},
                ],
            },
            {
                "block_id": "C0002",
                "kind": "paragraph",
                "analysis_text": "second",
                "sentences": [
                    {"sentence_id": "C0002:S002", "analysis_text": "second-b"},
                    {"sentence_id": "C0002:S001", "analysis_text": "second-a"},
                ],
            },
            {
                "block_id": "C0003",
                "kind": "paragraph",
                "analysis_text": "third",
                "sentences": [
                    {"sentence_id": "C0003:S001", "analysis_text": "third"},
                ],
            },
        ]
    )

    sources = materialize_projection_sources(
        zone_match_bundle=zone_match_bundle,
        analysis_bundle=analysis_bundle,
    )

    assert [source.block_id for source in sources] == ["C0003", "C0001", "C0002"]
    assert [sentence.sentence_id for sentence in sources[2].sentences] == [
        "C0002:S002",
        "C0002:S001",
    ]


def test_duplicate_text_with_distinct_sentence_ids_preserved() -> None:
    zone_match_bundle = _zone_match_bundle(
        blocks=[{"block_id": "C0001", "kind": "paragraph", "analysis_text": "x"}]
    )
    analysis_bundle = _analysis_bundle(
        content_blocks=[
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

    sentences = materialize_projection_sources(
        zone_match_bundle=zone_match_bundle,
        analysis_bundle=analysis_bundle,
    )[0].sentences

    assert len(sentences) == 2
    assert sentences[0] == sentences[1].__class__(
        sentence_id="C0001:S001",
        text="A。",
    )
    assert sentences[1].sentence_id == "C0001:S002"
    assert sentences[0].text == sentences[1].text == "A。"


def test_whole_unit_sentence_id_preserved() -> None:
    zone_match_bundle = _zone_match_bundle(
        blocks=[{"block_id": "C0005", "kind": "paragraph", "analysis_text": "x"}]
    )
    analysis_bundle = _analysis_bundle(
        content_blocks=[
            {
                "block_id": "C0005",
                "kind": "paragraph",
                "analysis_text": "whole",
                "sentences": [
                    {"sentence_id": "C0005:S001", "analysis_text": "whole"},
                ],
            }
        ]
    )

    sentence = materialize_projection_sources(
        zone_match_bundle=zone_match_bundle,
        analysis_bundle=analysis_bundle,
    )[0].sentences[0]

    assert sentence.sentence_id == "C0005:S001"


def test_missing_selected_block_fails_without_fallback() -> None:
    zone_match_bundle = _zone_match_bundle(
        blocks=[{"block_id": "C9999", "kind": "paragraph", "analysis_text": "fallback"}]
    )
    analysis_bundle = _analysis_bundle(
        content_blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "analysis_text": "other",
                "sentences": [
                    {"sentence_id": "C0001:S001", "analysis_text": "other"},
                ],
            }
        ]
    )

    with pytest.raises(ValueError, match="C9999"):
        materialize_projection_sources(
            zone_match_bundle=zone_match_bundle,
            analysis_bundle=analysis_bundle,
        )


class _RecordingFacade:
    def __init__(self) -> None:
        self.received_input: FilterOutputProjectionInput | None = None

    def project(
        self,
        *,
        projection_input: FilterOutputProjectionInput,
        job: ResolvedFilterOutputProjectionJob,
    ) -> FilterOutputProjectionStepResult:
        self.received_input = projection_input
        return FilterOutputProjectionStepResult(
            filter_job_id=projection_input.filter_job_id,
            doc_id=projection_input.doc_id,
            file_hash=projection_input.file_hash,
            zone_key=projection_input.zone_key,
        )


def test_facade_receives_materialized_projection_sources() -> None:
    zone_match_bundle = _zone_match_bundle(
        blocks=[
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "heading_path": ["摘要"],
                "analysis_text": "zone",
            }
        ]
    )
    analysis_bundle = _analysis_bundle_for_zone_match(zone_match_bundle)
    facade = _RecordingFacade()

    run_project_filter_output(
        projection_input=FilterOutputProjectionInput(
            filter_job_id=FILTER_JOB_ID,
            doc_id=DOC_ID,
            file_hash=LINEAGE_FILE_HASH,
            zone_key=ZONE_KEY,
            zone_match_bundle=zone_match_bundle,
        ),
        analysis_bundle=analysis_bundle,
        job=ResolvedFilterOutputProjectionJob(
            filter_job_id=FILTER_JOB_ID,
            strategy_id="test_strategy",
        ),
        facade=facade,
    )

    assert facade.received_input is not None
    assert len(facade.received_input.projection_sources) == 1
    source = facade.received_input.projection_sources[0]
    assert isinstance(source, ProjectionSourceBlock)
    assert source.text == "zone"
    assert source.sentences[0].sentence_id == "C0001:S001"
