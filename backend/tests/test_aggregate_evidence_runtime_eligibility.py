"""Split Aggregate Evidence assess vs eligibility phase tests."""

# ruff: noqa: SIM102
from __future__ import annotations

import ast
import sys
from dataclasses import fields
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    HEADING_SCOPE_ELIGIBILITY_FILENAME,
    resolve_source_scope_assessments_path,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import SCOPE_ASSESSMENTS_FILENAME
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    ASSESS_HEADING_SCOPES_OPERATION,
    EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION,
    AGGREGATE_EVIDENCE_FORM_ID,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade import (
    run_aggregate_evidence_assess_heading_scopes,
    run_aggregate_evidence_evaluate_heading_scope_eligibility,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.execution_types import (
    AggregateEvidenceAssessmentExecution,
    AggregateEvidenceEligibilityExecution,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
)
from runtime.io import load_json, save_json
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assess import run_assess
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.eligibility import run_eligibility
from tests.evidence_source_preparation_phase_test_helpers import (
    installed_assess_phase_kwargs,
    installed_eligibility_phase_kwargs,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stop_points import (
    EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP,
    EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP,
    resolve_through_operation_for_stop_point,
)
from runtime.run_index import build_aggregate_evidence_eligibility_index_document
from scripts.stage_runners.evidence_source_preparation.aggregate_evidence import eligibility_runner
from tests.test_heading_scope_eligibility import (
    _canonical_scope_assessments_path,
    _scope_assessments_payload,
)
from tests.test_aggregate_evidence_runtime_prepare import _run_route_to_prepare

CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "clinical_safety"
    / "aggregate_evidence"
)

ADAPTER_PATH = CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT / "phase_facade.py"
ASSESS_PLUGIN_PATH = CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT / "assess.py"
ELIGIBILITY_POLICY_PATH = (
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT / "heading_scope_eligibility_policy.py"
)
SOURCE_PREPARATION_AGGREGATE_EVIDENCE_DIR = CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def _write_valid_scope_assessments(
    tmp_path: Path,
    *,
    assess_run_id: str = "assess_source_run",
) -> Path:
    payload = _scope_assessments_payload()
    path = _canonical_scope_assessments_path(tmp_path, assess_run_id=assess_run_id)
    save_json(path, payload)
    save_json(
        path.parent / "run_summary.json",
        {
            "run_id": assess_run_id,
            "stage": "evidence_source_preparation",
            "doc_id": payload["doc_id"],
            "zone_key": payload["zone_key"],
            "stats": {"phase": "assess"},
        },
    )
    return path


def test_assess_adapter_does_not_call_eligibility_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refs = _run_route_to_prepare(tmp_path)
    assessment_input = load_json(refs["assessment_input"])
    runtime_context = load_json(refs["prepare_out"] / "assessment_runtime_context.json")

    def _fail_eligibility(**_kwargs: object) -> list[dict]:
        raise AssertionError("eligibility policy must not run during assess")

    monkeypatch.setattr(
        "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.heading_scope_eligibility_policy.build_heading_scope_eligibility_entries",
        _fail_eligibility,
    )

    execution = run_aggregate_evidence_assess_heading_scopes(
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
        assessment_profile_name=str(assessment_input["assessment_profile_ref"]),
        llm_mode="mock",
    )

    assert isinstance(execution, AggregateEvidenceAssessmentExecution)
    assert execution.scope_assessments["artifact_type"] == "scope_assessments"
    field_names = {field.name for field in fields(execution)}
    assert "heading_scope_eligibility" not in field_names
    assert "auto_included_scope_count" not in field_names


def test_eligibility_adapter_does_not_call_assessment_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope_path = _write_valid_scope_assessments(tmp_path)
    scope_assessments = load_json(scope_path)
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
        build_source_scope_assessments_ref,
    )

    source_scope_assessments_ref = build_source_scope_assessments_ref(
        scope_assessments_payload=scope_assessments,
        scope_assessments_path=scope_path,
        project_root=tmp_path,
        run_id="assess_source_run",
    )

    def _fail_assess(**_kwargs: object) -> dict:
        raise AssertionError("assessment runtime must not run during eligibility")

    monkeypatch.setattr(
        "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assess.run_aggregate_evidence_assess",
        _fail_assess,
    )

    execution = run_aggregate_evidence_evaluate_heading_scope_eligibility(
        scope_assessments=scope_assessments,
        source_scope_assessments_ref=source_scope_assessments_ref,
        build_heading_scope_eligibility_entries=(
            CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING.build_heading_scope_eligibility_entries
        ),
    )

    assert isinstance(execution, AggregateEvidenceEligibilityExecution)
    assert execution.heading_scope_eligibility["artifact_type"] == "heading_scope_eligibility"
    assert execution.heading_scope_eligibility["phase"] == "eligibility"
    reloaded = load_json(scope_path)
    assert reloaded == scope_assessments

    again = run_aggregate_evidence_evaluate_heading_scope_eligibility(
        scope_assessments=scope_assessments,
        source_scope_assessments_ref=source_scope_assessments_ref,
        build_heading_scope_eligibility_entries=(
            CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING.build_heading_scope_eligibility_entries
        ),
    )
    assert again.heading_scope_eligibility == execution.heading_scope_eligibility


