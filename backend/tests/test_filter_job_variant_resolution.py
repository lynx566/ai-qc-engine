"""Tests for Filter job variant resolution infrastructure."""

from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.filter.variant_registry import (
    build_filter_job_variants,
    resolve_filter_job_variant,
)
from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
)
from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from plugins.clinical_trial_doc.filter_profiles.common.models import (
    ClinicalTrialFilterConfig,
    HeadingFilterPolicy,
)
from plugins.clinical_trial_doc.filter_profiles.csr.clinical_safety_zh import (
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.csr.overview_zh import (
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.dsur.clinical_safety_zh import (
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.dsur.dsur_overview_zh import (
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)

_INSTALLED_CONFIGS = (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    IB_OVERVIEW_FILTER_PROFILE_ZH,
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
)

_EXPECTED_JOB_IDS = {
    "ib_clinical_safety_zh": "ib_clinical_safety",
    "ib_overview_zh": "ib_overview",
    "dsur_clinical_safety_zh": "dsur_clinical_safety",
    "dsur_overview_zh": "dsur_overview",
    "csr_clinical_safety_zh": "csr_clinical_safety",
    "csr_overview_zh": "csr_overview",
}

_MINIMAL_POLICY = HeadingFilterPolicy(
    heading_match_mode="contains",
    heading_terms=("安全性",),
)


def test_clinical_trial_filter_config_carries_filter_job_id_not_policy() -> None:
    config_fields = {field.name for field in fields(ClinicalTrialFilterConfig)}
    assert "filter_job_id" in config_fields
    policy_fields = {field.name for field in fields(HeadingFilterPolicy)}
    assert "filter_job_id" not in policy_fields


def test_all_six_installed_configs_declare_filter_job_id() -> None:
    for config in _INSTALLED_CONFIGS:
        expected = _EXPECTED_JOB_IDS[config.zone_config_name]
        assert config.filter_job_id == expected


def test_installed_variant_index_contains_all_zh_pairs() -> None:
    expected_keys = {
        ("ib_clinical_safety", "zh"),
        ("ib_overview", "zh"),
        ("dsur_clinical_safety", "zh"),
        ("dsur_overview", "zh"),
        ("csr_clinical_safety", "zh"),
        ("csr_overview", "zh"),
    }
    assert set(INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS) == expected_keys
    for key in expected_keys:
        config = INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS[key]
        assert (
            INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS[config.zone_config_name]
            is config
        )


def test_application_composition_exposes_filter_job_variants() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    assert (
        composition.filter_job_variants
        is INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS
    )


def test_resolve_known_job_and_language() -> None:
    resolved = resolve_filter_job_variant(
        filter_job_id="dsur_clinical_safety",
        language="zh",
        filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
    )
    assert resolved is DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH


def test_resolve_independent_of_zone_config_name() -> None:
    config = ClinicalTrialFilterConfig(
        zone_config_name="completely_different_internal_name",
        zone_config_version="0.2.0",
        filter_job_id="dsur_clinical_safety",
        language="zh",
        strategy_id="heading_zone",
        policy=_MINIMAL_POLICY,
    )
    variants = build_filter_job_variants((config,))
    resolved = resolve_filter_job_variant(
        filter_job_id="dsur_clinical_safety",
        language="zh",
        filter_job_variants=variants,
    )
    assert resolved is config
    assert resolved.zone_config_name == "completely_different_internal_name"


def test_resolve_opaque_job_id_without_metadata_derivation() -> None:
    config = ClinicalTrialFilterConfig(
        zone_config_name="opaque_catalog_key",
        zone_config_version="0.2.0",
        filter_job_id="job_alpha",
        language="zh",
        strategy_id="heading_zone",
        policy=_MINIMAL_POLICY,
    )
    variants = build_filter_job_variants((config,))
    resolved = resolve_filter_job_variant(
        filter_job_id="job_alpha",
        language="zh",
        filter_job_variants=variants,
    )
    assert resolved is config


def test_unknown_filter_job() -> None:
    with pytest.raises(ValueError, match="unknown Filter job: 'not_real'"):
        resolve_filter_job_variant(
            filter_job_id="not_real",
            language="zh",
            filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
        )


def test_unsupported_language_variant() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "unsupported language variant for Filter job "
            "'dsur_clinical_safety': language='en'"
        ),
    ):
        resolve_filter_job_variant(
            filter_job_id="dsur_clinical_safety",
            language="en",
            filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
        )


def test_unknown_job_and_unsupported_language_are_distinguishable() -> None:
    unknown = resolve_filter_job_variant
    variants = INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS

    with pytest.raises(ValueError, match="unknown Filter job"):
        unknown(
            filter_job_id="ib_not_real",
            language="zh",
            filter_job_variants=variants,
        )

    with pytest.raises(ValueError, match="unsupported language variant"):
        unknown(
            filter_job_id="dsur_clinical_safety",
            language="en",
            filter_job_variants=variants,
        )


def test_missing_language_required() -> None:
    with pytest.raises(ValueError, match="language is required"):
        resolve_filter_job_variant(
            filter_job_id="dsur_clinical_safety",
            language=None,
            filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
        )


def test_empty_language_rejected() -> None:
    with pytest.raises(ValueError, match="language must be a non-empty string"):
        resolve_filter_job_variant(
            filter_job_id="dsur_clinical_safety",
            language="",
            filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
        )


def test_empty_filter_job_id_rejected() -> None:
    with pytest.raises(ValueError, match="filter_job_id must be a non-empty string"):
        resolve_filter_job_variant(
            filter_job_id="",
            language="zh",
            filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
        )


def test_duplicate_variant_rejected_at_index_build() -> None:
    config_a = ClinicalTrialFilterConfig(
        zone_config_name="duplicate_a",
        zone_config_version="0.2.0",
        filter_job_id="same_job",
        language="zh",
        policy=_MINIMAL_POLICY,
    )
    config_b = ClinicalTrialFilterConfig(
        zone_config_name="duplicate_b",
        zone_config_version="0.2.0",
        filter_job_id="same_job",
        language="zh",
        policy=_MINIMAL_POLICY,
    )
    with pytest.raises(ValueError, match="duplicate installed Filter variant"):
        build_filter_job_variants((config_a, config_b))


def test_sparse_variants() -> None:
    job_a_zh = ClinicalTrialFilterConfig(
        zone_config_name="job_a_zh",
        zone_config_version="0.2.0",
        filter_job_id="job_a",
        language="zh",
        policy=_MINIMAL_POLICY,
    )
    job_a_en = ClinicalTrialFilterConfig(
        zone_config_name="job_a_en",
        zone_config_version="0.2.0",
        filter_job_id="job_a",
        language="en",
        policy=_MINIMAL_POLICY,
    )
    job_b_zh = ClinicalTrialFilterConfig(
        zone_config_name="job_b_zh",
        zone_config_version="0.2.0",
        filter_job_id="job_b",
        language="zh",
        policy=_MINIMAL_POLICY,
    )
    variants = build_filter_job_variants((job_a_zh, job_a_en, job_b_zh))

    assert (
        resolve_filter_job_variant(
            filter_job_id="job_a",
            language="en",
            filter_job_variants=variants,
        )
        is job_a_en
    )
    with pytest.raises(ValueError, match="unsupported language variant"):
        resolve_filter_job_variant(
            filter_job_id="job_b",
            language="en",
            filter_job_variants=variants,
        )


def test_filter_job_id_empty_at_construction() -> None:
    with pytest.raises(ValueError, match="filter_job_id must be a non-empty string"):
        ClinicalTrialFilterConfig(
            zone_config_name="invalid",
            zone_config_version="0.2.0",
            filter_job_id="",
            language="zh",
            policy=_MINIMAL_POLICY,
        )


def test_variant_registry_module_is_system_neutral() -> None:
    source = (
        BACKEND_ROOT / "operations" / "filter" / "variant_registry.py"
    ).read_text(encoding="utf-8")
    for token in (
        "application",
        "clinical_trial_doc",
        "capability.",
        "runtime.",
        "runner",
    ):
        assert token not in source


def test_flow_imports_canonical_filter_variant_resolver() -> None:
    import execution_flow.document_consistency_qc.flow as flow_module
    from operations.filter.variant_registry import resolve_filter_job_variant

    assert flow_module.resolve_filter_job_variant is resolve_filter_job_variant

    flow_source = (
        BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "flow.py"
    ).read_text(encoding="utf-8")
    assert "operations.filter.variant_registry" in flow_source
    assert "resolve_filter_job_variant:" not in flow_source.split(
        "def run_document_consistency_qc_flow", 1
    )[1].split(")", 1)[0]
