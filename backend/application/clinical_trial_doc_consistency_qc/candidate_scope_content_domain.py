"""Candidate Scope content-domain grouping derived from installed projection/route semantics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from operations.filter_output_projection.contracts import (
    ResolvedFilterOutputProjectionJob,
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

from application.clinical_trial_doc_consistency_qc.content_domain_presentation import (
    content_domain_display_label,
)


@dataclass(frozen=True, slots=True)
class CandidateScopeContentDomainGroup:
    content_domain_id: str
    display_label: str
    filter_job_ids: tuple[str, ...]


def resolve_filter_job_content_domain_ids(
    projection_job: ResolvedFilterOutputProjectionJob,
) -> frozenset[str]:
    """Return route semantic module ids that consume candidate sources from one filter job."""

    if projection_job.strategy_id == DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID:
        raw = projection_job.strategy_config.get(
            DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY
        )
        domain_id = str(raw or "").strip()
        if not domain_id:
            raise ValueError(
                "direct Filter-output projection job "
                f"{projection_job.filter_job_id!r} is missing "
                f"{DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY!r}"
            )
        return frozenset({domain_id})

    if (
        projection_job.strategy_id
        == OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID
    ):
        raw = projection_job.strategy_config.get(
            OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY
        )
        domain_id = str(raw or "").strip()
        if not domain_id:
            raise ValueError(
                "overview Filter-output projection job "
                f"{projection_job.filter_job_id!r} is missing "
                f"{OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY!r}"
            )
        return frozenset({domain_id})

    raise ValueError(
        "unsupported Filter-output projection strategy for content-domain grouping: "
        f"filter_job_id={projection_job.filter_job_id!r}, "
        f"strategy_id={projection_job.strategy_id!r}"
    )


def _capability_filter_job_ids(
    *,
    capability_id: str,
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
) -> frozenset[str]:
    job_ids: set[str] = set()
    for (bound_capability_id, _slot_id), filter_job_ids in filter_job_bindings.items():
        if bound_capability_id != capability_id:
            continue
        job_ids.update(filter_job_ids)
    if not job_ids:
        raise ValueError(
            f"capability {capability_id!r} has no installed filter job bindings"
        )
    return frozenset(job_ids)


def build_candidate_scope_content_domain_groups(
    *,
    capability_id: str,
    filter_job_bindings: Mapping[tuple[str, str], tuple[str, ...]],
    filter_output_projection_jobs: Mapping[str, ResolvedFilterOutputProjectionJob],
    route_semantic_module_sequence: Sequence[str],
) -> tuple[CandidateScopeContentDomainGroup, ...]:
    """Build user-facing content-domain groups for one installed capability."""

    capability_jobs = _capability_filter_job_ids(
        capability_id=capability_id,
        filter_job_bindings=filter_job_bindings,
    )
    routed_domain_ids = tuple(
        domain_id.strip()
        for domain_id in route_semantic_module_sequence
        if isinstance(domain_id, str) and domain_id.strip()
    )
    if not routed_domain_ids:
        raise ValueError(
            f"capability {capability_id!r} has no installed route semantic modules"
        )

    domain_to_jobs: dict[str, set[str]] = {domain_id: set() for domain_id in routed_domain_ids}

    for filter_job_id in sorted(capability_jobs):
        projection_job = filter_output_projection_jobs.get(filter_job_id)
        if projection_job is None:
            raise ValueError(
                f"capability {capability_id!r} references unknown filter job "
                f"{filter_job_id!r}"
            )
        content_domain_ids = resolve_filter_job_content_domain_ids(projection_job)
        for content_domain_id in content_domain_ids:
            if content_domain_id not in domain_to_jobs:
                continue
            domain_to_jobs[content_domain_id].add(filter_job_id)

    unassigned_jobs = {
        filter_job_id
        for filter_job_id in capability_jobs
        if not any(
            filter_job_id in domain_to_jobs[domain_id]
            for domain_id in routed_domain_ids
        )
    }
    if unassigned_jobs:
        raise ValueError(
            f"capability {capability_id!r} filter jobs are not assigned to any "
            f"installed route content domain: {sorted(unassigned_jobs)!r}"
        )

    groups: list[CandidateScopeContentDomainGroup] = []
    for content_domain_id in routed_domain_ids:
        filter_job_ids = tuple(sorted(domain_to_jobs[content_domain_id]))
        if not filter_job_ids:
            continue
        groups.append(
            CandidateScopeContentDomainGroup(
                content_domain_id=content_domain_id,
                display_label=content_domain_display_label(content_domain_id),
                filter_job_ids=filter_job_ids,
            )
        )

    if not groups:
        raise ValueError(
            f"capability {capability_id!r} produced no candidate-scope content-domain groups"
        )

    return tuple(groups)


__all__ = [
    "CandidateScopeContentDomainGroup",
    "build_candidate_scope_content_domain_groups",
    "resolve_filter_job_content_domain_ids",
]
