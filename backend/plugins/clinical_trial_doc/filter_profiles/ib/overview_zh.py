"""IB Chinese overview Filter config (heading-based recall)."""

from __future__ import annotations

from plugins.clinical_trial_doc.filter_profiles.common.models import (
    ClinicalTrialFilterConfig,
    HeadingFilterPolicy,
)

_IB_OVERVIEW_POLICY_ZH = HeadingFilterPolicy(
    heading_match_mode="contains",
    required_heading_level=1,
    heading_terms=(
        "摘要",
        "概要",
        "概述",
        "研究者指南",
        "结论",
    ),
)

IB_OVERVIEW_FILTER_PROFILE_ZH = ClinicalTrialFilterConfig(
    zone_config_name="ib_overview_zh",
    zone_config_version="0.2.0",
    filter_job_id="ib_overview",
    language="zh",
    strategy_id="heading_zone",
    policy=_IB_OVERVIEW_POLICY_ZH,
)
