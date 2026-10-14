"""Development previews only; product integrations call the Python APIs."""

from __future__ import annotations

# ruff: noqa: E402

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def task_scoped_directory(root: Path, task_run_id: str) -> Path:
    """Task IDs are single filename components, never caller-supplied paths."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", task_run_id):
        raise ValueError("task_run_id must be a single alphanumeric path component")
    return root / task_run_id


def default_preview_path(task_run_id: str, stage: str) -> Path:
    filenames = {
        "report": "qc_report.preview.json",
        "presentation": "qc_report.presentation.preview.json",
        "pdf": "qc_report.preview.pdf",
    }
    return (
        task_scoped_directory(Path("renders/qc_report"), task_run_id) / filenames[stage]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a QC report development preview."
    )
    parser.add_argument("--task-run-id", required=True)
    parser.add_argument(
        "--stage", choices=("report", "presentation", "pdf"), required=True
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    try:
        output = (
            args.output
            if args.output is not None
            else default_preview_path(args.task_run_id, args.stage)
        )
    except ValueError as exc:
        parser.error(str(exc))

    from task.clinical_trial_doc_qc.report_read import load_qc_report

    report = load_qc_report(
        project_root=args.project_root, task_run_id=args.task_run_id
    )
    if args.stage == "report":
        content = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    else:
        from application.qc_report.presentation import build_qc_report_presentation

        presentation = build_qc_report_presentation(report)
        if args.stage == "presentation":
            content = json.dumps(
                asdict(presentation), ensure_ascii=False, indent=2
            ).encode("utf-8")
        else:
            from renderers.qc_report import render_qc_report_pdf

            content = render_qc_report_pdf(presentation)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
