"""Contract tests for Filter config vs executable HeadingFilterPolicy split."""

from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.filtering.block_universe import BlockUniverse
from core.filtering.heading_zone import HeadingZoneStrategy
from core.filtering.registry import resolve_filter_strategy_for_config
from core.filtering.strategies import FilterContext
from steps.filter import extract_zones_from_bundle
from plugins.clinical_trial_doc.filter_profiles.common.models import (
    ClinicalTrialFilterConfig,
    HeadingFilterPolicy,
)
from plugins.clinical_trial_doc.filter_profiles.csr.clinical_safety_zh import (
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.csr.overview_zh import (
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.dsur.clinical_safety_zh import (
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.dsur.dsur_overview_zh import (
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)
from tests.filter_test_helpers import resolved_filter_job

_POLICY_FIELD_NAMES = frozenset(
    {
        "heading_match_mode",
        "heading_terms",
        "exclude_heading_terms",
        "required_heading_level",
    }
)

_CONFIG_METADATA_FIELD_NAMES = frozenset(
    {
        "zone_config_name",
        "zone_config_version",
        "filter_job_id",
        "language",
        "strategy_id",
        "policy",
    }
)

_REMOVED_CONFIG_FIELD_NAMES = frozenset(
    {
        "doc_type",
        "zone_role",
        "target_domain",
    }
)

_INSTALLED_CONFIGS = (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    IB_OVERVIEW_FILTER_PROFILE_ZH,
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
)

_INSTALLED_PROFILE_VERSION = "0.2.0"


def _heading(
    block_id: str,
    text: str,
    *,
    level: int,
    stripped: str | None = None,
    doc_order_index: int | None = None,
) -> dict:
    block = {
        "block_id": block_id,
        "kind": "heading",
        "text": text,
        "meta": {
            "heading_level": level,
            "heading_text_stripped": stripped or text,
        },
    }
    if doc_order_index is not None:
        block["doc_order_index"] = doc_order_index
    return block


def _paragraph(
    block_id: str,
    text: str,
    *,
    doc_order_index: int | None = None,
) -> dict:
    block = {"block_id": block_id, "kind": "paragraph", "text": text}
    if doc_order_index is not None:
        block["doc_order_index"] = doc_order_index
    return block


def _bundle(*blocks: dict) -> dict:
    return {
        "doc_id": "doc_001",
        "file_name": "doc_001.docx",
        "source_type": "docx",
        "content_blocks": list(blocks),
        "table_blocks": [],
    }


def test_heading_filter_policy_fields_are_execution_only() -> None:
    policy_fields = {field.name for field in fields(HeadingFilterPolicy)}
    assert policy_fields == _POLICY_FIELD_NAMES


def test_clinical_trial_filter_config_owns_metadata_and_policy() -> None:
    config_fields = {field.name for field in fields(ClinicalTrialFilterConfig)}
    assert config_fields == _CONFIG_METADATA_FIELD_NAMES
    assert config_fields.isdisjoint(_REMOVED_CONFIG_FIELD_NAMES)
    assert "notes" not in config_fields


def test_policy_fields_not_on_installed_config() -> None:
    for name in _POLICY_FIELD_NAMES:
        assert not hasattr(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH, name)


def test_metadata_fields_not_on_executable_policy() -> None:
    policy = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.policy
    for name in (
        "zone_config_name",
        "zone_config_version",
        "filter_job_id",
        "language",
        "strategy_id",
        "notes",
        *_REMOVED_CONFIG_FIELD_NAMES,
    ):
        assert not hasattr(policy, name)


def test_strategy_id_not_on_heading_filter_policy() -> None:
    policy = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.policy
    assert not hasattr(policy, "strategy_id")
    assert IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.strategy_id == "heading_zone"
    assert (
        resolve_filter_strategy_for_config(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH).strategy_id
        == "heading_zone"
    )


def test_matching_depends_only_on_policy_not_config_metadata() -> None:
    shared_policy = HeadingFilterPolicy(
        heading_match_mode="contains",
        required_heading_level=None,
        heading_terms=("安全性",),
        exclude_heading_terms=(),
    )
    config_a = ClinicalTrialFilterConfig(
        zone_config_name="ib_clinical_safety_zh",
        zone_config_version="0.2.0",
        filter_job_id="ib_clinical_safety",
        language="zh",
        strategy_id="heading_zone",
        policy=shared_policy,
    )
    config_b = ClinicalTrialFilterConfig(
        zone_config_name="csr_overview_zh",
        zone_config_version="9.9.9",
        filter_job_id="csr_overview",
        language="zh",
        strategy_id="heading_zone",
        policy=shared_policy,
    )

    bundle = _bundle(
        _heading("h1", "7 安全性", level=1, stripped="安全性"),
        _paragraph("p1", "body", doc_order_index=1),
    )
    strategy = HeadingZoneStrategy()
    block_universe = BlockUniverse.from_analysis_bundle(bundle)

    result_a = strategy.extract(
        block_universe=block_universe,
        zone_config=config_a,
        context=FilterContext(),
    )
    result_b = strategy.extract(
        block_universe=block_universe,
        zone_config=config_b,
        context=FilterContext(),
    )

    assert result_a.selected_block_ids == result_b.selected_block_ids == frozenset(
        {"h1", "p1"}
    )
    assert result_a.matched_zones[0]["zone_config_name"] == "ib_clinical_safety_zh"
    assert result_b.matched_zones[0]["zone_config_name"] == "csr_overview_zh"


def test_overview_uses_same_policy_type_as_clinical_safety() -> None:
    overview_policy = CSR_OVERVIEW_FILTER_PROFILE_ZH.policy
    assert isinstance(overview_policy, HeadingFilterPolicy)
    assert overview_policy.required_heading_level == 1
    assert overview_policy.heading_match_mode == "contains"
    assert isinstance(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.policy, HeadingFilterPolicy)


@pytest.mark.parametrize("config", _INSTALLED_CONFIGS)
def test_installed_config_is_clinical_trial_filter_config(config) -> None:
    assert isinstance(config, ClinicalTrialFilterConfig)
    assert isinstance(config.policy, HeadingFilterPolicy)


@pytest.mark.parametrize("config", _INSTALLED_CONFIGS)
def test_installed_profile_version_is_0_2_0(config) -> None:
    assert config.zone_config_version == _INSTALLED_PROFILE_VERSION
    for name in _REMOVED_CONFIG_FIELD_NAMES:
        assert not hasattr(config, name)


def test_ib_overview_profile_behavior_unchanged() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", "1 摘要", level=1, stripped="摘要"),
            _paragraph("p1", "summary body"),
            _heading("h2", "5.2.1 摘要", level=3, stripped="摘要"),
            _paragraph("p2", "nested summary"),
        ),
        resolved_filter_job(IB_OVERVIEW_FILTER_PROFILE_ZH),
    )

    assert result["matched_zone_count"] == 1
    zone = result["matched_zones"][0]
    assert zone["zone_config_name"] == "ib_overview_zh"
    assert zone["match"]["matched_heading_level"] == 1


def test_combined_ib_profiles_behavior_unchanged() -> None:
    bundle = _bundle(
        _heading("h1", "1 摘要", level=1, stripped="摘要"),
        _paragraph("p1", "summary body"),
        _heading("h2", "2.1 不良事件概要", level=2, stripped="不良事件概要"),
        _paragraph("p2", "detail via ae term, not summary"),
        _heading("h3", "5.2.1 临床安全性", level=3, stripped="临床安全性"),
        _paragraph("p3", "detail body"),
    )
    overview = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(IB_OVERVIEW_FILTER_PROFILE_ZH),
    )
    safety = extract_zones_from_bundle(
        bundle,
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert overview["matched_zone_count"] == 1
    assert safety["matched_zone_count"] == 1
    assert overview["matched_zones"][0]["zone_config_name"] == "ib_overview_zh"
    detail_zone = safety["matched_zones"][0]
    assert detail_zone["zone_config_name"] == "ib_clinical_safety_zh"
    assert detail_zone["match"]["matched_term"] == "不良事件"


def test_persisted_zone_match_metadata_keys_unchanged() -> None:
    result = extract_zones_from_bundle(
        _bundle(
            _heading("h1", "7 安全性", level=1, stripped="安全性"),
            _paragraph("p1", "body", doc_order_index=1),
        ),
        resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
    )

    assert result["zone_config_name"] == "ib_clinical_safety_zh"
    assert result["zone_config_version"] == _INSTALLED_PROFILE_VERSION
    assert result["language"] == "zh"
    assert result["resolved_filter_strategy_id"] == "heading_zone"
    assert "resolved_filter_strategy_ids" not in result
    assert "zone_config_names" not in result
    assert "zone_groups" not in result
    for name in _REMOVED_CONFIG_FIELD_NAMES:
        assert name not in result
        assert "target_domains" not in result

    zone = result["matched_zones"][0]
    for key in (
        "zone_config_name",
        "zone_config_version",
        "language",
    ):
        assert key in zone
    for name in _REMOVED_CONFIG_FIELD_NAMES:
        assert name not in zone
