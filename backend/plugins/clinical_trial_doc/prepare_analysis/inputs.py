"""Reusable formal invocation inputs for clinical Prepare Analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from operations.prepare_analysis import (
    PrepareAnalysisPrivacyConfiguration,
    PrepareAnalysisRequestOptions,
)

CLINICAL_PREPARE_INPUT_SCHEMA_VERSION = "1"
CLINICAL_REGEX_RULE_SET_ZH = "clinical_regex_zh_v1"
CLINICAL_UIE_CONFIG_ZH = "clinical_uie_zh_v1"


def _validate_optional_ref(value: str | None, *, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")


def _validate_program_id(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    program_id = value.strip()
    if not program_id:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    return program_id


@dataclass(frozen=True, slots=True)
class ClinicalPreparePrivacyConfig(PrepareAnalysisPrivacyConfiguration):
    """Per-run selectors into one installed clinical privacy composition."""

    enabled: bool
    registry_enabled: bool
    regex_rule_set_ref: str | None
    uie_config_ref: str | None
    date_shift_enabled: bool
    clinical_program_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "enabled",
            "registry_enabled",
            "date_shift_enabled",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(f"{field_name} must be a bool")
        _validate_optional_ref(
            self.regex_rule_set_ref,
            field_name="regex_rule_set_ref",
        )
        _validate_optional_ref(self.uie_config_ref, field_name="uie_config_ref")
        _validate_program_id(
            self.clinical_program_id,
            field_name="clinical_program_id",
        )

        selected = (
            self.registry_enabled
            or self.regex_rule_set_ref is not None
            or self.uie_config_ref is not None
            or self.date_shift_enabled
        )
        if not self.enabled and selected:
            raise ValueError(
                "disabled privacy config must not select registry, regex, UIE, "
                "or date shift"
            )
        if self.enabled and not selected:
            raise ValueError("enabled privacy config must select at least one behavior")

        if not self.enabled:
            if self.registry_enabled:
                raise ValueError("disabled privacy config must not enable registry")
            if self.clinical_program_id is not None:
                raise ValueError(
                    "disabled privacy config must not include clinical_program_id"
                )
            return

        if self.registry_enabled:
            if self.clinical_program_id is None:
                raise ValueError(
                    "registry_enabled requires clinical_program_id in privacy config"
                )
        elif self.clinical_program_id is not None:
            raise ValueError(
                "clinical_program_id is only allowed when registry_enabled is true"
            )

    @classmethod
    def identity(cls) -> ClinicalPreparePrivacyConfig:
        return build_clinical_prepare_privacy_config(
            registry_enabled=False,
            regex_rule_set_ref=None,
            uie_config_ref=None,
            date_shift_enabled=False,
            clinical_program_id=None,
            enabled=False,
        )


def clinical_prepare_privacy_behaviors_selected(
    *,
    registry_enabled: bool,
    regex_rule_set_ref: str | None,
    uie_config_ref: str | None,
) -> bool:
    """Return whether any masking behavior other than date shift is selected."""

    return (
        registry_enabled
        or regex_rule_set_ref is not None
        or uie_config_ref is not None
    )


def resolve_clinical_prepare_date_shift_enabled(
    *,
    masking_behaviors_selected: bool,
    date_shift_explicit: bool | None,
) -> bool:
    """Resolve date-shift policy from explicit override or masking selection."""

    if date_shift_explicit is None:
        return masking_behaviors_selected
    return date_shift_explicit


def build_clinical_prepare_privacy_config(
    *,
    registry_enabled: bool,
    regex_rule_set_ref: str | None,
    uie_config_ref: str | None,
    date_shift_enabled: bool,
    clinical_program_id: str | None = None,
    enabled: bool | None = None,
) -> ClinicalPreparePrivacyConfig:
    """Construct one validated clinical Prepare privacy config from semantic fields."""

    behaviors_selected = clinical_prepare_privacy_behaviors_selected(
        registry_enabled=registry_enabled,
        regex_rule_set_ref=regex_rule_set_ref,
        uie_config_ref=uie_config_ref,
    )
    resolved_enabled = (
        behaviors_selected or date_shift_enabled
        if enabled is None
        else enabled
    )
    return ClinicalPreparePrivacyConfig(
        enabled=resolved_enabled,
        registry_enabled=registry_enabled,
        regex_rule_set_ref=regex_rule_set_ref,
        uie_config_ref=uie_config_ref,
        date_shift_enabled=date_shift_enabled,
        clinical_program_id=clinical_program_id,
    )


def _load_json_object(path: Path | str) -> dict[str, Any]:
    resolved = Path(path).resolve()
    with resolved.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"clinical Prepare input must be a JSON object: {resolved}")
    if payload.get("schema_version") != CLINICAL_PREPARE_INPUT_SCHEMA_VERSION:
        raise ValueError(
            "clinical Prepare input schema_version must be "
            f"{CLINICAL_PREPARE_INPUT_SCHEMA_VERSION!r}"
        )
    return payload


def _privacy_config_from_payload(payload: dict[str, Any]) -> ClinicalPreparePrivacyConfig:
    program_raw = payload.get("clinical_program_id")
    clinical_program_id = (
        _validate_program_id(program_raw, field_name="clinical_program_id")
        if program_raw is not None
        else None
    )
    return build_clinical_prepare_privacy_config(
        registry_enabled=payload["registry_enabled"],
        regex_rule_set_ref=payload.get("regex_rule_set_ref"),
        uie_config_ref=payload.get("uie_config_ref"),
        date_shift_enabled=payload["date_shift_enabled"],
        clinical_program_id=clinical_program_id,
        enabled=payload["enabled"],
    )


def load_clinical_prepare_request_options(
    path: Path | str | None = None,
) -> PrepareAnalysisRequestOptions:
    """Load clinical privacy config from JSON, or return identity when path is omitted."""

    if path is None:
        return PrepareAnalysisRequestOptions(
            privacy_config=ClinicalPreparePrivacyConfig.identity()
        )

    payload = _load_json_object(path)
    allowed = {
        "schema_version",
        "enabled",
        "registry_enabled",
        "clinical_program_id",
        "regex_rule_set_ref",
        "uie_config_ref",
        "date_shift_enabled",
    }
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        raise ValueError(
            "unknown clinical privacy input field(s): " + ", ".join(unexpected)
        )
    required = {"enabled", "registry_enabled", "date_shift_enabled"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(
            "missing clinical privacy input field(s): " + ", ".join(missing)
        )
    return PrepareAnalysisRequestOptions(
        privacy_config=_privacy_config_from_payload(payload)
    )


__all__ = [
    "CLINICAL_PREPARE_INPUT_SCHEMA_VERSION",
    "CLINICAL_REGEX_RULE_SET_ZH",
    "CLINICAL_UIE_CONFIG_ZH",
    "ClinicalPreparePrivacyConfig",
    "build_clinical_prepare_privacy_config",
    "clinical_prepare_privacy_behaviors_selected",
    "load_clinical_prepare_request_options",
    "resolve_clinical_prepare_date_shift_enabled",
]
