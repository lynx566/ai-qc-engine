"""CLI adapter for standalone Aggregate Comparison evidence materialization."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[6]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize one or two ordered aggregate evidence source bundles "
            "as formal Aggregate Comparison evidence."
        )
    )
    parser.add_argument("--source", default=None)
    parser.add_argument("--source-a", default=None)
    parser.add_argument("--source-b", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--run-id", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.source_adapter import (
        adapt_clinical_safety_aggregate_source_bundle,
    )
    from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.materialization import (
        run_aggregate_comparison_materialization,
    )
    from scripts.stage_runners.common import ensure_project_on_path

    ensure_project_on_path()
    try:
        report = run_aggregate_comparison_materialization(
            project_root=PROJECT_ROOT,
            source_adapter=adapt_clinical_safety_aggregate_source_bundle,
            source=args.source,
            source_a=args.source_a,
            source_b=args.source_b,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    for message in report.messages:
        print(message)


if __name__ == "__main__":
    main()
