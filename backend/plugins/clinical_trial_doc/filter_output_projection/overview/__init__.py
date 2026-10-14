"""Overview semantic decomposition Filter-output projection."""

from plugins.clinical_trial_doc.filter_output_projection.overview.facade import (
    OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY,
    OverviewSemanticDecompositionProjectionFacade,
    build_overview_semantic_decomposition_facade,
    project_overview_semantic_decomposition,
)

__all__ = [
    "OVERVIEW_TARGET_SEMANTIC_MODULE_ID_CONFIG_KEY",
    "OverviewSemanticDecompositionProjectionFacade",
    "build_overview_semantic_decomposition_facade",
    "project_overview_semantic_decomposition",
]
