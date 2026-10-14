"""Behavioral guard: prepare_analysis_runner does not accept raw source files."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.stage_runners import prepare_analysis_runner


def test_prepare_analysis_runner_rejects_file_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docx = tmp_path / "sample.docx"
    docx.write_bytes(b"not a real docx")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_analysis_runner.py",
            "--file",
            str(docx),
            "--language",
            "zh",
            "--clinical-program",
            "clinical_program_001",
        ],
    )

    with pytest.raises(SystemExit):
        prepare_analysis_runner.main()
