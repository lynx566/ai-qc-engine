"""Neutral in-memory contracts for Prepare Analysis configuration resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, is_dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from privacy.detectors.base import SensitiveEntityDetector
    from privacy.mapping_store import MappingStore
    from privacy.profile import PrivacyProfile
    from privacy.schemas import MaskResult
else:
    MaskResult = Any


def _validate_opaque_ref(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")


@dataclass(frozen=True, slots=True)
class PrepareAnalysisConfigId:
    """Opaque identity of one static Prepare Analysis composition envelope."""

    value: str

    def __post_init__(self) -> None:
        _validate_opaque_ref(self.value, field_name="prepare_analysis_config_id")

    def __str__(self) -> str:
        return self.value


class PrepareAnalysisDomainConfiguration:
    """Marker base for one coherent, domain-owned static composition.

    Domain packages extend this process-local object with the settings their
    resolver needs.  The neutral contract deliberately does not enumerate
    independent implementation, rules, registry, date, or provenance IDs.
    """


@dataclass(frozen=True, slots=True)
class PrepareAnalysisConfig:
    """Static composition selected by an opaque Prepare Analysis config ID."""

    prepare_analysis_config_id: PrepareAnalysisConfigId
    domain: PrepareAnalysisDomainConfiguration

    def __post_init__(self) -> None:
        if not isinstance(self.prepare_analysis_config_id, PrepareAnalysisConfigId):
            raise TypeError(
                "prepare_analysis_config_id must be a PrepareAnalysisConfigId"
            )
        if not isinstance(self.domain, PrepareAnalysisDomainConfiguration):
            raise TypeError("domain must be a PrepareAnalysisDomainConfiguration")
        dataclass_params = getattr(type(self.domain), "__dataclass_params__", None)
        if not is_dataclass(self.domain) or not getattr(
            dataclass_params, "frozen", False
        ):
            raise TypeError("domain configuration must be an immutable dataclass")


class PrepareAnalysisPrivacyConfiguration:
    """Domain-owned per-invocation privacy configuration marker."""


@dataclass(frozen=True, slots=True)
class PrepareAnalysisRequestOptions:
    """Formal per-invocation choices under one static configuration."""

    privacy_config: PrepareAnalysisPrivacyConfiguration

    def __post_init__(self) -> None:
        if not isinstance(
            self.privacy_config,
            PrepareAnalysisPrivacyConfiguration,
        ):
            raise TypeError(
                "privacy_config must be a PrepareAnalysisPrivacyConfiguration"
            )


@runtime_checkable
class ResolvedPrepareAnalysisPlan(Protocol):
    """In-memory boundary for fully resolved domain execution semantics.

    S2 will define a domain-owned immutable implementation.  This neutral
    protocol intentionally does not require live detector or model instances.
    """

    @property
    def prepare_analysis_config_id(self) -> PrepareAnalysisConfigId: ...

    @property
    def privacy_enabled(self) -> bool: ...

    @property
    def requested_detector_ids(self) -> tuple[str, ...]: ...

    @property
    def effective_detector_ids(self) -> tuple[str, ...]: ...

    @property
    def date_shift_enabled(self) -> bool: ...

    @property
    def date_shift_offset_days(self) -> int: ...

    @property
    def result_extension_values(self) -> Mapping[str, str]: ...

    @property
    def privacy_provenance_stats(self) -> Mapping[str, str]: ...

    @property
    def provenance_descriptor(self) -> Mapping[str, Any]: ...

    def build_detector(self) -> SensitiveEntityDetector: ...

    def build_privacy_profile(self) -> PrivacyProfile: ...

    def new_mapping_store(self) -> MappingStore: ...

    def validate_result_extension(self, payload: Mapping[str, Any]) -> None: ...


@runtime_checkable
class PrepareAnalysisDomainResolver(Protocol):
    """Resolve static configuration plus invocation facts into an execution plan."""

    def resolve(
        self,
        *,
        config: PrepareAnalysisConfig,
        request_options: PrepareAnalysisRequestOptions,
    ) -> ResolvedPrepareAnalysisPlan: ...


@dataclass
class AnalysisBundleResult:
    """Canonical in-memory result returned by the Prepare Analysis Step."""

    doc_id: str
    analysis_bundle: dict[str, Any]
    mask_result: MaskResult | None = None
    block_audit_surfaces: list[dict[str, Any]] = field(default_factory=list)
    heading_projection: Any | None = None


__all__ = [
    "AnalysisBundleResult",
    "PrepareAnalysisConfig",
    "PrepareAnalysisConfigId",
    "PrepareAnalysisDomainConfiguration",
    "PrepareAnalysisDomainResolver",
    "PrepareAnalysisPrivacyConfiguration",
    "PrepareAnalysisRequestOptions",
    "ResolvedPrepareAnalysisPlan",
]
