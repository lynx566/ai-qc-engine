"""CLI adapter for the Request File Intake runtime operation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.request_file_intake import run_request_file_intake_operation
from runtime.run_provenance import snapshot_git_provenance_before_run
from scripts.stage_runners.common import ensure_project_on_path, resolve_existing_file


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Request File Intake: hash one submitted file and emit a formal "
            "request_file_intake_result artifact."
        )
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Source file path",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Optional output directory "
            "(default: runs/request_file_intake/<run_id>/)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    ensure_project_on_path()
    argv = list(argv) if argv is not None else sys.argv[1:]
    if sum(1 for token in argv if token == "--file") > 1:
        raise SystemExit("only one --file is supported")
    args = parse_args(argv)
    source_file = resolve_existing_file(args.file, flag_name="--file")
    git_prov = snapshot_git_provenance_before_run(root=PROJECT_ROOT)
    try:
        report = run_request_file_intake_operation(
            project_root=PROJECT_ROOT,
            source_file=source_file,
            output_dir=args.output_dir,
            git_provenance=git_prov,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    for message in report.messages:
        print(message)


if __name__ == "__main__":
    main()
