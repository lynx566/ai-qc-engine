"""PR3 closure: canonical process runners and evidence lineage."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
    EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import SCOPE_ASSESSMENTS_FILENAME
from runtime.io import load_json
from scripts.stage_runners.evidence_source_preparation.aggregate_evidence import (
    assess_runner,
    prepare_runner,
)
from tests.test_aggregate_evidence_runtime_prepare import _run_route_to_prepare

AGGREGATE_ASSESSMENTS_FILENAME = "aggregate_assessments.json"


def test_aggregate_evidence_prepare_runner_writes_process_artifacts(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    paths = refs["paths"]
    out_dir = tmp_path / "legacy_prepare_out"

    argv = [
        "--routed-aggregate-bundle",
        str(refs["aggregate_bundle"]),
        "--coverage-bundle",
        str(paths["coverage"]),
        "--block-manifest",
        str(paths["block_manifest"]),
        "--doc-meta-bundle",
        str(paths["doc_meta_bundle"]),
        "--analysis-bundle",
        str(paths["analysis"]),
        "--out",
        str(out_dir),
    ]
    prepare_runner.main(argv)

    assessment_input = load_json(out_dir / "assessment_input.json")
    assert assessment_input["stage"] == EVIDENCE_SOURCE_PREPARATION_STAGE
    assert assessment_input["phase"] == EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE
    assert "comparison_type" not in assessment_input
    assert not (out_dir / "llm_input_aggregate.json").exists()
    assert not (out_dir / "routing_manifest.json").exists()


def test_aggregate_evidence_assess_runner_writes_process_artifacts(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    prepare_out = refs["prepare_out"]
    assessment_input_path = prepare_out / "assessment_input.json"
    assess_out = tmp_path / "legacy_assess_out"

    assess_runner.main(
        [
            "--assessment-input",
            str(assessment_input_path),
            "--out",
            str(assess_out),
            "--llm",
            "mock",
        ]
    )

    scope_assessments = load_json(assess_out / SCOPE_ASSESSMENTS_FILENAME)
    assert scope_assessments["stage"] == EVIDENCE_SOURCE_PREPARATION_STAGE
    assert scope_assessments["phase"] == EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE
    assert "comparison_type" not in scope_assessments
    assert (assess_out / "scope_assessment_review.json").is_file()
    assert not (assess_out / AGGREGATE_ASSESSMENTS_FILENAME).exists()
    assert not (assess_out / "tag_output.json").exists()


def test_canonical_code_does_not_import_legacy_writers() -> None:
    import runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assess as assess_runtime
    import runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare as prepare_runtime
    import runtime.projected_source_route_stage as route_runtime

    prepare_source = Path(prepare_runtime.__file__).read_text(encoding="utf-8")
    assess_source = Path(assess_runtime.__file__).read_text(encoding="utf-8")
    route_source = Path(route_runtime.__file__).read_text(encoding="utf-8")

    assert "run_tag_prepare_stage" not in prepare_source
    assert "run_tag_stage" not in assess_source
    for source in (prepare_source, assess_source, route_source):
        assert "overview_decompose_mock_runner" not in source
        assert "overview_decompose_mock" not in source
        assert "_resolve_selection_path" not in source
