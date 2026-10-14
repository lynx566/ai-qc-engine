"""Filter-output projection facade builder installation for clinical-trial QC."""

from __future__ import annotations

from operations.filter_output_projection.facade_builder import (
    FilterOutputProjectionFacadeBuilder,
)
from plugins.clinical_trial_doc.filter_output_projection.facade_builder import (
    build_clinical_trial_filter_output_projection_facade,
)

INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_FACADE_BUILDER: (
    FilterOutputProjectionFacadeBuilder
) = build_clinical_trial_filter_output_projection_facade

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_FACADE_BUILDER",
]
