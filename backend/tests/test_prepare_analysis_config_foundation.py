"""Focused S1 tests for neutral Prepare Analysis contracts and config registry."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, fields
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.prepare_analysis import (
    DuplicatePrepareAnalysisConfigError,
    PrepareAnalysisConfig,
    PrepareAnalysisConfigId,
    PrepareAnalysisConfigRegistry,
    PrepareAnalysisDomainConfiguration,
    PrepareAnalysisDomainResolver,
    PrepareAnalysisPrivacyConfiguration,
    PrepareAnalysisRequestOptions,
    ResolvedPrepareAnalysisPlan,
    UnknownPrepareAnalysisConfigError,
)
from plugins.clinical_trial_doc.prepare_analysis import (
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG,
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    ClinicalPrepareAnalysisDomainConfiguration,
    ClinicalPreparePrivacyConfig,
    register_current_clinical_prepare_analysis_config,
)

NEUTRAL_PREPARE_ANALYSIS_ROOT = BACKEND_ROOT / "operations" / "prepare_analysis"


def test_clinical_side_registers_and_resolves_current_config() -> None:
    registry = PrepareAnalysisConfigRegistry()

    register_current_clinical_prepare_analysis_config(registry)

    resolved = registry.resolve(CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID)
    assert resolved is CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG
    assert isinstance(resolved.domain, ClinicalPrepareAnalysisDomainConfiguration)


def test_registry_rejects_unknown_and_duplicate_config_ids() -> None:
    registry = PrepareAnalysisConfigRegistry()
    register_current_clinical_prepare_analysis_config(registry)

    with pytest.raises(UnknownPrepareAnalysisConfigError, match="unknown"):
        registry.resolve(PrepareAnalysisConfigId("pacfg_missing"))
    with pytest.raises(DuplicatePrepareAnalysisConfigError, match="duplicate"):
        register_current_clinical_prepare_analysis_config(registry)


def test_registry_validates_type_boundary() -> None:
    registry = PrepareAnalysisConfigRegistry()

    with pytest.raises(TypeError, match="PrepareAnalysisConfig"):
        registry.register(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="PrepareAnalysisConfigId"):
        registry.resolve("pacfg_7f3a1c9e")  # type: ignore[arg-type]


def test_config_identity_is_opaque_and_not_normalized_or_parsed() -> None:
    @dataclass(frozen=True)
    class ArbitraryDomain(PrepareAnalysisDomainConfiguration):
        pass

    opaque_id = PrepareAnalysisConfigId("x.ib/zh:privacy-looking-but-opaque")
    config = PrepareAnalysisConfig(opaque_id, ArbitraryDomain())
    registry = PrepareAnalysisConfigRegistry()
    registry.register(config)

    assert registry.resolve(opaque_id) is config
    with pytest.raises(UnknownPrepareAnalysisConfigError):
        registry.resolve(PrepareAnalysisConfigId("x.ib/zh"))


@pytest.mark.parametrize("value", ["", " ", " leading", "trailing "])
def test_opaque_references_reject_invalid_structural_values(value: str) -> None:
    with pytest.raises(ValueError):
        PrepareAnalysisConfigId(value)


def test_static_config_rejects_invalid_structural_construction() -> None:
    config_id = PrepareAnalysisConfigId("pacfg_test")

    class MutableDomain(PrepareAnalysisDomainConfiguration):
        pass

    with pytest.raises(TypeError, match="PrepareAnalysisConfigId"):
        PrepareAnalysisConfig("pacfg_test", MutableDomain())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="PrepareAnalysisDomainConfiguration"):
        PrepareAnalysisConfig(config_id, object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="immutable dataclass"):
        PrepareAnalysisConfig(config_id, MutableDomain())


def test_request_options_carry_only_a_nominal_privacy_config() -> None:
    privacy_config = ClinicalPreparePrivacyConfig.identity()
    assert PrepareAnalysisRequestOptions(privacy_config).privacy_config is privacy_config
    assert isinstance(privacy_config, PrepareAnalysisPrivacyConfiguration)
    assert {field.name for field in fields(PrepareAnalysisRequestOptions)} == {
        "privacy_config"
    }

    with pytest.raises(TypeError, match="privacy_config"):
        PrepareAnalysisRequestOptions("registry,regex")  # type: ignore[arg-type]


def test_resolved_plan_and_domain_resolver_are_minimal_in_memory_protocols() -> None:
    @dataclass(frozen=True)
    class ImmutablePlan:
        prepare_analysis_config_id: PrepareAnalysisConfigId
        privacy_enabled: bool = False
        requested_detector_ids: tuple[str, ...] = ()
        effective_detector_ids: tuple[str, ...] = ()
        date_shift_enabled: bool = False
        date_shift_offset_days: int = 0

        @property
        def result_extension_values(self):
            return {}

        @property
        def provenance_descriptor(self):
            return {}

        @property
        def privacy_provenance_stats(self):
            return {}

        def build_detector(self):
            return object()

        def build_privacy_profile(self):
            return object()

        def new_mapping_store(self):
            return object()

        def validate_result_extension(self, payload):
            del payload

    class ResolverShape:
        def resolve(
            self,
            *,
            config: PrepareAnalysisConfig,
            request_options: PrepareAnalysisRequestOptions,
        ) -> ResolvedPrepareAnalysisPlan:
            del request_options
            return ImmutablePlan(config.prepare_analysis_config_id)

    plan = ImmutablePlan(PrepareAnalysisConfigId("pacfg_test"))
    assert isinstance(plan, ResolvedPrepareAnalysisPlan)
    assert isinstance(ResolverShape(), PrepareAnalysisDomainResolver)
    assert set(ResolvedPrepareAnalysisPlan.__annotations__) == set()
    assert {
        name
        for name in ResolvedPrepareAnalysisPlan.__dict__
        if not name.startswith("_")
    } == {
        "build_detector",
        "build_privacy_profile",
        "date_shift_enabled",
        "date_shift_offset_days",
        "effective_detector_ids",
        "new_mapping_store",
        "prepare_analysis_config_id",
        "privacy_enabled",
        "privacy_provenance_stats",
        "provenance_descriptor",
        "requested_detector_ids",
        "result_extension_values",
        "validate_result_extension",
    }


def test_neutral_prepare_analysis_modules_do_not_import_clinical_plugin() -> None:
    violations: list[str] = []
    for path in sorted(NEUTRAL_PREPARE_ANALYSIS_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            else:
                continue
            if any(
                name == "plugins.clinical_trial_doc"
                or name.startswith("plugins.clinical_trial_doc.")
                for name in imported
            ):
                violations.append(f"{path.name}: {imported}")

    assert not violations, "\n".join(violations)


def test_s1_does_not_add_persisted_contract_builders() -> None:
    module_names = {path.name for path in NEUTRAL_PREPARE_ANALYSIS_ROOT.glob("*.py")}
    assert module_names == {"__init__.py", "contracts.py", "registry.py"}
