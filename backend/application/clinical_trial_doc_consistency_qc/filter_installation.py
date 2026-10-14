"""Filter application installation for clinical-trial Document Consistency QC."""

from __future__ import annotations

from types import MappingProxyType

from operations.filter.variant_registry import (
    build_filter_job_variants,
)
from plugins.clinical_trial_doc.filter_profiles import (
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)

INSTALLED_FILTER_PROFILES: tuple[object, ...] = (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    IB_OVERVIEW_FILTER_PROFILE_ZH,
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
)
_installed_filter_config_names = [
    config.zone_config_name for config in INSTALLED_FILTER_PROFILES
]
if len(set(_installed_filter_config_names)) != len(_installed_filter_config_names):
    raise ValueError("installed clinical Filter config IDs must be unique")

INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS: MappingProxyType[str, object] = (
    MappingProxyType(
        {
            config.zone_config_name: config
            for config in INSTALLED_FILTER_PROFILES
        }
    )
)

INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS = build_filter_job_variants(
    INSTALLED_FILTER_PROFILES
)

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS",
    "INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS",
    "INSTALLED_FILTER_PROFILES",
]
