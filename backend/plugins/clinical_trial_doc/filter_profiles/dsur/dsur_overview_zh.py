"""DSUR Chinese overview Filter config (heading-based recall)."""

from __future__ import annotations

from plugins.clinical_trial_doc.filter_profiles.common.models import (
    ClinicalTrialFilterConfig,
    HeadingFilterPolicy,
)

_DSUR_OVERVIEW_POLICY_ZH = HeadingFilterPolicy(
    heading_match_mode="contains",
    required_heading_level=None,
    heading_terms=(
        "执行概要",
        "摘要",
        "前言",
        "结论",
    ),
    exclude_heading_terms=(
        "论文摘要",
    ),
)

DSUR_OVERVIEW_FILTER_PROFILE_ZH = ClinicalTrialFilterConfig(
    zone_config_name="dsur_overview_zh",
    zone_config_version="0.2.0",
    filter_job_id="dsur_overview",
    language="zh",
    strategy_id="heading_zone",
    policy=_DSUR_OVERVIEW_POLICY_ZH,
)
