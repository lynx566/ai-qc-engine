"""CLI adapter for Comparison Finding Verification input inspection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[6]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification_input_inspection import (
    run_comparison_finding_verification_input_inspection,
)
from scripts.stage_runners.common import ensure_project_on_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect Comparison Finding Verification user inputs materialized "
            "from a Comparison Finding Assessment execution run."
        )
    )
    parser.add_argument(
        "--assessment-run-dir",
        required=True,
        help=(
            "Path to a comparison_finding_assessment run directory containing "
            "run_summary.json and findings.json"
        ),
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    ensure_project_on_path()
    args = parse_args(argv)
    try:
        report = run_comparison_finding_verification_input_inspection(
            project_root=PROJECT_ROOT,
            assessment_run_dir=args.assessment_run_dir,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(str(exc)) from exc
    for message in report.messages:
        print(message)


if __name__ == "__main__":
    main()
