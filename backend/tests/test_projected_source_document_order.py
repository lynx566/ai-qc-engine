"""Document-order merge for projected-source fan-in before Route."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.block_position import block_position_key, blocks_by_id
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionStepResult,
    ProjectedSource,
)
from operations.filter_output_projection.document_order import (
    sort_projected_sources_by_document_position,
)
from operations.filter_output_projection.fan_in import (
    ProjectionFanInInput,
    select_projected_sources_for_semantic_module,
)
from operations.filter_output_projection.projected_sentence import (
    block_level_source_ref,
)
from plugins.clinical_trial_doc.filter_output_projection.document_anchor import (
    projected_source_document_anchor,
)
from tests.projection_test_helpers import (
    assembled_projected_source,
    projected_sentence,
    raw_projected_source,
)

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _content_block(block_id: str, *, order: int, heading_path: list[str] | None = None) -> dict:
    return {
        "block_id": block_id,
        "kind": "paragraph",
        "order": order,
        "heading_path": heading_path or [],
    }


def _table_block(block_id: str, *, doc_order_index: int) -> dict:
    return {
        "block_id": block_id,
        "kind": "table",
        "doc_order_index": doc_order_index,
        "heading_path": ["19.重要发现总结"],
    }


def _minimal_manifest(*blocks: dict) -> dict:
    content = [b for b in blocks if b.get("kind") != "table"]
    tables = [b for b in blocks if b.get("kind") == "table"]
    return {
        "block_manifest_id": "block_manifest_test",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": content,
        "table_blocks": tables,
    }


def _raw_source(
    block_id: str,
    *,
    filter_job_id: str = "dsur_clinical_safety",
) -> ProjectedSource:
    return raw_projected_source(
        semantic_module_id="clinical_safety",
        block_id=block_id,
        lineage={"filter_job_id": filter_job_id, "zone_key": "dsur_clinical_safety_zh"},
    )


def _assembled_source(
    *,
    substantive_block_id: str,
    substantive_item_index: str = "1",
    context_block_id: str | None = None,
    filter_job_id: str = "dsur_overview",
) -> ProjectedSource:
    sentences = [
        projected_sentence(
            sentence_id=f"{substantive_block_id}:S{substantive_item_index.zfill(3)}",
            text="正文",
            source_block_id=substantive_block_id,
        )
    ]
    if context_block_id is not None:
        sentences.insert(
            0,
            projected_sentence(
                sentence_id=f"{context_block_id}:S001",
                text="上下文",
                source_block_id=context_block_id,
            ),
        )
    return assembled_projected_source(
        semantic_module_id="clinical_safety",
        sentences=tuple(sentences),
        heading_path=["执行概要"],
        lineage={"filter_job_id": filter_job_id, "zone_key": "dsur_overview_zh"},
        source_refs=(
            block_level_source_ref(block_id=substantive_block_id, source_group="blocks"),
            *(
                (
                    block_level_source_ref(
                        block_id=context_block_id,
                        source_group="blocks",
                    ),
                )
                if context_block_id is not None
                else ()
            ),
        ),
    )


def _sort_key(manifest: dict, source: ProjectedSource) -> tuple:
    return projected_source_document_anchor(
        source,
        blocks_by_id=blocks_by_id(manifest),
    )


def _sorted_block_ids(manifest: dict, sources: tuple[ProjectedSource, ...]) -> list[str]:
    sorted_sources = sort_projected_sources_by_document_position(
        sources,
        resolve_document_anchor=lambda source: _sort_key(manifest, source),
    )
    ids: list[str] = []
    for source in sorted_sources:
        if source.sentences:
            ids.append(source.sentences[0].source_block_id)
        else:
            ids.append(source.source_refs[0].refs["block_id"])
    return ids


def _fan_in_input(
    *,
    filter_job_id: str,
    zone_key: str,
    projected_sources: tuple[ProjectedSource, ...],
) -> ProjectionFanInInput:
    return ProjectionFanInInput(
        step_result=FilterOutputProjectionStepResult(
            filter_job_id=filter_job_id,
            doc_id="doc_test",
            file_hash=LINEAGE_FILE_HASH,
            zone_key=zone_key,
            projected_sources=projected_sources,
        ),
        filter_output_projection_bundle_id=f"bundle_{filter_job_id}",
    )


def test_raw_sources_sorted_by_block_manifest_document_position() -> None:
    manifest = _minimal_manifest(
        _content_block("C0010", order=10),
        _content_block("C0005", order=5),
        _content_block("C0008", order=8),
    )
    sources = (
        _raw_source("C0010"),
        _raw_source("C0005"),
        _raw_source("C0008"),
    )
    assert _sorted_block_ids(manifest, sources) == ["C0005", "C0008", "C0010"]


def test_assembled_source_uses_substantive_block_not_earlier_context() -> None:
    manifest = _minimal_manifest(
        _content_block("C0004", order=4, heading_path=["执行概要"]),
        _content_block("C0006", order=6, heading_path=["执行概要"]),
    )
    source = _assembled_source(substantive_block_id="C0006", context_block_id="C0004")
    anchor = projected_source_document_anchor(source, blocks_by_id=blocks_by_id(manifest))
    assert anchor[0] == block_position_key(manifest["blocks"][1])
    assert anchor != (block_position_key(manifest["blocks"][0]), 1)


def test_reversed_contributor_bundle_order_yields_same_document_traversal() -> None:
    manifest = _minimal_manifest(
        _content_block("C0006", order=6, heading_path=["执行概要"]),
        _content_block("C0014", order=14, heading_path=["3.报告周期内因安全性原因而采取的措施"]),
        _content_block("C0104", order=104, heading_path=["20.结论"]),
    )
    overview = (_assembled_source(substantive_block_id="C0006"), _assembled_source(substantive_block_id="C0104"))
    safety = (_raw_source("C0014"),)

    forward = _sorted_block_ids(manifest, safety + overview)
    reversed_order = _sorted_block_ids(manifest, overview + safety)
    assert forward == reversed_order == ["C0006", "C0014", "C0104"]


def test_projection_input_refs_keep_contributor_order() -> None:
    overview = (_assembled_source(substantive_block_id="C0006"),)
    safety = (_raw_source("C0014"),)

    safety_first = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(
            _fan_in_input(
                filter_job_id="dsur_clinical_safety",
                zone_key="dsur_clinical_safety_zh",
                projected_sources=safety,
            ),
            _fan_in_input(
                filter_job_id="dsur_overview",
                zone_key="dsur_overview_zh",
                projected_sources=overview,
            ),
        ),
        semantic_module_id="clinical_safety",
    )
    overview_first = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(
            _fan_in_input(
                filter_job_id="dsur_overview",
                zone_key="dsur_overview_zh",
                projected_sources=overview,
            ),
            _fan_in_input(
                filter_job_id="dsur_clinical_safety",
                zone_key="dsur_clinical_safety_zh",
                projected_sources=safety,
            ),
        ),
        semantic_module_id="clinical_safety",
    )

    assert [ref.filter_job_id for ref in safety_first.projection_input_refs] == [
        "dsur_clinical_safety",
        "dsur_overview",
    ]
    assert [ref.filter_job_id for ref in overview_first.projection_input_refs] == [
        "dsur_overview",
        "dsur_clinical_safety",
    ]


def test_exact_position_collision_preserves_input_order() -> None:
    manifest = _minimal_manifest(_content_block("C0005", order=5))
    first = _raw_source("C0005", filter_job_id="job_a")
    second = _assembled_source(substantive_block_id="C0005", filter_job_id="job_b")
    sorted_sources = sort_projected_sources_by_document_position(
        (first, second),
        resolve_document_anchor=lambda source: _sort_key(manifest, source),
    )
    assert sorted_sources == (first, second)


def test_route_stage_applies_document_order_before_executor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from runtime.projected_source_route_stage import run_projected_source_route_stage
    from tests.route_test_fixtures import _minimal_doc_meta

    manifest = _minimal_manifest(
        _content_block("C0006", order=6),
        _content_block("C0014", order=14),
    )
    sources = (_raw_source("C0014"), _assembled_source(substantive_block_id="C0006"))
    captured: dict[str, tuple[ProjectedSource, ...]] = {}

    def _capture(**kwargs):
        captured["projected_sources"] = tuple(kwargs["projected_sources"])
        from steps.route import RouteStepResult

        return RouteStepResult(
            doc_id="doc_test",
            zone_key="",
            route_artifacts={
                "route_counts": {"aggregate": 0, "table": 0, "case": 0, "unknown": 0},
                "routing_manifest": {
                    "doc_id": "doc_test",
                    "source_refs": {"projection_input_refs": []},
                    "route_counts": {"aggregate": 0, "table": 0, "case": 0, "unknown": 0},
                    "unit_count": 0,
                    "unknown_unit_count": 0,
                },
                "routed_bundles": {
                    "aggregate": {
                        "routed_unit_bundle_id": "bundle_aggregate",
                        "units": [],
                    },
                    "table": {
                        "routed_unit_bundle_id": "bundle_table",
                        "units": [],
                    },
                    "case": {
                        "routed_unit_bundle_id": "bundle_case",
                        "units": [],
                    },
                    "unknown": {
                        "routed_unit_bundle_id": "bundle_unknown",
                        "units": [],
                    },
                },
            },
        )

    monkeypatch.setattr(
        "runtime.projected_source_route_stage.run_from_projected_sources",
        _capture,
    )

    manifest_path = tmp_path / "block_manifest.json"
    doc_meta_path = tmp_path / "doc_meta_bundle.json"
    analysis_path = tmp_path / "analysis_bundle.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    doc_meta_path.write_text(json.dumps(_minimal_doc_meta()), encoding="utf-8")
    analysis_path.write_text(
        json.dumps(
            {
                "analysis_bundle_id": "analysis_test",
                "doc_id": "doc_test",
                "file_hash": LINEAGE_FILE_HASH,
            }
        ),
        encoding="utf-8",
    )

    run_projected_source_route_stage(
        projected_sources=sources,
        semantic_module_id="clinical_safety",
        block_manifest_path=manifest_path,
        doc_meta_bundle_path=doc_meta_path,
        analysis_bundle_path=analysis_path,
        output_dir=tmp_path / "route_out",
        projection_doc_id="doc_test",
        projection_file_hash=LINEAGE_FILE_HASH,
        projection_input_refs=(
            {
                "filter_output_projection_bundle_id": "bundle_a",
                "filter_job_id": "dsur_clinical_safety",
                "zone_key": "dsur_clinical_safety_zh",
            },
        ),
        route_executor=lambda **_: None,
    )

    ordered = captured["projected_sources"]
    assert ordered[0].source_refs[0].refs["block_id"] == "C0006"
    assert ordered[1].source_refs[0].refs["block_id"] == "C0014"
