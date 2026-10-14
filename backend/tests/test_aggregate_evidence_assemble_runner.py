"""Process.assemble CLI runner tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE,
)
from runtime.io import load_json, save_json
from scripts.stage_runners.evidence_source_preparation.aggregate_evidence import (
    assemble_runner,
)
from tests.current_aggregate_assemble_test_helpers import (
    build_current_aggregate_assemble_inputs,
)


def test_aggregate_evidence_assemble_runner_default_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture_dir = tmp_path / "prepare_fixture"
    fixture_dir.mkdir()
    assessment_input, runtime_context, scope_assessments, eligibility = (
        build_current_aggregate_assemble_inputs()
    )
    save_json(fixture_dir / "assessment_input.json", assessment_input)
    save_json(fixture_dir / "assessment_runtime_context.json", runtime_context)
    save_json(fixture_dir / "scope_assessments.json", scope_assessments)
    save_json(fixture_dir / "heading_scope_eligibility.json", eligibility)

    output_root = tmp_path / "runs" / "evidence_source_preparation" / "assemble"
    monkeypatch.setattr(assemble_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assemble_runner.py",
            "--assessment-input",
            str(fixture_dir / "assessment_input.json"),
            "--assessment-runtime-context",
            str(fixture_dir / "assessment_runtime_context.json"),
            "--assessments",
            str(fixture_dir / "scope_assessments.json"),
            "--eligibility",
            str(fixture_dir / "heading_scope_eligibility.json"),
            "--output-root",
            str(output_root),
            "--run-id",
            "assemble_cli_test",
        ],
    )
    assemble_runner.main()

    artifact_dir = (
        output_root
        / "assemble_cli_test"
        / "doc_current_assemble"
        / "clinical_safety"
        / "aggregate_evidence"
    )
    assert (artifact_dir / AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME).is_file()
    summary = load_json(artifact_dir / "run_summary.json")
    assert summary["stats"]["phase"] == EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE
    assert summary["stats"]["assembled_heading_scope_count"] == 2


def test_aggregate_evidence_assemble_runner_missing_input_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assemble_runner.py",
            "--assessment-input",
            str(missing),
            "--assessment-runtime-context",
            str(missing),
            "--assessments",
            str(missing),
            "--eligibility",
            str(missing),
        ],
    )
    with pytest.raises(SystemExit):
        assemble_runner.main()
