"""Tests for the Product-level developer task runner."""

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RUN_PRODUCT_TASK_PATH = BACKEND_ROOT / "scripts" / "run_product_task.py"
IB_SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.task_lifecycle import load_task_lifecycle_manifest
from execution_flow.document_consistency_qc.flow_loader import load_flow_run_execution
from runtime.io import load_json
from application.clinical_trial_doc_consistency_qc.result_read_model import (
    DocumentConsistencyQcInternalResultReadModel,
    InternalResultFinding,
    InternalResultScopeResult,
)
from scripts import run_product_task
from task.clinical_trial_doc_qc.task_input import load_task_input_manifest
from tests.candidate_scope_isolation import (
    SHOWCASE_DOCX,
    bridge_test_resume_dependencies,
)


@contextmanager
def _installed_fake_llm_dependencies():
    dependencies = bridge_test_resume_dependencies()
    with (
        patch(
            "application.clinical_trial_doc_consistency_qc.execution."
            "materialize_installed_projection_runtime_dependencies",
            return_value=dependencies["projection_runtime_dependencies"],
        ),
        patch(
            "application.clinical_trial_doc_consistency_qc.execution."
            "_materialize_installed_evidence_source_preparation_execution_dependencies",
            return_value=dependencies[
                "evidence_source_preparation_execution_dependencies"
            ],
        ),
        patch(
            "application.clinical_trial_doc_consistency_qc.execution."
            "materialize_installed_evidence_comparison_execution_dependencies",
            return_value=dependencies["evidence_comparison_execution_dependencies"],
        ),
    ):
        yield


