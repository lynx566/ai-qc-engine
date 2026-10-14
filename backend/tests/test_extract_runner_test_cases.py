from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.stage_runners import extract_runner


def test_validate_mode_accepts_test_cases_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_runner.py",
            "validate",
            "--test-cases",
            "tests/fixtures/clinical_trial_doc/extract/extract_test_cases.json",
        ],
    )
    args = extract_runner.parse_args()
    assert (
        args.test_cases
        == "tests/fixtures/clinical_trial_doc/extract/extract_test_cases.json"
    )


def test_validate_mode_rejects_manifest_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_runner.py",
            "validate",
            "--manifest",
            "tests/fixtures/clinical_trial_doc/extract/extract_test_cases.json",
        ],
    )
    with pytest.raises(SystemExit):
        extract_runner.parse_args()


def test_validate_mode_requires_test_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["extract_runner.py", "validate"])
    with pytest.raises(SystemExit):
        extract_runner.parse_args()


def test_help_lists_test_cases_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["extract_runner.py", "--help"])
    with pytest.raises(SystemExit):
        extract_runner.parse_args()
    help_text = capsys.readouterr().out
    assert "--test-cases" in help_text
    assert "extract validation test cases JSON" in help_text
    assert "--manifest" not in help_text
