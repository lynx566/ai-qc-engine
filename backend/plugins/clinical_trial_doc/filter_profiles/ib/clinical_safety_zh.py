"""IB Chinese clinical-safety Filter config (heading-based recall)."""

from __future__ import annotations

from plugins.clinical_trial_doc.filter_profiles.common.models import (
    ClinicalTrialFilterConfig,
    HeadingFilterPolicy,
)

_IB_CLINICAL_SAFETY_POLICY_ZH = HeadingFilterPolicy(
    heading_match_mode="contains",
    required_heading_level=None,
    heading_terms=(
        "安全性",
        "不良事件",
        "不良反应",
        "重要风险",
        "风险评估",
        "风险评价",
    ),
    exclude_heading_terms=(
        "非临床",
        "药理",
        "药效",
        "毒理",
        "遗传毒性",
        "生殖毒性",
        "重复给药毒性",
        "单次给药毒性",
        "质量安全",
        "数据安全",
        "同类药",
    ),
)

IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH = ClinicalTrialFilterConfig(
    zone_config_name="ib_clinical_safety_zh",
    zone_config_version="0.2.0",
    filter_job_id="ib_clinical_safety",
    language="zh",
    strategy_id="heading_zone",
    policy=_IB_CLINICAL_SAFETY_POLICY_ZH,
)
