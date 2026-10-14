"""Disposable 180 DPI PDF page images for manual QA; never a runtime adapter."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tools.qc_report_runner import (  # noqa: E402
    default_preview_path,
    task_scoped_directory,
)


def render_preview_pages(
    task_run_id: str,
    pdf_path: Path | None = None,
    *,
    workspace_root: Path = Path("."),
) -> tuple[Path, ...]:
    """Replace only one task's numbered page PNGs and return their paths."""
    workspace = workspace_root.resolve()
    target = task_scoped_directory(workspace / ".tmp/pdfs/qc_report", task_run_id)
    if target.resolve() != target:
        raise ValueError("QA directory redirects from its intended TaskRun location")
    source = (
        pdf_path
        if pdf_path is not None
        else workspace / default_preview_path(task_run_id, "pdf")
    )
    import pymupdf  # Development-only optional dependency.

    with pymupdf.open(source) as document:
        if not document.is_pdf:
            raise ValueError("QA input must be a PDF")
        target.mkdir(parents=True, exist_ok=True)
        old_pages = [
            p
            for p in target.iterdir()
            if re.fullmatch(r"page-\d{2,}\.png", p.name) and p.is_file()
        ]
        # Verify every resolved deletion target before unlinking any of them.
        if any(not p.resolve().is_relative_to(target) for p in old_pages):
            raise ValueError("QA page redirects outside its intended TaskRun directory")
        for page in old_pages:
            page.unlink()
        paths = []
        for number, page in enumerate(document, 1):
            path = target / f"page-{number:02}.png"
            page.get_pixmap(dpi=180).save(path)
            paths.append(path)
        return tuple(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render disposable QC report PDF QA images at 180 DPI."
    )
    parser.add_argument("--task-run-id", required=True)
    parser.add_argument(
        "--pdf", type=Path, help="Override the task-scoped PDF preview input."
    )
    args = parser.parse_args(argv)
    render_preview_pages(args.task_run_id, args.pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
