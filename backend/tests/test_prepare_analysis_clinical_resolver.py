"""Focused S2 tests for clinical Prepare Analysis domain resolution."""

from __future__ import annotations

import ast
import sys
from dataclasses import fields
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.registry.alias import AliasEntityRecord
from operations.prepare_analysis import (
    PrepareAnalysisConfig,
    PrepareAnalysisConfigId,
    PrepareAnalysisConfigRegistry,
    PrepareAnalysisDomainResolver,
    PrepareAnalysisRequestOptions,
    ResolvedPrepareAnalysisPlan,
)
from plugins.clinical_trial_doc.prepare_analysis import (
    CLINICAL_REGEX_RULE_SET_ZH,
    CLINICAL_UIE_CONFIG_ZH,
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    ClinicalPrepareAnalysisResolutionError,
    ClinicalPreparePrivacyConfig,
    ClinicalResolvedPrepareAnalysisPlan,
    register_current_clinical_prepare_analysis_config,
)
from plugins.clinical_trial_doc.prepare_analysis import (
    resolver as resolver_module,
)
from plugins.clinical_trial_doc.prepare_analysis.resolver import (
    ClinicalPrepareAnalysisDomainConfiguration,
    ResolvedRegistryDetectorSpec,
    ResolvedUieDetectorSpec,
)
from plugins.clinical_trial_doc.privacy.profile import (
    CLINICAL_TOKEN_PREFIXES,
    CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
)
from plugins.clinical_trial_doc.privacy.regex_rules_zh import (
    CLINICAL_TRIAL_DOC_REGEX_RULES_ZH,
)
from plugins.clinical_trial_doc.privacy.registry.export import (
    export_clinical_registry_entries,
    export_clinical_registry_entries_for_program,
)
from plugins.clinical_trial_doc.privacy.registry.loader import (
    get_clinical_program,
)
from plugins.clinical_trial_doc.privacy.registry.schemas import (
    ClinicalProgramRecord,
)


def _privacy_config(
    detector_ids: tuple[str, ...],
    *,
    date_shift_enabled: bool,
    program_id: str | None = None,
) -> ClinicalPreparePrivacyConfig:
    registry_enabled = "registry" in detector_ids
    return ClinicalPreparePrivacyConfig(
        enabled=bool(detector_ids) or date_shift_enabled,
        registry_enabled=registry_enabled,
        regex_rule_set_ref=(
            CLINICAL_REGEX_RULE_SET_ZH if "regex" in detector_ids else None
        ),
        uie_config_ref=(
            CLINICAL_UIE_CONFIG_ZH if "uie" in detector_ids else None
        ),
        date_shift_enabled=date_shift_enabled,
        clinical_program_id=(
            program_id if registry_enabled else None
        ),
    )


def _resolve(
    detector_ids: tuple[str, ...] = (),
    *,
    date_shift_explicit: bool | None = None,
    program_id: str | None = "clinical_program_001",
) -> ClinicalResolvedPrepareAnalysisPlan:
    date_shift_enabled = (
        bool(detector_ids)
        if date_shift_explicit is None
        else date_shift_explicit
    )
    request_options = PrepareAnalysisRequestOptions(
        _privacy_config(
            detector_ids,
            date_shift_enabled=date_shift_enabled,
            program_id=program_id,
        )
    )
    return CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG.domain.resolve(
        config=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
        request_options=request_options,
    )


def _program(
    program_id: str,
    alias: str,
) -> ClinicalProgramRecord:
    return ClinicalProgramRecord(
        canonical_id=program_id,
        study_drugs=(),
        sponsor=AliasEntityRecord(
            canonical_id=f"{program_id}:sponsor",
            token=f"Sponsor_{program_id[-1]}",
            aliases=(alias,),
        ),
    )


def test_registered_config_exposes_configured_clinical_resolver() -> None:
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)
    config = registry.resolve(CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID)

    assert isinstance(config.domain, ClinicalPrepareAnalysisDomainConfiguration)
    assert isinstance(config.domain, PrepareAnalysisDomainResolver)
    plan = config.domain.resolve(
        config=config,
        request_options=PrepareAnalysisRequestOptions(
            ClinicalPreparePrivacyConfig.identity()
        ),
    )
    assert isinstance(plan, ResolvedPrepareAnalysisPlan)
    assert plan.requested_detector_ids == ()
    assert plan.date_shift.enabled is False


