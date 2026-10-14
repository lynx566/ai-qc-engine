"""Clinical domain resolution for canonical Prepare Analysis execution."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from operations.prepare_analysis.contracts import (
    PrepareAnalysisConfig,
    PrepareAnalysisConfigId,
    PrepareAnalysisDomainConfiguration,
    PrepareAnalysisRequestOptions,
)
from privacy.detectors.composite import CompositeDetector
from privacy.detectors.local_model_detector import LocalModelDetector
from privacy.detectors.regex_detector import RegexDetector, RegexRule
from privacy.detectors.registry_detector import RegistryDetector, RegistryEntry
from privacy.detectors.uie_detector import UIEDetector
from privacy.mapping_store import MappingStore
from privacy.profile import PrivacyProfile

from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    CLINICAL_REGEX_RULE_SET_ZH,
    CLINICAL_UIE_CONFIG_ZH,
    ClinicalPreparePrivacyConfig,
)
from plugins.clinical_trial_doc.privacy.profile import (
    CLINICAL_TOKEN_PREFIXES,
    CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
)
from plugins.clinical_trial_doc.privacy.regex_rules_zh import (
    CLINICAL_TRIAL_DOC_REGEX_RULES_ZH,
)
from plugins.clinical_trial_doc.privacy.registry.export import (
    export_clinical_registry_entries_for_program,
)
from plugins.clinical_trial_doc.privacy.registry.loader import get_clinical_program
from plugins.clinical_trial_doc.privacy.uie_schema_zh import (
    CLINICAL_TRIAL_DOC_UIE_GENERIC_TERM_DENYLIST,
    CLINICAL_TRIAL_DOC_UIE_SCHEMA_TO_ENTITY_TYPE_ZH,
)
from plugins.clinical_trial_doc.VERSION import (
    CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS,
    CLINICAL_TRIAL_DOC_PLUGIN_VERSION,
)

_LOGICAL_DETECTOR_IDS = ("registry", "regex", "uie")
_CLINICAL_PLUGIN_NAME = "clinical_trial_doc"


class ClinicalPrepareAnalysisResolutionError(ValueError):
    """A configured clinical composition could not resolve an execution plan."""


@dataclass(frozen=True, slots=True)
class ResolvedRegistryDetectorSpec:
    entries: tuple[RegistryEntry, ...]
    detector_id: str = "registry"
    implementation_id: str = "registry"

    def build(self) -> RegistryDetector:
        return RegistryDetector(self.entries)


@dataclass(frozen=True, slots=True)
class ResolvedRegexDetectorSpec:
    rules: tuple[RegexRule, ...]
    detector_id: str = "regex"
    implementation_id: str = "regex"

    def build(self) -> RegexDetector:
        return RegexDetector(self.rules)


@dataclass(frozen=True, slots=True)
class ResolvedUieDetectorSpec:
    schema_items: tuple[tuple[str, str], ...]
    denylist: frozenset[str]
    implementation_id: Literal["uie", "local_model"]
    detector_id: str = "uie"

    def build(self) -> UIEDetector | LocalModelDetector:
        if self.implementation_id == "local_model":
            return LocalModelDetector()
        return UIEDetector(dict(self.schema_items), denylist=self.denylist)


ResolvedClinicalDetectorSpec = (
    ResolvedRegistryDetectorSpec | ResolvedRegexDetectorSpec | ResolvedUieDetectorSpec
)


@dataclass(frozen=True, slots=True)
class ResolvedDateShiftInstruction:
    enabled: bool
    effective_offset_days: int
    offset_source: Literal["profile", "debug_override", "disabled"]


@dataclass(frozen=True, slots=True)
class ResolvedMaskPolicy:
    entity_types_to_mask: frozenset[str]
    entity_types_to_keep: frozenset[str]


@dataclass(frozen=True, slots=True)
class ResolvedTokenAllocationPolicy:
    token_prefixes: tuple[tuple[str, str], ...]

    def new_mapping_store(self) -> MappingStore:
        return MappingStore(token_prefixes=dict(self.token_prefixes))


@dataclass(frozen=True, slots=True)
class ResolvedClinicalPluginProvenance:
    composition_id: str
    plugin_name: str
    plugin_version: str
    component_versions: tuple[tuple[str, str], ...]
    detector_implementations: tuple[tuple[str, str], ...]

    def as_plugin_dict(self, *, include_components: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.plugin_name,
            "version": self.plugin_version,
        }
        if include_components:
            payload["components"] = dict(self.component_versions)
        return payload


@dataclass(frozen=True, slots=True)
class ClinicalResolvedPrepareAnalysisPlan:
    """Complete immutable per-participant clinical execution plan."""

    prepare_analysis_config_id: PrepareAnalysisConfigId
    privacy_enabled: bool
    detector_specs: tuple[ResolvedClinicalDetectorSpec, ...]
    requested_detector_ids: tuple[str, ...]
    effective_detector_ids: tuple[str, ...]
    date_shift: ResolvedDateShiftInstruction
    mask_policy: ResolvedMaskPolicy
    token_policy: ResolvedTokenAllocationPolicy
    provenance: ResolvedClinicalPluginProvenance
    _privacy_stat_pairs: tuple[tuple[str, str], ...] = ()

    @property
    def date_shift_enabled(self) -> bool:
        return self.date_shift.enabled

    @property
    def date_shift_offset_days(self) -> int:
        return self.date_shift.effective_offset_days

    @property
    def result_extension_values(self) -> Mapping[str, str]:
        return {}

    @property
    def provenance_descriptor(self) -> Mapping[str, Any]:
        return self.provenance.as_plugin_dict(include_components=self.privacy_enabled)

    def build_detector(self) -> CompositeDetector:
        return CompositeDetector([spec.build() for spec in self.detector_specs])

    def build_privacy_profile(self) -> PrivacyProfile:
        """Create fresh generic policy data without another clinical lookup."""

        return PrivacyProfile(
            entity_types_to_mask=self.mask_policy.entity_types_to_mask,
            entity_types_to_keep=self.mask_policy.entity_types_to_keep,
            date_shift_offset_days=self.date_shift.effective_offset_days,
            token_prefixes=dict(self.token_policy.token_prefixes),
        )

    def new_mapping_store(self) -> MappingStore:
        return self.token_policy.new_mapping_store()

    def validate_result_extension(self, payload: Mapping[str, Any]) -> None:
        return None

    @property
    def privacy_provenance_stats(self) -> Mapping[str, str]:
        return dict(self._privacy_stat_pairs)


def _uie_runtime_available() -> bool:
    try:
        importlib.import_module("paddlenlp")
    except ModuleNotFoundError:
        return False
    return True


def _validated_date_shift_offset(value: object, *, source: str) -> int:
    if type(value) is not int:
        raise ClinicalPrepareAnalysisResolutionError(
            f"clinical date-shift offset from {source} must be an integer"
        )
    return value


@dataclass(frozen=True, slots=True)
class ClinicalPrepareAnalysisDomainConfiguration(PrepareAnalysisDomainConfiguration):
    """One coherent configured clinical resolver and its private policy family."""

    entity_types_to_mask: frozenset[str] = frozenset(
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.entity_types_to_mask
    )
    entity_types_to_keep: frozenset[str] = frozenset(
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.entity_types_to_keep
    )
    profile_date_shift_offset_days: int = (
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.date_shift_offset_days
    )
    installed_regex_rule_sets: tuple[tuple[str, tuple[RegexRule, ...]], ...] = (
        (CLINICAL_REGEX_RULE_SET_ZH, tuple(CLINICAL_TRIAL_DOC_REGEX_RULES_ZH)),
    )
    installed_uie_configs: tuple[
        tuple[str, tuple[tuple[str, str], ...]], ...
    ] = (
        (
            CLINICAL_UIE_CONFIG_ZH,
            tuple(sorted(CLINICAL_TRIAL_DOC_UIE_SCHEMA_TO_ENTITY_TYPE_ZH.items())),
        ),
    )
    uie_denylist: frozenset[str] = frozenset(
        CLINICAL_TRIAL_DOC_UIE_GENERIC_TERM_DENYLIST
    )
    token_prefixes: tuple[tuple[str, str], ...] = tuple(
        sorted(CLINICAL_TOKEN_PREFIXES.items())
    )
    component_versions: tuple[tuple[str, str], ...] = tuple(
        sorted(CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS.items())
    )
    detector_execution_order: tuple[str, ...] = _LOGICAL_DETECTOR_IDS
    uie_fallback_allowed: bool = True
    debug_date_shift_offset_days: int | None = None

    def resolve(
        self,
        *,
        config: PrepareAnalysisConfig,
        request_options: PrepareAnalysisRequestOptions,
    ) -> ClinicalResolvedPrepareAnalysisPlan:
        if config.domain is not self:
            raise ClinicalPrepareAnalysisResolutionError(
                "clinical resolver is not the domain configured by this config"
            )
        if not isinstance(request_options, PrepareAnalysisRequestOptions):
            raise TypeError("request_options must be a PrepareAnalysisRequestOptions")
        privacy_config = request_options.privacy_config
        if not isinstance(privacy_config, ClinicalPreparePrivacyConfig):
            raise TypeError("privacy_config must be a ClinicalPreparePrivacyConfig")

        installed_regex = dict(self.installed_regex_rule_sets)
        if (
            privacy_config.regex_rule_set_ref is not None
            and privacy_config.regex_rule_set_ref not in installed_regex
        ):
            raise ClinicalPrepareAnalysisResolutionError(
                "unknown installed clinical regex rule-set ref: "
                f"{privacy_config.regex_rule_set_ref!r}"
            )
        installed_uie = dict(self.installed_uie_configs)
        if (
            privacy_config.uie_config_ref is not None
            and privacy_config.uie_config_ref not in installed_uie
        ):
            raise ClinicalPrepareAnalysisResolutionError(
                "unknown installed clinical UIE config ref: "
                f"{privacy_config.uie_config_ref!r}"
            )

        program = None
        if privacy_config.registry_enabled:
            program_id = privacy_config.clinical_program_id
            assert program_id is not None
            program = get_clinical_program(program_id)
            if program is None:
                raise ClinicalPrepareAnalysisResolutionError(
                    "unknown clinical program required by resolved policy: "
                    f"{program_id!r}"
                )

        detector_specs: list[ResolvedClinicalDetectorSpec] = []
        requested_detector_ids: list[str] = []
        selected_detectors = {
            "registry": privacy_config.registry_enabled,
            "regex": privacy_config.regex_rule_set_ref is not None,
            "uie": privacy_config.uie_config_ref is not None,
        }
        for detector_id in self.detector_execution_order:
            if not selected_detectors.get(detector_id, False):
                continue
            requested_detector_ids.append(detector_id)
            if detector_id == "registry":
                assert program is not None
                try:
                    entries = export_clinical_registry_entries_for_program(program)
                except (TypeError, ValueError) as exc:
                    raise ClinicalPrepareAnalysisResolutionError(
                        "clinical Program registry export failed"
                    ) from exc
                if not entries:
                    raise ClinicalPrepareAnalysisResolutionError(
                        "clinical Program registry resolved no detector entries"
                    )
                detector_specs.append(ResolvedRegistryDetectorSpec(entries))
            elif detector_id == "regex":
                assert privacy_config.regex_rule_set_ref is not None
                rules = installed_regex[privacy_config.regex_rule_set_ref]
                if not rules:
                    raise ClinicalPrepareAnalysisResolutionError(
                        "installed clinical regex rule set resolved no rules"
                    )
                detector_specs.append(ResolvedRegexDetectorSpec(rules))
            elif detector_id == "uie":
                assert privacy_config.uie_config_ref is not None
                schema_items = installed_uie[privacy_config.uie_config_ref]
                if not schema_items:
                    raise ClinicalPrepareAnalysisResolutionError(
                        "installed clinical UIE config resolved no schema"
                    )
                if _uie_runtime_available():
                    implementation: Literal["uie", "local_model"] = "uie"
                elif self.uie_fallback_allowed:
                    implementation = "local_model"
                else:
                    raise ClinicalPrepareAnalysisResolutionError(
                        "UIE implementation unavailable and fallback is disallowed"
                    )
                detector_specs.append(
                    ResolvedUieDetectorSpec(
                        schema_items=schema_items,
                        denylist=self.uie_denylist,
                        implementation_id=implementation,
                    )
                )

        if privacy_config.date_shift_enabled:
            if self.debug_date_shift_offset_days is not None:
                offset = _validated_date_shift_offset(
                    self.debug_date_shift_offset_days,
                    source="debug override",
                )
                offset_source: Literal[
                    "profile",
                    "debug_override",
                    "disabled",
                ] = "debug_override"
            else:
                offset = _validated_date_shift_offset(
                    self.profile_date_shift_offset_days,
                    source="clinical profile",
                )
                offset_source = "profile"
            date_shift = ResolvedDateShiftInstruction(True, offset, offset_source)
        else:
            date_shift = ResolvedDateShiftInstruction(False, 0, "disabled")

        privacy_stats: list[tuple[str, str]] = []
        if privacy_config.registry_enabled and privacy_config.clinical_program_id:
            privacy_stats.append(
                ("clinical_program_id", privacy_config.clinical_program_id)
            )

        component_keys = {"privacy_profile"}
        if privacy_config.registry_enabled:
            component_keys.add("registry")
        if privacy_config.regex_rule_set_ref is not None:
            component_keys.add("regex_rules_zh")
        if privacy_config.uie_config_ref is not None:
            component_keys.add("uie_schema_zh")
        all_component_versions = dict(self.component_versions)
        component_versions = tuple(
            (key, all_component_versions[key])
            for key in sorted(component_keys)
            if key in all_component_versions
        )
        effective_ids = tuple(spec.implementation_id for spec in detector_specs)
        provenance = ResolvedClinicalPluginProvenance(
            composition_id=str(config.prepare_analysis_config_id),
            plugin_name=_CLINICAL_PLUGIN_NAME,
            plugin_version=CLINICAL_TRIAL_DOC_PLUGIN_VERSION,
            component_versions=component_versions,
            detector_implementations=tuple(
                zip(requested_detector_ids, effective_ids, strict=True)
            ),
        )

        return ClinicalResolvedPrepareAnalysisPlan(
            prepare_analysis_config_id=config.prepare_analysis_config_id,
            privacy_enabled=privacy_config.enabled,
            detector_specs=tuple(detector_specs),
            requested_detector_ids=tuple(requested_detector_ids),
            effective_detector_ids=effective_ids,
            date_shift=date_shift,
            mask_policy=ResolvedMaskPolicy(
                entity_types_to_mask=self.entity_types_to_mask,
                entity_types_to_keep=self.entity_types_to_keep,
            ),
            token_policy=ResolvedTokenAllocationPolicy(self.token_prefixes),
            provenance=provenance,
            _privacy_stat_pairs=tuple(privacy_stats),
        )


__all__ = [
    "ClinicalPrepareAnalysisDomainConfiguration",
    "ClinicalPrepareAnalysisResolutionError",
    "ClinicalResolvedPrepareAnalysisPlan",
    "ResolvedClinicalPluginProvenance",
    "ResolvedDateShiftInstruction",
    "ResolvedMaskPolicy",
    "ResolvedRegexDetectorSpec",
    "ResolvedRegistryDetectorSpec",
    "ResolvedTokenAllocationPolicy",
    "ResolvedUieDetectorSpec",
]
