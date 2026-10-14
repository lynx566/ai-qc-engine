from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dataclasses import dataclass

from core.filtering.block_universe import BlockUniverse
from core.filtering.heading_zone import HeadingZoneStrategy
from core.filtering.jobs import ResolvedFilterJob
from core.filtering.registry import (
    DEFAULT_FILTER_STRATEGY_ID,
    resolve_filter_strategy,
    resolve_filter_strategy_for_config,
    strategy_id_from_zone_config,
)
from core.filtering.strategies import FilterContext
from steps.filter import extract_zones_from_bundle
from tests.filter_test_helpers import resolved_filter_job
from plugins.clinical_trial_doc.filter_profiles.csr.clinical_safety_zh import (
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.dsur.clinical_safety_zh import (
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)


def _heading(block_id: str, text: str, *, level: int, stripped: str | None = None) -> dict:
    return {
        "block_id": block_id,
        "kind": "heading",
        "text": text,
        "doc_order_index": 0,
        "meta": {
            "heading_level": level,
            "heading_text_stripped": stripped or text,
        },
    }


def _paragraph(block_id: str, text: str, *, doc_order_index: int) -> dict:
    return {
        "block_id": block_id,
        "kind": "paragraph",
        "text": text,
        "doc_order_index": doc_order_index,
    }


def _analysis_bundle(**groups: list[dict]) -> dict:
    return {
        "doc_id": "doc_001",
        "file_name": "doc_001.docx",
        "source_type": "docx",
        "front_matter_blocks": groups.get("front_matter_blocks", []),
        "content_blocks": groups.get("content_blocks", []),
        "table_blocks": groups.get("table_blocks", []),
        "format_blocks": groups.get("format_blocks", []),
    }


def test_block_universe_expands_four_groups() -> None:
    universe = BlockUniverse.from_analysis_bundle(
        _analysis_bundle(
            front_matter_blocks=[{"block_id": "M0001", "kind": "toc", "doc_order_index": 0}],
            content_blocks=[{"block_id": "C0001", "kind": "paragraph", "doc_order_index": 1}],
            table_blocks=[{"block_id": "T0001", "kind": "table", "doc_order_index": 2}],
            format_blocks=[{"block_id": "F0001", "kind": "header", "doc_order_index": 3}],
        )
    )

    assert len(universe.front_matter_blocks) == 1
    assert len(universe.content_blocks) == 1
    assert len(universe.table_blocks) == 1
    assert len(universe.format_blocks) == 1
    assert [b["block_id"] for b in universe.all_blocks_by_doc_order] == [
        "M0001",
        "C0001",
        "T0001",
        "F0001",
    ]
    assert set(universe.blocks_by_id) == {"M0001", "C0001", "T0001", "F0001"}


def test_zone_config_without_strategy_id_defaults_to_heading_zone() -> None:
    @dataclass(frozen=True)
    class LegacyZoneConfig:
        heading_terms: tuple[str, ...] = ("安全性",)
        heading_match_mode: str = "contains"

    legacy = LegacyZoneConfig()
    assert strategy_id_from_zone_config(legacy) == DEFAULT_FILTER_STRATEGY_ID
    strategy = resolve_filter_strategy_for_config(legacy)
    assert strategy.strategy_id == "heading_zone"


def test_clinical_safety_zone_configs_declare_heading_zone_strategy() -> None:
    for config in (
        IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
        CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
        DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    ):
        assert config.strategy_id == "heading_zone"
        assert resolve_filter_strategy_for_config(config).strategy_id == "heading_zone"


def test_resolve_filter_strategy_unknown_raises() -> None:
    with pytest.raises(KeyError, match="Unknown filter strategy 'nonexistent_strategy'"):
        resolve_filter_strategy("nonexistent_strategy")


def test_resolve_filter_strategy_for_config_unknown_strategy_id_raises() -> None:
    @dataclass(frozen=True)
    class UnknownStrategyConfig:
        strategy_id: str = "unknown_strategy"

    with pytest.raises(KeyError, match="Unknown filter strategy 'unknown_strategy'"):
        resolve_filter_strategy_for_config(UnknownStrategyConfig())


def test_heading_zone_excludes_front_matter_and_format_blocks() -> None:
    strategy = HeadingZoneStrategy()
    universe = BlockUniverse.from_analysis_bundle(
        _analysis_bundle(
            front_matter_blocks=[
                {
                    "block_id": "M0001",
                    "kind": "heading",
                    "text": "安全性",
                    "doc_order_index": 0,
                    "meta": {"heading_level": 1, "heading_text_stripped": "安全性"},
                }
            ],
            content_blocks=[
                _heading("h1", "7 安全性", level=1, stripped="安全性",),
                _paragraph("p1", "body", doc_order_index=1),
            ],
            format_blocks=[
                {
                    "block_id": "F0001",
                    "kind": "heading",
                    "text": "安全性",
                    "doc_order_index": 99,
                    "meta": {"heading_level": 1, "heading_text_stripped": "安全性"},
                }
            ],
        )
    )

    result = strategy.extract(
        block_universe=universe,
        zone_config=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
        context=FilterContext(),
    )

    assert result.selected_block_ids == frozenset({"h1", "p1"})
    assert "M0001" not in result.selected_block_ids
    assert "F0001" not in result.selected_block_ids


def test_resolved_filter_job_is_frozen_and_preserves_identities() -> None:
    config = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    strategy = resolve_filter_strategy_for_config(config)
    job = ResolvedFilterJob(config=config, strategy=strategy)

    assert job.config is config
    assert job.strategy is strategy

    with pytest.raises(AttributeError):
        job.config = config  # type: ignore[misc]


def test_extract_zones_from_bundle_uses_injected_strategy() -> None:
    bundle = _analysis_bundle(
        content_blocks=[
            _heading("h1", "7 安全性", level=1, stripped="安全性"),
            _paragraph("p1", "body", doc_order_index=1),
        ]
    )
    strategy = resolve_filter_strategy_for_config(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH)
    job = ResolvedFilterJob(
        config=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
        strategy=strategy,
    )

    result = extract_zones_from_bundle(bundle, job)

    assert result["matched_zone_count"] == 1
    assert result["matched_zones"][0]["match"]["matched_heading_block_id"] == "h1"


def test_extract_zones_from_bundle_records_filter_strategy_metadata() -> None:
    bundle = _analysis_bundle(
        content_blocks=[
            _heading("h1", "7 安全性", level=1, stripped="安全性"),
            _paragraph("p1", "body", doc_order_index=1),
        ]
    )

    result = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert result["resolved_filter_strategy_id"] == "heading_zone"
    assert "profile_strategy_ids" not in result
    assert "profile_strategy_id" not in result


def test_heading_zone_does_not_collect_table_caption_or_note_in_zone_blocks() -> None:
    strategy = HeadingZoneStrategy()
    universe = BlockUniverse.from_analysis_bundle(
        _analysis_bundle(
            content_blocks=[
                _heading("h1", "7 安全性", level=1, stripped="安全性"),
                {
                    "block_id": "cap1",
                    "kind": "table_caption",
                    "text": "表1 不良事件",
                    "doc_order_index": 1,
                },
                _paragraph("p1", "body", doc_order_index=2),
                {
                    "block_id": "note1",
                    "kind": "table_note",
                    "text": "注：数据截至2023年",
                    "doc_order_index": 3,
                },
            ],
        )
    )

    result = strategy.extract(
        block_universe=universe,
        zone_config=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
        context=FilterContext(),
    )

    zone_block_ids = {b["block_id"] for b in result.matched_zones[0]["blocks"]}
    assert zone_block_ids == {"h1", "p1"}
    assert "cap1" not in zone_block_ids
    assert "note1" not in zone_block_ids
