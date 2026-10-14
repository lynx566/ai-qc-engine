"""Aggregate Evidence assemble runtime tests."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME,
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assemble import (
    run_assemble,
)
from runtime.io import load_json, save_json
from tests.current_aggregate_assemble_test_helpers import (
    build_current_aggregate_assemble_inputs,
)
from tests.evidence_source_preparation_phase_test_helpers import (
    installed_assemble_phase_kwargs,
)


def test_aggregate_evidence_runtime_assemble_writes_artifacts(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    assessment_input, runtime_context, scope_assessments, eligibility = (
        build_current_aggregate_assemble_inputs()
    )
    save_json(fixture_dir / "assessment_input.json", assessment_input)
    save_json(fixture_dir / "assessment_runtime_context.json", runtime_context)
    save_json(fixture_dir / "scope_assessments.json", scope_assessments)
    save_json(fixture_dir / "heading_scope_eligibility.json", eligibility)

    out_dir = tmp_path / "assemble_out"
    result = run_assemble(
        **installed_assemble_phase_kwargs(),
        assessment_input_path=fixture_dir / "assessment_input.json",
        assessment_runtime_context_path=fixture_dir / "assessment_runtime_context.json",
        scope_assessments_path=fixture_dir / "scope_assessments.json",
        heading_scope_eligibility_path=fixture_dir / "heading_scope_eligibility.json",
        output_dir=out_dir,
        run_id="assemble_test_run",
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )

    assert result.output_dir == out_dir.resolve()
    assert result.assembled_heading_scope_count == 2
    assert result.excluded_heading_scope_count == 1
    assert (out_dir / AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME).is_file()
    assert (out_dir / "run_summary.json").is_file()

    summary = load_json(out_dir / "run_summary.json")
    assert summary["stats"]["phase"] == EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE
    assert summary["stats"]["input_heading_scope_count"] == 3
    assert summary["stats"]["assembled_heading_scope_count"] == 2

    artifact = load_json(out_dir / AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME)
    assert artifact["schema_version"] == AGGREGATE_EVIDENCE_SOURCE_BUNDLE_SCHEMA_VERSION
    assert {"stage", "phase", "zone_key", "coverage"}.isdisjoint(artifact)
