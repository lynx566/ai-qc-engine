"""Filter-output projection application installation for clinical-trial Document Consistency QC."""

from __future__ import annotations

from types import MappingProxyType

from operations.filter_output_projection.contracts import (
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.registry import (
    build_filter_output_projection_job_index,
)
from plugins.clinical_trial_doc.filter_output_projection.direct import (
    DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
    DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.facade import (
    OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY,
)
from plugins.clinical_trial_doc.filter_output_projection.strategy_ids import (
    OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
)

from .filter_installation import INSTALLED_FILTER_PROFILES

CLINICAL_SAFETY_SEMANTIC_MODULE_ID = "clinical_safety"

_CLINICAL_SAFETY_FILTER_PROFILES = tuple(
    profile
    for profile in INSTALLED_FILTER_PROFILES
    if profile.filter_job_id.endswith("_clinical_safety")
)

_OVERVIEW_FILTER_PROFILES = tuple(
    profile
    for profile in INSTALLED_FILTER_PROFILES
    if profile.filter_job_id.endswith("_overview")
)


def _direct_projection_job(filter_job_id: str) -> ResolvedFilterOutputProjectionJob:
    return ResolvedFilterOutputProjectionJob(
        filter_job_id=filter_job_id,
        strategy_id=DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        strategy_config=MappingProxyType(
            {
                DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY: (
                    CLINICAL_SAFETY_SEMANTIC_MODULE_ID
                ),
            }
        ),
    )


def _overview_projection_job(filter_job_id: str) -> ResolvedFilterOutputProjectionJob:
    return ResolvedFilterOutputProjectionJob(
        filter_job_id=filter_job_id,
        strategy_id=OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        strategy_config=MappingProxyType(
            {
                OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY: (
                    CLINICAL_SAFETY_SEMANTIC_MODULE_ID
                )
            }
        ),
    )


_INSTALLED_FILTER_OUTPUT_PROJECTION_JOB_OBJECTS: tuple[
    ResolvedFilterOutputProjectionJob, ...
] = (
    *(
        _direct_projection_job(profile.filter_job_id)
        for profile in _CLINICAL_SAFETY_FILTER_PROFILES
    ),
    *(
        _overview_projection_job(profile.filter_job_id)
        for profile in _OVERVIEW_FILTER_PROFILES
    ),
)

INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS = (
    build_filter_output_projection_job_index(
        _INSTALLED_FILTER_OUTPUT_PROJECTION_JOB_OBJECTS
    )
)


def validate_filter_output_projection_installation(
    *,
    installed_filter_job_ids: frozenset[str],
    filter_output_projection_jobs: MappingProxyType[str, ResolvedFilterOutputProjectionJob]
    | dict[str, ResolvedFilterOutputProjectionJob],
) -> None:
    """Ensure every installed production Filter job has exactly one projection binding."""

    projection_ids = frozenset(filter_output_projection_jobs)
    missing = installed_filter_job_ids - projection_ids
    if missing:
        raise ValueError(
            "missing Filter-output projection bindings for filter jobs: "
            + ", ".join(sorted(missing))
        )
    extra = projection_ids - installed_filter_job_ids
    if extra:
        raise ValueError(
            "unknown Filter-output projection bindings for filter jobs: "
            + ", ".join(sorted(extra))
        )


_installed_filter_job_ids = frozenset(
    profile.filter_job_id for profile in INSTALLED_FILTER_PROFILES
)
validate_filter_output_projection_installation(
    installed_filter_job_ids=_installed_filter_job_ids,
    filter_output_projection_jobs=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS,
)


__all__ = [
    "CLINICAL_SAFETY_SEMANTIC_MODULE_ID",
    "INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS",
    "validate_filter_output_projection_installation",
]
