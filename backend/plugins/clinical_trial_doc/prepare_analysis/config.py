"""Clinical-owned registration of the current Prepare Analysis composition."""

from __future__ import annotations

from operations.prepare_analysis.contracts import (
    PrepareAnalysisConfig,
    PrepareAnalysisConfigId,
)
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry

from plugins.clinical_trial_doc.prepare_analysis.resolver import (
    ClinicalPrepareAnalysisDomainConfiguration,
)

CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID = PrepareAnalysisConfigId("pacfg_7f3a1c9e")


CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG = PrepareAnalysisConfig(
    prepare_analysis_config_id=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    domain=ClinicalPrepareAnalysisDomainConfiguration(),
)


def register_current_clinical_prepare_analysis_config(
    registry: PrepareAnalysisConfigRegistry,
) -> None:
    """Register the sole currently supported clinical Prepare configuration."""

    if not isinstance(registry, PrepareAnalysisConfigRegistry):
        raise TypeError("registry must be a PrepareAnalysisConfigRegistry")
    registry.register(CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG)


def build_current_clinical_prepare_analysis_config_registry() -> (
    PrepareAnalysisConfigRegistry
):
    """Return a neutral registry populated with the installed clinical config."""

    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    return registry


__all__ = [
    "CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG",
    "CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID",
    "ClinicalPrepareAnalysisDomainConfiguration",
    "build_current_clinical_prepare_analysis_config_registry",
    "register_current_clinical_prepare_analysis_config",
]
