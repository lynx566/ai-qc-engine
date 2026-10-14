"""Projected-source Route executor installation for clinical-trial documents."""

from __future__ import annotations

from operations.projected_source_route.contracts import ProjectedSourceRouteExecutor
from plugins.clinical_trial_doc.routing import (
    route_prepare_units_from_projected_sources,
)

INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR: (
    ProjectedSourceRouteExecutor
) = route_prepare_units_from_projected_sources

__all__ = ["INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR"]
