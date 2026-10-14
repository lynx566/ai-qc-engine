from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.prepare_analysis import (
    build_clinical_prepare_analysis_standalone_invocation,
)
from plugins.clinical_trial_doc.prepare_analysis import resolver as clinical_resolver
from privacy.config import (
    PRIVACY_DETECTORS_CLI_CONFLICT_MSG,
    PrivacyConfig,
    resolve_after_extract_cli,
)


def _bundle_argv(tmp_path: Path, *extra: str) -> list[str]:
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        '{"doc_id":"d","document_meta":{"language":"zh"}}', encoding="utf-8"
    )
    return [
        "prepare_analysis_runner.py",
        "--bundle",
        str(bundle),
        "--clinical-program",
        "clinical_program_001",
        *extra,
    ]


def test_privacy_detectors_shortcut_maps_to_after_extract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        _bundle_argv(tmp_path, "--privacy-detectors", "registry,regex"),
    )
    from scripts.stage_runners import prepare_analysis_runner

    args = prepare_analysis_runner.parse_args()
    config = PrivacyConfig.from_cli(after_extract=args.privacy_after_extract_detectors)
    assert config.transform_detectors("after_extract") == ["registry", "regex"]
    assert config.transform_detectors("after_filter") == []


def test_privacy_detectors_empty_string_selects_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", _bundle_argv(tmp_path, "--privacy-detectors", ""))
    from scripts.stage_runners import prepare_analysis_runner

    args = prepare_analysis_runner.parse_args()
    assert (
        PrivacyConfig.from_cli(
            after_extract=args.privacy_after_extract_detectors
        ).transform_detectors("after_extract")
        == []
    )


def test_privacy_detector_alias_conflict_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        _bundle_argv(
            tmp_path,
            "--privacy-detectors",
            "registry",
            "--privacy-after-extract-detectors",
            "regex",
        ),
    )
    from scripts.stage_runners import prepare_analysis_runner

    with pytest.raises(SystemExit):
        prepare_analysis_runner.parse_args()


def test_resolve_after_extract_cli_conflict_message() -> None:
    with pytest.raises(ValueError, match=PRIVACY_DETECTORS_CLI_CONFLICT_MSG):
        resolve_after_extract_cli(
            privacy_detectors="registry",
            privacy_after_extract_detectors="regex",
        )


def test_prepare_after_filter_cli_surface_is_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        _bundle_argv(tmp_path, "--privacy-after-filter-detectors", "uie"),
    )
    from scripts.stage_runners import prepare_analysis_runner

    with pytest.raises(SystemExit):
        prepare_analysis_runner.parse_args()


def test_standalone_adapter_fails_fast_on_after_filter_config() -> None:
    config = PrivacyConfig.from_cli(after_filter="uie")
    with pytest.raises(ValueError, match="after_filter detectors are unsupported"):
        build_clinical_prepare_analysis_standalone_invocation(
            clinical_program_id="clinical_program_001",
            bundle={"doc_id": "d", "document_meta": {"language": "zh"}},
            privacy_config=config,
        )


@pytest.mark.parametrize(
    ("detectors", "date_shift", "enabled"),
    [
        ("registry,regex", None, True),
        (None, None, False),
        (None, True, True),
        ("registry,regex", False, False),
    ],
)
def test_standalone_translation_preserves_date_activation(
    detectors: str | None,
    date_shift: bool | None,
    enabled: bool,
) -> None:
    invocation = build_clinical_prepare_analysis_standalone_invocation(
        clinical_program_id="clinical_program_001",
        bundle={"doc_id": "d", "document_meta": {"language": "zh"}},
        privacy_after_extract_detectors=detectors,
        date_shift_explicit=date_shift,
    )
    config = invocation.config_registry.resolve(invocation.prepare_analysis_config_id)
    plan = config.domain.resolve(
        config=config,
        request_options=invocation.request_options,
    )
    assert plan.date_shift_enabled is enabled
    assert plan.privacy_enabled is bool(detectors) or enabled


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("--date-shift", True), ("--no-date-shift", False)],
)
def test_prepare_runner_date_shift_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
    expected: bool,
) -> None:
    monkeypatch.setattr(sys, "argv", _bundle_argv(tmp_path, flag))
    from scripts.stage_runners import prepare_analysis_runner

    assert prepare_analysis_runner.parse_args().date_shift_explicit is expected


def test_prepare_runner_date_shift_default_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", _bundle_argv(tmp_path))
    from scripts.stage_runners import prepare_analysis_runner

    assert prepare_analysis_runner.parse_args().date_shift_explicit is None


def test_standalone_translation_requires_program_identity_for_registry() -> None:
    with pytest.raises(RuntimeError, match="clinical_program_id must be set for registry"):
        build_clinical_prepare_analysis_standalone_invocation(
            clinical_program_id=None,
            bundle={"doc_id": "d", "document_meta": {"language": "zh"}},
            privacy_after_extract_detectors="registry",
        )


def test_standalone_uie_selection_uses_resolver_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clinical_resolver, "_uie_runtime_available", lambda: False)
    invocation = build_clinical_prepare_analysis_standalone_invocation(
        clinical_program_id="clinical_program_001",
        bundle={"doc_id": "d", "document_meta": {"language": "zh"}},
        privacy_after_extract_detectors="uie",
        date_shift_explicit=False,
    )
    config = invocation.config_registry.resolve(invocation.prepare_analysis_config_id)
    plan = config.domain.resolve(
        config=config,
        request_options=invocation.request_options,
    )
    assert plan.requested_detector_ids == ("uie",)
    assert plan.effective_detector_ids == ("local_model",)


def test_standalone_date_shift_is_resolver_owned_profile_policy() -> None:
    invocation = build_clinical_prepare_analysis_standalone_invocation(
        clinical_program_id="clinical_program_001",
        bundle={"doc_id": "d", "document_meta": {"language": "zh"}},
        date_shift_explicit=True,
    )
    config = invocation.config_registry.resolve(invocation.prepare_analysis_config_id)
    plan = config.domain.resolve(
        config=config,
        request_options=invocation.request_options,
    )
    assert plan.date_shift.offset_source == "profile"
    assert plan.date_shift_offset_days > 0