def test_explicit_identity_is_deterministic_and_request_is_required() -> None:
    resolver = CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG.domain
    identity = PrepareAnalysisRequestOptions(ClinicalPreparePrivacyConfig.identity())
    first = resolver.resolve(
        config=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
        request_options=identity,
    )
    second = resolver.resolve(
        config=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
        request_options=identity,
    )
    assert first == second
    assert first.privacy_enabled is False

    with pytest.raises(TypeError, match="request_options"):
        resolver.resolve(
            config=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
            request_options=None,  # type: ignore[arg-type]
        )


def test_unknown_program_is_conditional_on_program_owned_data() -> None:
    identity = _resolve(program_id=None)
    regex_only = _resolve(
        ("regex",),
        date_shift_explicit=False,
        program_id=None,
    )
    assert identity.requested_detector_ids == ()
    assert regex_only.requested_detector_ids == ("regex",)

    with pytest.raises(ClinicalPrepareAnalysisResolutionError, match="unknown"):
        _resolve(
            ("registry",),
            date_shift_explicit=False,
            program_id="unknown_program",
        )


def test_date_shift_only_succeeds_with_unknown_program() -> None:
    plan = _resolve(
        (),
        date_shift_explicit=True,
        program_id=None,
    )
    assert plan.requested_detector_ids == ()
    assert plan.date_shift.enabled is True
    assert plan.date_shift.effective_offset_days == (
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.date_shift_offset_days
    )
    assert plan.date_shift.offset_source == "profile"


def test_program_scoped_registry_isolates_two_programs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program_a = _program("program_a", "ALIAS_ONLY_A")
    program_b = _program("program_b", "ALIAS_ONLY_B")
    programs = {program.canonical_id: program for program in (program_a, program_b)}
    monkeypatch.setattr(
        resolver_module,
        "get_clinical_program",
        lambda program_id: programs.get(program_id),
    )

    plan_a = _resolve(
        ("registry",),
        date_shift_explicit=False,
        program_id="program_a",
    )
    plan_b = _resolve(
        ("registry",),
        date_shift_explicit=False,
        program_id="program_b",
    )
    spec_a = plan_a.detector_specs[0]
    spec_b = plan_b.detector_specs[0]
    assert isinstance(spec_a, ResolvedRegistryDetectorSpec)
    assert isinstance(spec_b, ResolvedRegistryDetectorSpec)
    aliases_a = {alias for entry in spec_a.entries for alias in entry.aliases}
    aliases_b = {alias for entry in spec_b.entries for alias in entry.aliases}
    assert "ALIAS_ONLY_A" in aliases_a
    assert "ALIAS_ONLY_B" not in aliases_a
    assert "ALIAS_ONLY_B" in aliases_b
    assert "ALIAS_ONLY_A" not in aliases_b

    candidates_a = spec_a.build().detect("ALIAS_ONLY_A and ALIAS_ONLY_B")
    candidates_b = spec_b.build().detect("ALIAS_ONLY_A and ALIAS_ONLY_B")
    assert [candidate.original_text for candidate in candidates_a] == ["ALIAS_ONLY_A"]
    assert [candidate.original_text for candidate in candidates_b] == ["ALIAS_ONLY_B"]


def test_existing_single_program_registry_export_is_semantically_identical() -> None:
    program = get_clinical_program("clinical_program_001")
    assert program is not None
    assert export_clinical_registry_entries_for_program(program) == tuple(
        export_clinical_registry_entries()
    )