def test_assess_runtime_does_not_write_eligibility_artifacts(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    assess_out = tmp_path / "assess_only"
    result = run_assess(
        **installed_assess_phase_kwargs(),
        assessment_input_path=refs["assessment_input"],
        output_dir=assess_out,
        run_id="assess_split_test",
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )
    assert result.scope_assessments_path.is_file()
    assert not (assess_out / HEADING_SCOPE_ELIGIBILITY_FILENAME).exists()
    assert not (assess_out / "scope_processing_plan.json").exists()
    summary = load_json(result.run_summary_path)
    assert summary["stats"]["phase"] == "assess"
    assert summary["stats"]["completed_operation"] == ASSESS_HEADING_SCOPES_OPERATION
    assert "auto_included_scope_count" not in summary.get("stats", {})


def test_eligibility_runner_requires_assessments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["eligibility_runner.py"])
    with pytest.raises(SystemExit):
        eligibility_runner.main()


def test_eligibility_runner_rejects_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing_scope_assessments.json"
    monkeypatch.setattr(sys, "argv", ["eligibility_runner.py", "--assessments", str(missing)])
    with pytest.raises(SystemExit):
        eligibility_runner.main()


def test_eligibility_runner_rejects_non_scope_assessments_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad_path = tmp_path / "not_scope_assessments.json"
    save_json(bad_path, {"artifact_type": "assessment_input", "schema_version": "0.1.0"})
    monkeypatch.setattr(
        sys,
        "argv",
        ["eligibility_runner.py", "--assessments", str(bad_path), "--out", str(tmp_path / "out")],
    )
    with pytest.raises(SystemExit):
        eligibility_runner.main()


def test_eligibility_runner_success_writes_only_eligibility_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scope_path = _write_valid_scope_assessments(tmp_path)
    out_dir = tmp_path / "eligibility_out"
    monkeypatch.setattr(eligibility_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eligibility_runner.py",
            "--assessments",
            str(scope_path),
            "--out",
            str(out_dir),
            "--run-id",
            "eligibility_runner_test",
        ],
    )
    eligibility_runner.main()

    captured = capsys.readouterr()
    assert "phase=eligibility" in captured.out
    assert EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION in captured.out
    assert (out_dir / HEADING_SCOPE_ELIGIBILITY_FILENAME).is_file()
    assert (out_dir / "run_summary.json").is_file()
    assert not (out_dir / SCOPE_ASSESSMENTS_FILENAME).exists()
    assert load_json(scope_path) == _scope_assessments_payload()

    eligibility = load_json(out_dir / HEADING_SCOPE_ELIGIBILITY_FILENAME)
    source_ref = eligibility["source_scope_assessments_ref"]
    assert source_ref["run_id"] == "assess_source_run"
    assert source_ref["path"].startswith(
        "runs/evidence_source_preparation/assess/assess_source_run/"
    )
    assert source_ref["path"].endswith(SCOPE_ASSESSMENTS_FILENAME)
    assert not Path(source_ref["path"]).is_absolute()
    assert resolve_source_scope_assessments_path(
        project_root=tmp_path,
        source_ref=source_ref,
    ) == scope_path.resolve()
    summary = load_json(out_dir / "run_summary.json")
    assert summary["stats"]["source_scope_assessments_ref"] == source_ref


def test_same_assessments_produce_two_independent_eligibility_runs(
    tmp_path: Path,
) -> None:
    scope_path = _write_valid_scope_assessments(tmp_path)
    scope_before = scope_path.read_text(encoding="utf-8")

    out_a = tmp_path / "eligibility_a"
    out_b = tmp_path / "eligibility_b"
    result_a = run_eligibility(
        **installed_eligibility_phase_kwargs(),
        artifact_reference_root=tmp_path,
        scope_assessments_path=scope_path,
        output_dir=out_a,
        run_id="eligibility_a",
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )
    result_b = run_eligibility(
        **installed_eligibility_phase_kwargs(),
        artifact_reference_root=tmp_path,
        scope_assessments_path=scope_path,
        output_dir=out_b,
        run_id="eligibility_b",
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )

    assert result_a.run_id != result_b.run_id
    assert result_a.heading_scope_eligibility_path.is_file()
    assert result_b.heading_scope_eligibility_path.is_file()
    assert result_a.heading_scope_eligibility_path != result_b.heading_scope_eligibility_path
    assert scope_path.read_text(encoding="utf-8") == scope_before

    env_a = load_json(result_a.heading_scope_eligibility_path)
    env_b = load_json(result_b.heading_scope_eligibility_path)
    assert env_a["source_scope_assessments_ref"] == env_b["source_scope_assessments_ref"]
    assert env_a["source_scope_assessments_ref"]["run_id"] == "assess_source_run"


