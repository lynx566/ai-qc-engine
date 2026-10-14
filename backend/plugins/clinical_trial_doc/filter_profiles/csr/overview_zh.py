"""CSR Chinese overview Filter config (heading-based recall)."""

from __future__ import annotations

from plugins.clinical_trial_doc.filter_profiles.common.models import (
    ClinicalTrialFilterConfig,
    HeadingFilterPolicy,
)

_CSR_OVERVIEW_POLICY_ZH = HeadingFilterPolicy(
    heading_match_mode="contains",
    required_heading_level=1,
    heading_terms=(
        "概要",
        "摘要",
        "结论",
    ),
)

CSR_OVERVIEW_FILTER_PROFILE_ZH = ClinicalTrialFilterConfig(
    zone_config_name="csr_overview_zh",
    zone_config_version="0.2.0",
    filter_job_id="csr_overview",
    language="zh",
    strategy_id="heading_zone",
    policy=_CSR_OVERVIEW_POLICY_ZH,
)
