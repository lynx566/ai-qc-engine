"""Clinical-trial strategy → Filter-output projection facade construction."""

from __future__ import annotations

from operations.filter_output_projection.contracts import (
    FilterOutputProjectionFacade,
    ResolvedFilterOutputProjectionJob,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)

from plugins.clinical_trial_doc.filter_output_projection.direct import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.facade import (
    build_overview_semantic_decomposition_facade,
)
from plugins.clinical_trial_doc.filter_output_projection.strategy_ids import (
    OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
)


def build_clinical_trial_filter_output_projection_facade(
    *,
    job: ResolvedFilterOutputProjectionJob,
    runtime_dependencies: FilterOutputProjectionRuntimeDependencies,
) -> FilterOutputProjectionFacade:
    """Map one resolved projection job to its concrete clinical-trial facade."""

    if job.strategy_id == DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID:
        return DIRECT_FILTER_OUTPUT_PROJECTION_FACADE

    if (
        job.strategy_id
        == OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID
    ):
        provider = runtime_dependencies.llm_provider
        if provider is None:
            raise ValueError(
                "llm_provider is required for Filter-output projection strategy "
                f"{job.strategy_id!r}"
            )
        return build_overview_semantic_decomposition_facade(
            llm_provider=provider,
            llm_execution_config=runtime_dependencies.llm_execution_config,
        )

    known = (
        DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
        OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
    )
    raise ValueError(
        f"unknown Filter-output projection strategy_id={job.strategy_id!r}; "
        f"known={known!r}"
    )


__all__ = ["build_clinical_trial_filter_output_projection_facade"]
