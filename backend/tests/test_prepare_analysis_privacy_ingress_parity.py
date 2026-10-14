"""Parity guards for clinical Prepare privacy JSON vs standalone CLI ingress."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.prepare_analysis import (
    CLINICAL_REGEX_RULE_SET_ZH,
    build_clinical_prepare_analysis_standalone_invocation,
    load_clinical_prepare_request_options,
)
from plugins.clinical_trial_doc.prepare_analysis.inputs import (
    CLINICAL_PREPARE_INPUT_SCHEMA_VERSION,
)

CANONICAL_PROGRAM = "clinical_program_001"


def _bundle() -> dict[str, object]:
    return {"doc_id": "d", "document_meta": {"language": "zh"}}


def _write_privacy_json(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "privacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _privacy_config_from_json(tmp_path: Path, payload: dict[str, object]):
    return load_clinical_prepare_request_options(
        _write_privacy_json(tmp_path, payload)
    ).privacy_config


def _privacy_config_from_cli(**kwargs: object):
    return build_clinical_prepare_analysis_standalone_invocation(
        bundle=_bundle(),
        clinical_program_id=CANONICAL_PROGRAM,
        **kwargs,
    ).request_options.privacy_config


@pytest.mark.parametrize(
    ("cli_kwargs", "json_payload"),
    [
        pytest.param(
            {},
            {
                "schema_version": CLINICAL_PREPARE_INPUT_SCHEMA_VERSION,
                "enabled": False,
                "registry_enabled": False,
                "date_shift_enabled": False,
            },
            id="identity",
        ),
        pytest.param(
            {"privacy_after_extract_detectors": "registry,regex"},
            {
                "schema_version": CLINICAL_PREPARE_INPUT_SCHEMA_VERSION,
                "enabled": True,
                "registry_enabled": True,
                "regex_rule_set_ref": CLINICAL_REGEX_RULE_SET_ZH,
                "date_shift_enabled": True,
                "clinical_program_id": CANONICAL_PROGRAM,
            },
            id="registry-regex",
        ),
        pytest.param(
            {"date_shift_explicit": True, "privacy_after_extract_detectors": ""},
            {
                "schema_version": CLINICAL_PREPARE_INPUT_SCHEMA_VERSION,
                "enabled": True,
                "registry_enabled": False,
                "date_shift_enabled": True,
            },
            id="dates-only",
        ),
        pytest.param(
            {
                "privacy_after_extract_detectors": "registry,regex",
                "date_shift_explicit": False,
            },
            {
                "schema_version": CLINICAL_PREPARE_INPUT_SCHEMA_VERSION,
                "enabled": True,
                "registry_enabled": True,
                "regex_rule_set_ref": CLINICAL_REGEX_RULE_SET_ZH,
                "date_shift_enabled": False,
                "clinical_program_id": CANONICAL_PROGRAM,
            },
            id="mask-no-date",
        ),
    ],
)
def test_cli_and_json_privacy_config_semantics_match(
    tmp_path: Path,
    cli_kwargs: dict[str, object],
    json_payload: dict[str, object],
) -> None:
    cli_config = _privacy_config_from_cli(**cli_kwargs)
    json_config = _privacy_config_from_json(tmp_path, json_payload)
    assert asdict(cli_config) == asdict(json_config)


def test_identity_json_path_matches_explicit_none_loader() -> None:
    assert load_clinical_prepare_request_options().privacy_config == (
        _privacy_config_from_cli()
    )
