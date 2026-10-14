"""CLI adapter for Comparison Finding Assessment plan inspection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[6]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_plan import (
    run_comparison_finding_assessment_plan_inspection,
)
from scripts.stage_runners.common import ensure_project_on_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect Comparison Finding Assessment jobs planned from formal "
            "aggregate comparison evidence and an installed capability config."
        )
    )
    parser.add_argument(
        "--evidence",
        required=True,
        help="Path to aggregate_comparison_evidence.json",
    )
    parser.add_argument(
        "--capability",
        required=True,
        help=(
            "Installed capability id used only to resolve assessment config "
            "(internal_csr, internal_dsur, internal_ib, dsur_updated_ib)"
        ),
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    ensure_project_on_path()
    args = parse_args(argv)
    try:
        report = run_comparison_finding_assessment_plan_inspection(
            project_root=PROJECT_ROOT,
            evidence=args.evidence,
            capability_id=args.capability,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc
    for message in report.messages:
        print(message)


if __name__ == "__main__":
    main()