def test_direct_entry_exposes_only_product_level_commands() -> None:
    result = subprocess.run(
        [sys.executable, str(RUN_PRODUCT_TASK_PATH), "--help"],
        cwd=BACKEND_ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "{start,resume,run}" in result.stdout
    assert "--capability" not in result.stdout
    assert "--participant-slot" not in result.stdout
    assert "--flow-run-id" not in result.stdout
    assert "staging" not in result.stdout.lower()


@pytest.mark.parametrize("command", ["start", "resume", "run"])
def test_subcommand_help_does_not_expose_flow_level_inputs(command: str) -> None:
    result = subprocess.run(
        [sys.executable, str(RUN_PRODUCT_TASK_PATH), command, "--help"],
        cwd=BACKEND_ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--capability" not in result.stdout
    assert "--participant-slot" not in result.stdout
    assert "--flow-run-id" not in result.stdout
    assert "--candidate-scope-mode" not in result.stdout
    assert "staging" not in result.stdout.lower()


def test_single_document_arguments_build_product_source_slot(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    source.write_bytes(b"docx")
    privacy = tmp_path / "privacy.json"
    privacy.write_text("{}", encoding="utf-8")
    args = run_product_task._parse_args(
        [
            "start",
            "--task",
            "internal_dsur_qc",
            "--source",
            str(source),
            "--privacy-config",
            str(privacy),
        ]
    )

    sources, privacy_paths = run_product_task._build_start_inputs(args)

    assert sources == {"source": source.resolve()}
    assert privacy_paths == {"source": privacy.resolve()}


def test_cross_document_arguments_build_product_source_slots(tmp_path: Path) -> None:
    source_a = tmp_path / "dsur.docx"
    source_b = tmp_path / "ib.docx"
    source_a.write_bytes(b"dsur")
    source_b.write_bytes(b"ib")
    args = run_product_task._parse_args(
        [
            "start",
            "--task",
            "dsur_updated_ib_qc",
            "--source-a",
            str(source_a),
            "--source-b",
            str(source_b),
        ]
    )

    sources, privacy_paths = run_product_task._build_start_inputs(args)

    assert sources == {
        "source_a": source_a.resolve(),
        "source_b": source_b.resolve(),
    }
    assert privacy_paths == {"source_a": None, "source_b": None}


@pytest.mark.parametrize(
    "argv",
    [
        ["start", "--task", "internal_dsur_qc"],
        [
            "start",
            "--task",
            "internal_ib_qc",
            "--source-a",
            "a.docx",
            "--source-b",
            "b.docx",
        ],
        ["start", "--task", "dsur_updated_ib_qc", "--source-a", "a.docx"],
        [
            "start",
            "--task",
            "dsur_updated_ib_qc",
            "--source",
            "one.docx",
        ],
    ],
)
def test_start_rejects_source_arguments_outside_product_slot_contract(
    argv: list[str],
) -> None:
    args = run_product_task._parse_args(argv)

    with pytest.raises(SystemExit):
        run_product_task._build_start_inputs(args)


def test_start_runs_product_path_and_reports_reloaded_pause(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert SHOWCASE_DOCX.is_file()
    with _installed_fake_llm_dependencies():
        run_product_task.main(
            [
                "start",
                "--task",
                "internal_dsur_qc",
                "--source",
                str(SHOWCASE_DOCX),
                "--project-root",
                str(tmp_path),
                "--json",
            ]
        )

    output = json.loads(capsys.readouterr().out)
    task_run_id = output["task_run_id"]
    assert output["task_id"] == "internal_dsur_qc"
    assert output["flow_run_id"].startswith("document_consistency_qc_")
    assert output["product_phase"] == "flow_execution_requested"
    assert output["flow_outcome"] == "paused_at_candidate_scope"
    assert output["requires_user_action"] is True
    assert output["result_available"] is False
    assert Path(output["flow_run_summary_path"]).is_file()
    assert load_task_input_manifest(
        project_root=tmp_path,
        task_run_id=task_run_id,
    )["inputs"][0]["task_slot_id"] == "source"
    assert [
        event["event_type"]
        for event in load_task_lifecycle_manifest(
            project_root=tmp_path,
            task_run_id=task_run_id,
        )["events"]
    ] == [
        "input_admission_started",
        "flow_allocation_started",
        "flow_allocated",
        "flow_execution_requested",
    ]


def test_cross_document_start_persists_both_product_slots(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert SHOWCASE_DOCX.is_file()
    assert IB_SAMPLE_DOCX.is_file()
    with _installed_fake_llm_dependencies():
        run_product_task.main(
            [
                "start",
                "--task",
                "dsur_updated_ib_qc",
                "--source-a",
                str(SHOWCASE_DOCX),
                "--source-b",
                str(IB_SAMPLE_DOCX),
                "--project-root",
                str(tmp_path),
                "--json",
            ]
        )

    output = json.loads(capsys.readouterr().out)
    task_input = load_task_input_manifest(
        project_root=tmp_path,
        task_run_id=output["task_run_id"],
    )
    assert [item["task_slot_id"] for item in task_input["inputs"]] == [
        "source_a",
        "source_b",
    ]
    assert output["flow_outcome"] == "paused_at_candidate_scope"
    assert output["requires_user_action"] is True


def _start_paused_task(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> dict:
    with _installed_fake_llm_dependencies():
        run_product_task.main(
            [
                "start",
                "--task",
                "internal_dsur_qc",
                "--source",
                str(SHOWCASE_DOCX),
                "--project-root",
                str(tmp_path),
                "--json",
            ]
        )
    return json.loads(capsys.readouterr().out)


def test_resume_unchanged_uses_task_membership_and_loads_full_result(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    started = _start_paused_task(tmp_path, capsys)

    with _installed_fake_llm_dependencies():
        run_product_task.main(
            [
                "resume",
                "--task-run-id",
                started["task_run_id"],
                "--candidate-scope",
                "unchanged",
                "--project-root",
                str(tmp_path),
                "--load-result",
                "--json",
            ]
        )

    resumed = json.loads(capsys.readouterr().out)
    assert resumed["task_run_id"] == started["task_run_id"]
    assert resumed["flow_run_id"] == started["flow_run_id"]
    assert resumed["flow_outcome"] == "success"
    assert resumed["requires_user_action"] is False
    assert resumed["result_available"] is True
    assert resumed["result_loaded"] is True
    assert isinstance(resumed["finding_count"], int)

    execution = load_flow_run_execution(
        project_root=tmp_path,
        flow_run_id=resumed["flow_run_id"],
    )
    for slot in execution.slot_provenance:
        decision = load_json(Path(slot.candidate_scope_decision_path))
        assert {
            item["resolution"]["kind"] for item in decision["candidate_selections"]
        } == {"automatic_unchanged"}


def test_run_discards_in_memory_flow_identity_before_persisted_resume(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    real_start = run_product_task._start_product_task

    def _start_with_poisoned_memory_result(args):
        payload = real_start(args)
        payload["flow_run_id"] = "in_memory_flow_id_must_not_be_used"
        return payload

    with (
        _installed_fake_llm_dependencies(),
        patch.object(
            run_product_task,
            "_start_product_task",
            side_effect=_start_with_poisoned_memory_result,
        ),
    ):
        run_product_task.main(
            [
                "run",
                "--task",
                "internal_dsur_qc",
                "--source",
                str(SHOWCASE_DOCX),
                "--project-root",
                str(tmp_path),
                "--json",
            ]
        )

    output = json.loads(capsys.readouterr().out)
    assert output["flow_run_id"].startswith("document_consistency_qc_")
    assert output["flow_run_id"] != "in_memory_flow_id_must_not_be_used"
    assert output["flow_outcome"] == "success"
    assert output["result_available"] is True
    assert output["result_loaded"] is True


def test_load_result_summary_finding_count_uses_top_level_findings(
    tmp_path: Path,
) -> None:
    scope_without_findings = InternalResultScopeResult(
        slot_id="source",
        doc_id="doc-1",
        scope_id="scope-1",
        heading_path=("Safety",),
        outline_heading_block_id="block-1",
        semantic_module_id="clinical_safety",
        execution_status="success",
        has_successful_check=True,
    )
    findings = tuple(
        InternalResultFinding(
            finding_id=f"finding-{index}",
            label=f"label-{index}",
            conclusion="mismatch",
            comparison_mode_id="aggregate_evidence",
            evidence_refs=(),
            source_finding_ids=(f"source-{index}",),
        )
        for index in range(3)
    )
    result = DocumentConsistencyQcInternalResultReadModel(
        flow_id="document_consistency_qc",
        flow_run_id="document_consistency_qc_test",
        capability_id="clinical_trial_doc_consistency_qc",
        flow_status="success",
        comparison_run_status="success",
        finalization_status="final",
        fallback_comparison_modes=(),
        findings=findings,
        scope_results=(scope_without_findings,),
    )
    payload = {"result_available": True, "result_loaded": False}

    with patch.object(
        run_product_task,
        "load_document_consistency_qc_result",
        return_value=result,
    ):
        run_product_task._load_result_summary(
            payload,
            project_root=tmp_path,
            flow_run_id="document_consistency_qc_test",
            requested=True,
        )

    assert payload["result_loaded"] is True
    assert payload["finding_count"] == 3
    assert not hasattr(scope_without_findings, "findings")


def test_dsur_updated_ib_qc_completed_flow_reloads_without_result_probe_error(
    tmp_path: Path,
) -> None:
    from application.task_run import attach_flow_run, create_task_run
    from runtime.io import save_json
    from task.clinical_trial_doc_qc.task_run_read import load_task_run_page_context
    from tests.test_result_readiness import _fixture

    flow_run_id, summary = _fixture(tmp_path)
    summary["capability_id"] = "dsur_updated_ib"
    save_json(
        tmp_path
        / "runs"
        / "document_consistency_qc"
        / "test_internal_result"
        / "flow_run_summary.json",
        summary,
    )
    task_run_id = "task_run_20261012_test_dsur_reload"
    create_task_run(
        project_root=tmp_path,
        task_run_id=task_run_id,
        task_id="dsur_updated_ib_qc",
    )
    attach_flow_run(
        project_root=tmp_path,
        task_run_id=task_run_id,
        flow_id="document_consistency_qc",
        flow_run_id=flow_run_id,
    )

    context = load_task_run_page_context(
        project_root=tmp_path,
        task_run_id=task_run_id,
    )

    assert context.task_id == "dsur_updated_ib_qc"
    assert context.state.flow_outcome == "success"
    assert context.state.result_available is False
