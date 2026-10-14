"""Formal clinical Prepare invocation input contracts and JSON adapters."""

from __future__ import annotations

import json
import sys
from dataclasses import fields
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.prepare_analysis import PrepareAnalysisRequestOptions
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    CLINICAL_REGEX_RULE_SET_ZH,
    CLINICAL_UIE_CONFIG_ZH,
    ClinicalPreparePrivacyConfig,
    load_clinical_prepare_request_options,
)


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_clinical_privacy_config_fields_are_minimal_and_identity_is_explicit() -> None:
    assert {field.name for field in fields(ClinicalPreparePrivacyConfig)} == {
        "enabled",
        "registry_enabled",
        "regex_rule_set_ref",
        "uie_config_ref",
        "date_shift_enabled",
        "clinical_program_id",
    }
    identity = ClinicalPreparePrivacyConfig.identity()
    assert identity == ClinicalPreparePrivacyConfig(
        enabled=False,
        registry_enabled=False,
        regex_rule_set_ref=None,
        uie_config_ref=None,
        date_shift_enabled=False,
        clinical_program_id=None,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"registry_enabled": True},
        {"regex_rule_set_ref": CLINICAL_REGEX_RULE_SET_ZH},
        {"uie_config_ref": CLINICAL_UIE_CONFIG_ZH},
        {"date_shift_enabled": True},
    ],
)
def test_disabled_privacy_config_rejects_selected_behavior(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "enabled": False,
        "registry_enabled": False,
        "regex_rule_set_ref": None,
        "uie_config_ref": None,
        "date_shift_enabled": False,
        "clinical_program_id": None,
    }
    values.update(overrides)
    with pytest.raises(ValueError, match="disabled privacy config"):
        ClinicalPreparePrivacyConfig(**values)  # type: ignore[arg-type]


def test_enabled_privacy_config_requires_one_selection() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ClinicalPreparePrivacyConfig(
            enabled=True,
            registry_enabled=False,
            regex_rule_set_ref=None,
            uie_config_ref=None,
            date_shift_enabled=False,
            clinical_program_id=None,
        )


def test_registry_enabled_requires_clinical_program_id_in_privacy_config() -> None:
    with pytest.raises(ValueError, match="registry_enabled requires clinical_program_id"):
        ClinicalPreparePrivacyConfig(
            enabled=True,
            registry_enabled=True,
            regex_rule_set_ref=None,
            uie_config_ref=None,
            date_shift_enabled=False,
            clinical_program_id=None,
        )


def test_clinical_program_id_only_allowed_when_registry_enabled() -> None:
    with pytest.raises(ValueError, match="only allowed when registry_enabled"):
        ClinicalPreparePrivacyConfig(
            enabled=True,
            registry_enabled=False,
            regex_rule_set_ref=CLINICAL_REGEX_RULE_SET_ZH,
            uie_config_ref=None,
            date_shift_enabled=False,
            clinical_program_id="clinical_program_001",
        )


def test_load_clinical_prepare_request_options_none_returns_identity() -> None:
    request_options = load_clinical_prepare_request_options()
    assert isinstance(request_options, PrepareAnalysisRequestOptions)
    assert isinstance(request_options.privacy_config, ClinicalPreparePrivacyConfig)
    assert request_options.privacy_config == ClinicalPreparePrivacyConfig.identity()


def test_versioned_json_loader_returns_formal_neutral_envelopes(
    tmp_path: Path,
) -> None:
    privacy_path = _write_json(
        tmp_path / "privacy.json",
        {
            "schema_version": "1",
            "enabled": True,
            "registry_enabled": True,
            "clinical_program_id": "clinical_program_001",
            "regex_rule_set_ref": CLINICAL_REGEX_RULE_SET_ZH,
            "uie_config_ref": None,
            "date_shift_enabled": True,
        },
    )

    request_options = load_clinical_prepare_request_options(privacy_path)

    assert isinstance(request_options, PrepareAnalysisRequestOptions)
    assert isinstance(request_options.privacy_config, ClinicalPreparePrivacyConfig)
    privacy_config = request_options.privacy_config
    assert privacy_config.registry_enabled is True
    assert privacy_config.clinical_program_id == "clinical_program_001"
    assert privacy_config.regex_rule_set_ref == CLINICAL_REGEX_RULE_SET_ZH
    assert privacy_config.date_shift_enabled is True


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": "2", "enabled": True, "registry_enabled": False, "date_shift_enabled": False},
        {
            "schema_version": "1",
            "enabled": True,
            "registry_enabled": True,
            "date_shift_enabled": False,
        },
        {
            "schema_version": "1",
            "enabled": True,
            "registry_enabled": False,
            "date_shift_enabled": False,
            "unexpected_field": "value",
        },
    ],
)
def test_privacy_loader_rejects_invalid_schema_or_fields(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    path = _write_json(tmp_path / "privacy.json", payload)
    with pytest.raises(ValueError):
        load_clinical_prepare_request_options(path)
