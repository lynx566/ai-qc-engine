"""CLI adapter for the aggregate-evidence eligibility runtime operation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_phase_harness_installation import (
    resolve_installed_aggregate_evidence_phase_harness_dependencies,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.operations import (
    run_eligibility_operation,
)
from scripts.stage_runners.common import ensure_project_on_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate aggregate heading-scope eligibility."
    )
    parser.add_argument("--assessments", required=True)
    parser.add_argument("--out", "--output-dir", dest="output_dir", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--semantic-module-id",
        default=None,
        help="Installed aggregate semantic module (defaults when unambiguous).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    ensure_project_on_path()
    args = parse_args(argv)
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies(
        semantic_module_id=args.semantic_module_id,
    )
    try:
        report = run_eligibility_operation(
            phase_dependencies=phase_dependencies,
            project_root=PROJECT_ROOT,
            assessments=args.assessments,
            output_dir=args.output_dir,
            output_root=args.output_root,
            run_id=args.run_id,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    for message in report.messages:
        print(message)


if __name__ == "__main__":
    main()