@pytest.mark.parametrize(
    "source_location",
    ["canonical_without_summary", "workspace_with_summary", "outside_with_summary"],
)
def test_eligibility_reference_uses_execution_workspace(
    tmp_path: Path,
    source_location: str,
) -> None:
    workspace = tmp_path / "workspace"
    source_run_id = "source_assess_run"
    if source_location == "canonical_without_summary":
        source_path = _write_valid_scope_assessments(
            workspace, assess_run_id=source_run_id
        )
        (source_path.parent / "run_summary.json").unlink()
    else:
        source_base = (
            workspace
            if source_location == "workspace_with_summary"
            else tmp_path / "outside"
        )
        source_path = source_base / "imported" / SCOPE_ASSESSMENTS_FILENAME
        source_path.parent.mkdir(parents=True)
        save_json(source_path, _scope_assessments_payload())
        save_json(
            source_path.parent / "run_summary.json",
            {
                "run_id": source_run_id,
                "stage": "evidence_source_preparation",
                "stats": {"phase": "assess"},
            },
        )

    result = run_eligibility(
        **installed_eligibility_phase_kwargs(),
        artifact_reference_root=workspace,
        scope_assessments_path=source_path,
        output_dir=workspace / "eligibility_out",
        run_id="eligibility_workspace_ref",
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )
    envelope = load_json(result.heading_scope_eligibility_path)
    source_ref = envelope["source_scope_assessments_ref"]
    assert source_ref["run_id"] == source_run_id
    if source_location == "outside_with_summary":
        assert source_ref["path"] == source_path.resolve().as_posix()
        assert Path(source_ref["path"]).is_absolute()
        # Absolute historical references remain readable even with another base.
        resolution_base = tmp_path / "different_workspace"
    else:
        assert source_ref["path"] == source_path.relative_to(workspace).as_posix()
        assert not Path(source_ref["path"]).is_absolute()
        resolution_base = workspace
    assert resolve_source_scope_assessments_path(
        project_root=resolution_base, source_ref=source_ref
    ) == source_path.resolve()
    summary = load_json(result.run_summary_path)
    assert summary["stats"]["source_scope_assessments_ref"] == source_ref


def test_stop_at_through_mapping() -> None:
    assert resolve_through_operation_for_stop_point(
        EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP
    ) == (
        ASSESS_HEADING_SCOPES_OPERATION
    )
    assert resolve_through_operation_for_stop_point(
        EVIDENCE_SOURCE_PREPARATION_ELIGIBILITY_STEP
    ) == (
        EVALUATE_HEADING_SCOPE_ELIGIBILITY_OPERATION
    )


def test_eligibility_index_lists_only_eligibility_outputs(
    tmp_path: Path,
) -> None:
    scope_path = _write_valid_scope_assessments(tmp_path)
    out_dir = tmp_path / "eligibility_index"
    run_eligibility(
        **installed_eligibility_phase_kwargs(),
        artifact_reference_root=tmp_path,
        scope_assessments_path=scope_path,
        output_dir=out_dir,
        run_id="index_test",
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )
    doc = build_aggregate_evidence_eligibility_index_document(
        bundle=load_json(scope_path),
        out_dir=out_dir,
        index_root=out_dir,
        zone_key="ib_clinical_safety_zh",
    )
    assert "heading_scope_eligibility" in doc.outputs
    assert "scope_assessments" not in doc.outputs
    assert "scope_processing_plan" not in doc.outputs


def test_import_boundaries() -> None:
    adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
    assert "heading_scope_eligibility_policy" not in adapter_source
    assess_block = adapter_source.split("def run_aggregate_evidence_assess_heading_scopes", 1)[1]
    assess_block = assess_block.split("def run_aggregate_evidence_evaluate_heading_scope_eligibility", 1)[0]
    assert "heading_scope_eligibility_policy" not in assess_block
    assert "build_heading_scope_eligibility" not in assess_block

    assert (
        SOURCE_PREPARATION_AGGREGATE_EVIDENCE_DIR / "heading_scope_eligibility_policy.py"
    ).is_file()
    assert not (
        BACKEND_ROOT
        / "plugins"
        / "clinical_trial_doc"
        / "comparisons"
        / "aggregate_evidence"
    ).exists()

    policy_names = _imported_module_names(ELIGIBILITY_POLICY_PATH)
    forbidden_policy = (
        "core.tagging",
        "plugins.clinical_trial_doc.tagging",
        "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assess",
    )
    for prefix in forbidden_policy:
        assert not any(name.startswith(prefix) for name in policy_names), prefix

    assess_names = _imported_module_names(ASSESS_PLUGIN_PATH)
    assert "heading_scope_eligibility_policy" not in "".join(assess_names)
