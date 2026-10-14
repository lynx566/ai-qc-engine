from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)
from runtime.zone_registry import filter_job_dir_context


def test_filter_job_dir_context_uses_zone_config_name() -> None:
    assert (
        filter_job_dir_context(
            zone_key="ib_clinical_safety_zh",
            profile=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
        )
        == "ib_clinical_safety_zh"
    )


def test_filter_job_dir_context_zone_config_spec_uses_profile_name() -> None:
    spec = (
        "plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh:"
        "IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH"
    )
    assert (
        filter_job_dir_context(
            zone_key=spec,
            profile=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
        )
        == "ib_clinical_safety_zh"
    )


def test_filter_job_dir_context_distinct_profiles() -> None:
    overview = filter_job_dir_context(
        zone_key="ib_overview_zh",
        profile=IB_OVERVIEW_FILTER_PROFILE_ZH,
    )
    safety = filter_job_dir_context(
        zone_key="ib_clinical_safety_zh",
        profile=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    )
    assert overview == "ib_overview_zh"
    assert safety == "ib_clinical_safety_zh"
    assert overview != safety