def test_regex_rules_are_resolved_by_installed_selector() -> None:
    plan = _resolve(("regex",), date_shift_explicit=False, program_id=None)
    spec = plan.detector_specs[0]
    assert spec.rules == tuple(CLINICAL_TRIAL_DOC_REGEX_RULES_ZH)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("privacy_config", "match"),
    [
        (
            ClinicalPreparePrivacyConfig(
                enabled=True,
                registry_enabled=False,
                regex_rule_set_ref="missing_regex_rules",
                uie_config_ref=None,
                date_shift_enabled=False,
                clinical_program_id=None,
            ),
            "regex rule-set ref",
        ),
        (
            ClinicalPreparePrivacyConfig(
                enabled=True,
                registry_enabled=False,
                regex_rule_set_ref=None,
                uie_config_ref="missing_uie_config",
                date_shift_enabled=False,
                clinical_program_id=None,
            ),
            "UIE config ref",
        ),
    ],
)
def test_unknown_installed_privacy_selector_fails(
    privacy_config: ClinicalPreparePrivacyConfig,
    match: str,
) -> None:
    with pytest.raises(ClinicalPrepareAnalysisResolutionError, match=match):
        CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG.domain.resolve(
            config=CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
            request_options=PrepareAnalysisRequestOptions(privacy_config),
        )


def test_uie_schema_and_actual_fallback_implementation_are_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resolver_module, "_uie_runtime_available", lambda: False)
    fallback_plan = _resolve(("uie",), date_shift_explicit=False, program_id=None)
    fallback_spec = fallback_plan.detector_specs[0]
    assert isinstance(fallback_spec, ResolvedUieDetectorSpec)
    assert fallback_spec.schema_items
    assert fallback_spec.denylist
    assert fallback_spec.implementation_id == "local_model"
    assert fallback_plan.effective_detector_ids == ("local_model",)
    assert fallback_plan.provenance.detector_implementations == (
        ("uie", "local_model"),
    )

    monkeypatch.setattr(resolver_module, "_uie_runtime_available", lambda: True)
    uie_plan = _resolve(("uie",), date_shift_explicit=False, program_id=None)
    assert uie_plan.effective_detector_ids == ("uie",)


def test_uie_unavailable_without_allowed_fallback_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    domain = ClinicalPrepareAnalysisDomainConfiguration(uie_fallback_allowed=False)
    config = PrepareAnalysisConfig(PrepareAnalysisConfigId("pacfg_test"), domain)
    monkeypatch.setattr(resolver_module, "_uie_runtime_available", lambda: False)

    with pytest.raises(
        ClinicalPrepareAnalysisResolutionError,
        match="fallback is disallowed",
    ):
        domain.resolve(
            config=config,
            request_options=PrepareAnalysisRequestOptions(
                ClinicalPreparePrivacyConfig(
                    enabled=True,
                    registry_enabled=False,
                    regex_rule_set_ref=None,
                    uie_config_ref=CLINICAL_UIE_CONFIG_ZH,
                    date_shift_enabled=False,
                    clinical_program_id=None,
                )
            ),
        )


def test_date_shift_uses_installed_profile_policy() -> None:
    plan = _resolve((), date_shift_explicit=True, program_id=None)
    assert plan.date_shift.enabled is True
    assert plan.date_shift.effective_offset_days == (
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.date_shift_offset_days
    )
    assert plan.date_shift.offset_source == "profile"


def test_registry_plus_date_shift_uses_program_for_registry_and_profile_for_shift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = _program("clinical_program_001", "ALIAS_ONLY")
    monkeypatch.setattr(
        resolver_module,
        "get_clinical_program",
        lambda program_id: program if program_id == "clinical_program_001" else None,
    )
    plan = _resolve(
        ("registry",),
        date_shift_explicit=True,
        program_id="clinical_program_001",
    )
    assert plan.requested_detector_ids == ("registry",)
    assert isinstance(plan.detector_specs[0], ResolvedRegistryDetectorSpec)
    assert plan.date_shift.enabled is True
    assert plan.date_shift.effective_offset_days == (
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.date_shift_offset_days
    )
    assert plan.date_shift.offset_source == "profile"


def test_clinical_program_record_does_not_own_date_shift_offset() -> None:
    program = get_clinical_program("clinical_program_001")
    assert program is not None
    assert not hasattr(program, "date_shift_offset_days")


