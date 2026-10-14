from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.clinical_trial_doc_consistency_qc.extract_installation import (  # noqa: E402
    resolve_installed_extract_config_id,
)
from execution_flow.document_processing_sequence import (  # noqa: E402
    run_document_processing_intake_launch_extract,
)
from runtime.run_provenance import snapshot_git_provenance_before_run  # noqa: E402
from runtime.run_ids import utc_run_stamp  # noqa: E402
from scripts.stage_runners.extract_reports import (  # noqa: E402
    run_extract_test_cases_report,
    write_single_review,
)
from scripts.stage_runners.common import (  # noqa: E402
    ensure_project_on_path,
    resolve_existing_file,
)


def _ensure_project_on_path() -> None:
    ensure_project_on_path()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="extract runner")

    parser.add_argument(
        "mode",
        choices=["inspect", "export", "validate"],
        help="Run mode: inspect, export, or validate (batch via test cases JSON)",
    )

    parser.add_argument(
        "--file",
        action="append",
        type=str,
        default=None,
        help="Docx file path for inspect/export mode (repeatable for multiple docs)",
    )

    parser.add_argument(
        "--test-cases",
        type=str,
        default=None,
        help="Path to extract validation test cases JSON",
    )

    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help=(
            "Export mode only: output directory for bundle.json and run_summary.json. "
            "Default: runs/extract/<YYYYMMDD_HHMMSSZ>/<doc_id>/"
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include verbose JSON dumps in validate report",
    )

    parser.add_argument(
        "--export-slices",
        action="store_true",
        help="Export mode only: also write slices/ (content_blocks, table_blocks, …)",
    )

    args = parser.parse_args()
    if args.mode in {"inspect", "export"} and not args.file:
        parser.error(f"{args.mode} mode requires --file")
    if args.mode == "validate" and args.test_cases is None:
        parser.error("validate mode requires --test-cases")
    return args


def _collect_target_files(file_arg: str | list[str] | None) -> list[Path]:
    if file_arg is None:
        return []
    paths = file_arg if isinstance(file_arg, list) else [file_arg]
    return [resolve_existing_file(path, flag_name="--file") for path in paths]


def main() -> None:
    _ensure_project_on_path()
    args = parse_args()
    git_prov = snapshot_git_provenance_before_run(root=PROJECT_ROOT)

    if args.mode == "inspect":
        session_stamp = utc_run_stamp()
        for file_path in _collect_target_files(args.file):
            out_path = write_single_review(
                file_path,
                stamp=session_stamp,
                git_provenance=git_prov,
            )
            print(f"Generated inspect review: {out_path}")
        return

    if args.mode == "export":
        targets = _collect_target_files(args.file)
        shared_output_dir = args.out if len(targets) == 1 else None
        extract_config_id = resolve_installed_extract_config_id()
        for file_path in targets:
            sequence = run_document_processing_intake_launch_extract(
                project_root=PROJECT_ROOT,
                source_file=file_path,
                extract_config_id=extract_config_id,
                extract_output_dir=shared_output_dir,
                export_slices=args.export_slices,
                git_provenance=git_prov,
            )
            doc_result = sequence.extract_report.result.document
            print(f"Exported extract outputs: {doc_result.output_dir}")
            print(f"Session index: {sequence.extract_report.result.index_path}")
        return

    if args.mode == "validate":
        session_stamp = utc_run_stamp()
        report_path = run_extract_test_cases_report(
            resolve_existing_file(args.test_cases, flag_name="--test-cases"),
            verbose=args.verbose,
            stamp=session_stamp,
            git_provenance=git_prov,
        )
        print(f"Generated validate report: {report_path}")
        return


if __name__ == "__main__":
    main()
