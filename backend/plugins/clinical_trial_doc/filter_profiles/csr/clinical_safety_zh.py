"""CSR Chinese clinical-safety Filter config (heading-based recall)."""

from __future__ import annotations

from plugins.clinical_trial_doc.filter_profiles.common.models import (
    ClinicalTrialFilterConfig,
    HeadingFilterPolicy,
)

_CSR_CLINICAL_SAFETY_POLICY_ZH = HeadingFilterPolicy(
    heading_match_mode="contains",
    required_heading_level=None,
    heading_terms=(
        "安全性",
        "不良事件",
        "不良反应",
        "死亡",
        "实验室检查",
        "生命体征",
        "心电图",
        "体格检查",
    ),
    exclude_heading_terms=(
        "非临床",
        "药理",
        "药效",
        "毒理",
        "质量安全",
        "数据安全",
        "同类药",
        "疗效和安全性变量",
        "评估的疗效和安全性指标和流程图",
    ),
)

CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH = ClinicalTrialFilterConfig(
    zone_config_name="csr_clinical_safety_zh",
    zone_config_version="0.2.0",
    filter_job_id="csr_clinical_safety",
    language="zh",
    strategy_id="heading_zone",
    policy=_CSR_CLINICAL_SAFETY_POLICY_ZH,
)
