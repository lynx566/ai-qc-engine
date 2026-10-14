"""Clinical-trial Filter-output projection strategies."""

from plugins.clinical_trial_doc.filter_output_projection.direct import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
    DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY,
    DirectFilterOutputProjectionFacade,
    project_direct_filter_output,
)
from plugins.clinical_trial_doc.filter_output_projection.overview import (
    OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY,
    OverviewSemanticDecompositionProjectionFacade,
    build_overview_semantic_decomposition_facade,
    project_overview_semantic_decomposition,
)
from plugins.clinical_trial_doc.filter_output_projection.strategy_ids import (
    OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
)

__all__ = [
    "DIRECT_FILTER_OUTPUT_PROJECTION_FACADE",
    "DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID",
    "DIRECT_PROJECTION_SEMANTIC_MODULE_ID_CONFIG_KEY",
    "OVERVIEW_SEMANTIC_DECOMPOSITION_FILTER_OUTPUT_PROJECTION_STRATEGY_ID",
    "OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY",
    "DirectFilterOutputProjectionFacade",
    "OverviewSemanticDecompositionProjectionFacade",
    "build_overview_semantic_decomposition_facade",
    "project_direct_filter_output",
    "project_overview_semantic_decomposition",
]
