from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.prepare_analysis import (
    CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID,
    STANDALONE_RUNTIME_CONTEXT_LABEL,
    build_clinical_prepare_analysis_standalone_invocation,
    build_current_clinical_prepare_analysis_config_registry,
)


def _bundle() -> dict:
    return {"doc_id": "d", "document_meta": {"language": "zh"}}


def test_standalone_composition_uses_installed_config_registry() -> None:
    invocation = build_clinical_prepare_analysis_standalone_invocation(
        clinical_program_id="clinical_program_001",
        bundle=_bundle(),
    )
    assert (
        invocation.prepare_analysis_config_id
        == CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID
    )
    installed = build_current_clinical_prepare_analysis_config_registry()
    assert (
        invocation.config_registry.resolve(
            CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID
        ).domain
        == installed.resolve(CURRENT_CLINICAL_PREPARE_ANALYSIS_CONFIG_ID).domain
    )
    assert invocation.runtime_context_label == STANDALONE_RUNTIME_CONTEXT_LABEL
    assert invocation.request_options.privacy_config.enabled is False


def test_standalone_composition_does_not_accept_legacy_profile_selectors() -> None:
    with pytest.raises(TypeError):
        build_clinical_prepare_analysis_standalone_invocation(
            clinical_program_id="clinical_program_001",
            bundle=_bundle(),
            privacy_profile_spec="plugins.clinical_trial_doc.privacy.profile:CLINICAL_TRIAL_DOC_PRIVACY_PROFILE",
        )


def test_prepare_analysis_runner_has_no_profile_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        '{"doc_id":"d","document_meta":{"language":"zh"}}', encoding="utf-8"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_analysis_runner.py",
            "--bundle",
            str(bundle),
            "--clinical-program",
            "clinical_program_001",
        ],
    )
    from scripts.stage_runners import prepare_analysis_runner

    source = (BACKEND_ROOT / "scripts/stage_runners/prepare_analysis_runner.py").read_text(
        encoding="utf-8"
    )
    assert "--privacy-profile" not in source
    assert "--privacy-profile-config" not in source
    assert not hasattr(prepare_analysis_runner.parse_args(), "privacy_profile")