@pytest.mark.parametrize(
    ("detector_ids", "date_shift_explicit", "privacy_enabled"),
    [
        ((), False, False),
        (("registry", "regex"), None, True),
        (("registry", "regex", "uie"), None, True),
        ((), True, True),
        (("registry", "regex"), False, True),
    ],
)
def test_current_effective_behavior_shapes_are_representable(
    detector_ids: tuple[str, ...],
    date_shift_explicit: bool | None,
    privacy_enabled: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resolver_module, "_uie_runtime_available", lambda: False)
    plan = _resolve(
        detector_ids,
        date_shift_explicit=date_shift_explicit,
        program_id="clinical_program_001" if "registry" in detector_ids else None,
    )

    assert plan.requested_detector_ids == detector_ids
    assert plan.privacy_enabled is privacy_enabled
    assert plan.date_shift.enabled is (
        bool(detector_ids) if date_shift_explicit is None else date_shift_explicit
    )


def test_plan_is_complete_immutable_and_execution_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resolver_module, "_uie_runtime_available", lambda: False)
    plan = _resolve(
        ("registry", "regex", "uie"),
        date_shift_explicit=False,
        program_id="clinical_program_001",
    )
    assert isinstance(plan, ClinicalResolvedPrepareAnalysisPlan)
    assert isinstance(plan, ResolvedPrepareAnalysisPlan)
    assert not any(
        isinstance(getattr(plan, field.name), ClinicalProgramRecord)
        for field in fields(plan)
    )
    assert plan.mask_policy.entity_types_to_mask == frozenset(
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.entity_types_to_mask
    )
    assert dict(plan.token_policy.token_prefixes) == CLINICAL_TOKEN_PREFIXES
    assert plan.result_extension_values == {}
    assert plan.privacy_provenance_stats == {
        "clinical_program_id": "clinical_program_001",
    }
    plan.validate_result_extension({"stage": "prepare_analysis"})
    assert plan.provenance.plugin_version
    assert plan.provenance.component_versions
    assert plan.provenance_descriptor["name"] == "clinical_trial_doc"
    assert plan.date_shift_enabled is False
    assert plan.date_shift_offset_days == 0
    plan.validate_result_extension({"stage": "prepare_analysis"})

    monkeypatch.setattr(
        resolver_module,
        "get_clinical_program",
        lambda _program_id: pytest.fail("plan performed a later Program lookup"),
    )
    monkeypatch.setattr(
        resolver_module,
        "export_clinical_registry_entries_for_program",
        lambda _program: pytest.fail("plan performed a later registry lookup"),
    )

    first_detector = plan.build_detector()
    second_detector = plan.build_detector()
    first_store = plan.new_mapping_store()
    second_store = plan.new_mapping_store()
    assert first_detector is not second_detector
    assert first_store is not second_store
    assert first_store.mapping is not second_store.mapping
    assert plan.build_privacy_profile() is not plan.build_privacy_profile()


def test_request_contract_has_no_raw_detector_or_date_fields() -> None:
    assert {field.name for field in fields(PrepareAnalysisRequestOptions)} == {
        "privacy_config"
    }
    assert not {
        "detectors",
        "registry",
        "regex",
        "uie",
        "date_shift",
    }.intersection(field.name for field in fields(PrepareAnalysisRequestOptions))


def test_s2_does_not_cut_over_runtime_or_step() -> None:
    production_paths = (
        BACKEND_ROOT / "runtime" / "prepare_analysis" / "operations.py",
        BACKEND_ROOT / "steps" / "prepare_analysis.py",
        BACKEND_ROOT / "scripts" / "stage_runners" / "prepare_analysis_runner.py",
    )
    forbidden = "plugins.clinical_trial_doc.prepare_analysis.resolver"
    for path in production_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert forbidden not in imported


def test_compatibility_policy_recipe_machinery_is_retired() -> None:
    source = Path(resolver_module.__file__).read_text(encoding="utf-8")
    for token in (
        "PrepareAnalysisPrivacyPolicyRef",
        "_ClinicalCompatibilityRecipe",
        "compatibility_recipes",
        "default_policy_ref",
        "_compatibility_policy_ref",
    ):
        assert token not in source
