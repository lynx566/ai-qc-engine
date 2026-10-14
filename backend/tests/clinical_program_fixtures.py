"""Shared canonical clinical program fixtures for tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from operations.prepare_analysis import (
    PrepareAnalysisConfig,
    PrepareAnalysisConfigId,
    PrepareAnalysisRequestOptions,
    ResolvedPrepareAnalysisPlan,
)
from steps.prepare_analysis import prepare_analysis_bundle
from plugins.clinical_trial_doc.prepare_analysis import (
    CLINICAL_REGEX_RULE_SET_ZH,
    CLINICAL_UIE_CONFIG_ZH,
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    build_clinical_prepare_privacy_config,
    clinical_prepare_privacy_behaviors_selected,
    resolve_clinical_prepare_date_shift_enabled,
)
from plugins.clinical_trial_doc.prepare_analysis.resolver import (
    ClinicalPrepareAnalysisDomainConfiguration,
)
from plugins.clinical_trial_doc.privacy.profile import (
    CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
)
from privacy.config import PrivacyConfig
from privacy.mapping_store import MappingStore
from privacy.profile import PrivacyProfile

CANONICAL_TEST_CLINICAL_PROGRAM_ID = "clinical_program_001"
_TEST_PREPARE_ANALYSIS_CONFIG_ID = PrepareAnalysisConfigId("pacfg_test")


def _test_prepare_analysis_config(
    *,
    profile: PrivacyProfile | None,
    language: str,
    date_shift_offset_days: int | None,
) -> PrepareAnalysisConfig:
    if profile is None and date_shift_offset_days is None:
        return CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG

    current_profile = profile or CLINICAL_TRIAL_DOC_PRIVACY_PROFILE
    debug_offset = (
        date_shift_offset_days
        if date_shift_offset_days is not None
        else current_profile.date_shift_offset_days
        if profile is not None
        else None
    )

    if profile is None and date_shift_offset_days is not None:
        domain = replace(
            CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG.domain,
            debug_date_shift_offset_days=date_shift_offset_days,
        )
        return PrepareAnalysisConfig(_TEST_PREPARE_ANALYSIS_CONFIG_ID, domain)

    regex_rules = tuple(current_profile.regex_rules.get(language, ()))
    uie_schema = tuple(
        sorted(current_profile.uie_schema_by_language.get(language, {}).items())
    )
    domain = ClinicalPrepareAnalysisDomainConfiguration(
        entity_types_to_mask=frozenset(current_profile.entity_types_to_mask),
        entity_types_to_keep=frozenset(current_profile.entity_types_to_keep),
        profile_date_shift_offset_days=current_profile.date_shift_offset_days,
        installed_regex_rule_sets=((CLINICAL_REGEX_RULE_SET_ZH, regex_rules),),
        installed_uie_configs=((CLINICAL_UIE_CONFIG_ZH, uie_schema),),
        uie_denylist=frozenset(current_profile.uie_denylist),
        token_prefixes=tuple(sorted(current_profile.token_prefixes.items())),
        debug_date_shift_offset_days=debug_offset,
    )
    return PrepareAnalysisConfig(_TEST_PREPARE_ANALYSIS_CONFIG_ID, domain)


@dataclass(frozen=True)
class _TestExecutionOverrides:
    base: ResolvedPrepareAnalysisPlan
    detector: Any | None
    mapping_store: MappingStore | None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base, name)

    def build_detector(self):
        return self.detector or self.base.build_detector()

    def new_mapping_store(self) -> MappingStore:
        return self.mapping_store or self.base.new_mapping_store()


def prepare_analysis_bundle_for_test(
    bundle: dict[str, Any],
    *,
    clinical_program_id: str = CANONICAL_TEST_CLINICAL_PROGRAM_ID,
    language: str = "zh",
    profile: PrivacyProfile | None = None,
    privacy_config: PrivacyConfig | None = None,
    mapping_store: MappingStore | None = None,
    detector: Any | None = None,
    analysis_bundle_id: str | None = None,
    date_shift_offset_days: int | None = None,
    date_shift_explicit: bool | None = None,
) -> Any:
    """Translate historical test knobs into the canonical resolved-plan Step."""

    configured = privacy_config or PrivacyConfig.default()
    detector_ids = tuple(configured.transform_detectors("after_extract"))
    effective_date_explicit = (
        date_shift_offset_days > 0
        if date_shift_offset_days is not None
        else date_shift_explicit
    )
    registry_enabled = "registry" in detector_ids
    regex_rule_set_ref = (
        CLINICAL_REGEX_RULE_SET_ZH if "regex" in detector_ids else None
    )
    uie_config_ref = CLINICAL_UIE_CONFIG_ZH if "uie" in detector_ids else None
    masking_behaviors_selected = clinical_prepare_privacy_behaviors_selected(
        registry_enabled=registry_enabled,
        regex_rule_set_ref=regex_rule_set_ref,
        uie_config_ref=uie_config_ref,
    )
    date_shift_enabled = resolve_clinical_prepare_date_shift_enabled(
        masking_behaviors_selected=masking_behaviors_selected,
        date_shift_explicit=effective_date_explicit,
    )

    if profile is None and date_shift_offset_days is None:
        config = CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG
    else:
        config = _test_prepare_analysis_config(
            profile=profile,
            language=language,
            date_shift_offset_days=date_shift_offset_days,
        )
    plan = config.domain.resolve(  # type: ignore[attr-defined]
        config=config,
        request_options=PrepareAnalysisRequestOptions(
            privacy_config=build_clinical_prepare_privacy_config(
                registry_enabled=registry_enabled,
                regex_rule_set_ref=regex_rule_set_ref,
                uie_config_ref=uie_config_ref,
                date_shift_enabled=date_shift_enabled,
                clinical_program_id=(
                    clinical_program_id if registry_enabled else None
                ),
            )
        ),
    )
    if detector is not None or mapping_store is not None:
        plan = _TestExecutionOverrides(plan, detector, mapping_store)
    return prepare_analysis_bundle(
        bundle,
        resolved_plan=plan,
        analysis_bundle_id=analysis_bundle_id,
    )


def canonical_clinical_program_fields() -> dict[str, str]:
    return {
        "clinical_program_id": CANONICAL_TEST_CLINICAL_PROGRAM_ID,
    }


def inherited_clinical_program_field() -> dict[str, str]:
    """Deprecated test helper; program is no longer a downstream artifact field."""
    return {}


def canonical_analysis_bundle_fields() -> dict[str, str]:
    return {}


def ensure_canonical_analysis_bundle_fields(bundle: dict[str, object]) -> dict[str, object]:
    """Test helper: return bundle unchanged (program fields removed from analysis_bundle)."""
    return dict(bundle)
