"""Extract report utilities use canonical Extract runtime."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.extract_installation import (
    resolve_installed_extract_config_id,
)
from scripts.stage_runners import extract_reports

SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_minimal_001.docx"
)


def test_run_extract_uses_shared_intake_launch_extract_sequence() -> None:
    assert SAMPLE_DOCX.is_file()
    fake_bundle = SimpleNamespace(doc_id="ib_extract_minimal_001", document_meta={})
    fake_extract_report = SimpleNamespace(
        result=SimpleNamespace(
            document=SimpleNamespace(bundle=fake_bundle),
        )
    )
    fake_sequence = SimpleNamespace(extract_report=fake_extract_report)
    captured: dict = {}

    def _fake_sequence(**kwargs):
        captured.update(kwargs)
        return fake_sequence

    with patch.object(
        extract_reports,
        "run_document_processing_intake_launch_extract",
        side_effect=_fake_sequence,
    ) as sequence_mock:
        result = extract_reports.run_extract(SAMPLE_DOCX)

    assert result is fake_bundle
    sequence_mock.assert_called_once_with(
        project_root=extract_reports.PROJECT_ROOT,
        source_file=SAMPLE_DOCX,
        extract_config_id=resolve_installed_extract_config_id(),
        git_provenance=None,
    )
