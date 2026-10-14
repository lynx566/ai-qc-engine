"""Application installation guards for projected-source Route executor."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.projected_source_route_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR,
)
from operations.projected_source_route.contracts import ProjectedSourceRouteExecutor
from plugins.clinical_trial_doc.routing import (
    route_prepare_units_from_projected_sources,
)


def test_installed_projected_source_route_executor_is_callable() -> None:
    assert callable(INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR)


def test_installed_projected_source_route_executor_matches_plugin_implementation() -> (
    None
):
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR
        is route_prepare_units_from_projected_sources
    )
    assert isinstance(
        INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR,
        ProjectedSourceRouteExecutor,
    )
