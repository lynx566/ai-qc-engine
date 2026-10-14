"""Actual preview CLI serialization through formal APIs."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
from pypdf import PdfReader

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RUNNER = BACKEND_ROOT / "scripts/tools/qc_report_runner.py"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(RUNNER), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.mark.parametrize("stage", ["report", "presentation", "pdf"])
def test_real_preview_stages_write_requested_output(
    stage, representative_qc_task_run, tmp_path
):
    project_root, task_run_id = representative_qc_task_run
    output = tmp_path / "nested output" / f"preview.{stage}"
    result = run_cli(
        "--task-run-id",
        task_run_id,
        "--stage",
        stage,
        "--output",
        str(output),
        "--project-root",
        str(project_root),
    )
    assert result.returncode == 0, result.stderr
    assert output.is_file()
    if stage == "pdf":
        reader = PdfReader(output)
        text = "".join(page.extract_text() for page in reader.pages)
        assert "质控审查报告" in text and "DSUR质控" in text
    else:
        value = json.loads(output.read_text(encoding="utf-8"))
        if stage == "report":
            assert value["artifact_type"] == "qc_report"
            assert len(value["findings"]) == 18
        else:
            assert value["report_header"]["task"]["display_name"] == "DSUR质控"
            assert value["result_summary"]["finding_counts"] == [
                {"label": "fail", "display_name": "存在错误", "count": 12},
                {"label": "need_review", "display_name": "可能有误", "count": 6},
            ]


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--task-run-id", "x", "--stage", "html", "--output", "unused.pdf"],
        ["--task-run-id", "x"],
    ],
)
def test_invalid_cli_arguments_fail_with_usage(args):
    result = run_cli(*args)
    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_failed_load_does_not_write_preview(tmp_path):
    output = tmp_path / "absent.pdf"
    result = run_cli(
        "--task-run-id",
        "task_run_missing",
        "--stage",
        "pdf",
        "--output",
        str(output),
        "--project-root",
        str(tmp_path),
    )
    assert result.returncode != 0
    assert not output.exists()


@pytest.mark.parametrize(
    "stage,filename",
    [
        ("report", "qc_report.preview.json"),
        ("presentation", "qc_report.presentation.preview.json"),
        ("pdf", "qc_report.preview.pdf"),
    ],
)
def test_default_preview_paths_are_task_scoped(
    stage, filename, representative_qc_task_run
):
    project_root, task_run_id = representative_qc_task_run
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(RUNNER),
            "--task-run-id",
            task_run_id,
            "--stage",
            stage,
            "--project-root",
            str(project_root),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert (
        project_root / "renders/qc_report" / task_run_id / filename
    ).is_file()
    assert not (project_root / ".tmp").exists()


def test_different_task_ids_have_distinct_default_paths():
    sys.path.insert(0, str(BACKEND_ROOT))
    from scripts.tools.qc_report_runner import default_preview_path

    assert default_preview_path("task_run_a", "pdf") == Path(
        "renders/qc_report/task_run_a/qc_report.preview.pdf"
    )
    assert default_preview_path("task_run_b", "pdf") == Path(
        "renders/qc_report/task_run_b/qc_report.preview.pdf"
    )


@pytest.mark.parametrize("task_id", ["..", "../outside", "a/b", "a\\b", "C:escape", ""])
def test_default_paths_reject_non_component_task_ids(task_id):
    sys.path.insert(0, str(BACKEND_ROOT))
    from scripts.tools.qc_report_runner import default_preview_path

    with pytest.raises(ValueError):
        default_preview_path(task_id, "pdf")
