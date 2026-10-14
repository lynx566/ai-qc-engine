"""Neutral process-local registry for static Prepare Analysis configurations."""

from __future__ import annotations

from operations.prepare_analysis.contracts import (
    PrepareAnalysisConfig,
    PrepareAnalysisConfigId,
)


class UnknownPrepareAnalysisConfigError(LookupError):
    """Raised when an opaque Prepare Analysis config ID is not registered."""


class DuplicatePrepareAnalysisConfigError(ValueError):
    """Raised when a registry already contains the requested config ID."""


class PrepareAnalysisConfigRegistry:
    """Map opaque config identities to validated static configurations."""

    def __init__(self) -> None:
        self._configs: dict[PrepareAnalysisConfigId, PrepareAnalysisConfig] = {}

    def register(self, config: PrepareAnalysisConfig) -> None:
        if not isinstance(config, PrepareAnalysisConfig):
            raise TypeError("config must be a PrepareAnalysisConfig")
        config_id = config.prepare_analysis_config_id
        if config_id in self._configs:
            raise DuplicatePrepareAnalysisConfigError(
                f"duplicate prepare_analysis_config_id: {config_id}"
            )
        self._configs[config_id] = config

    def resolve(
        self,
        prepare_analysis_config_id: PrepareAnalysisConfigId,
    ) -> PrepareAnalysisConfig:
        if not isinstance(prepare_analysis_config_id, PrepareAnalysisConfigId):
            raise TypeError(
                "prepare_analysis_config_id must be a PrepareAnalysisConfigId"
            )
        try:
            return self._configs[prepare_analysis_config_id]
        except KeyError as exc:
            raise UnknownPrepareAnalysisConfigError(
                f"unknown prepare_analysis_config_id: {prepare_analysis_config_id}"
            ) from exc


__all__ = [
    "DuplicatePrepareAnalysisConfigError",
    "PrepareAnalysisConfigRegistry",
    "UnknownPrepareAnalysisConfigError",
]
