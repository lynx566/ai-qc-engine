"""CLI adapter for the aggregate-evidence prepare runtime operation."""

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
    run_prepare_operation,
)
from scripts.stage_runners.common import ensure_project_on_path

_EXPLICIT_FILE_ARGS = (
    "coverage_bundle",
    "block_manifest",
    "doc_meta_bundle",
    "analysis_bundle",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare aggregate evidence heading-scope assessment input."
    )
    parser.add_argument("--routed-aggregate-bundle", required=True)
    parser.add_argument("--coverage-bundle", default=None)
    parser.add_argument("--block-manifest", default=None)
    parser.add_argument("--doc-meta-bundle", default=None)
    parser.add_argument("--analysis-bundle", default=None)
    parser.add_argument(
        "--filter-run-dir",
        action="append",
        dest="filter_run_dirs",
        default=None,
        metavar="DIR",
        help=(
            "Filter job output directory (repeatable for projected fan-in). "
            "Single value remains valid for single-source prepare."
        ),
    )
    parser.add_argument("--doc-meta-dir", default=None)
    parser.add_argument("--out", dest="output_dir", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--semantic-module-id",
        default=None,
        help="Installed aggregate semantic module (defaults when unambiguous).",
    )
    args = parser.parse_args(argv)
    _validate_input_mode(args)
    return args


def _validate_input_mode(args: argparse.Namespace) -> None:
    explicit = [getattr(args, name) for name in _EXPLICIT_FILE_ARGS]
    explicit_count = sum(value is not None for value in explicit)
    has_filter = bool(args.filter_run_dirs)
    has_doc_meta = args.doc_meta_dir is not None
    if explicit_count == len(_EXPLICIT_FILE_ARGS) and not has_filter and not has_doc_meta:
        return
    if has_filter and not explicit_count:
        return
    if explicit_count and (has_filter or has_doc_meta):
        raise SystemExit(
            "Aggregate Evidence prepare runner input modes are mutually exclusive: "
            "use either four explicit file flags or --filter-run-dir [--doc-meta-dir]."
        )
    if has_doc_meta and not has_filter:
        raise SystemExit("--doc-meta-dir requires --filter-run-dir")
    if explicit_count:
        raise SystemExit("explicit file mode requires all four input flags")
    raise SystemExit("provide explicit upstream files or --filter-run-dir")


def main(argv: list[str] | None = None) -> None:
    ensure_project_on_path()
    args = parse_args(argv)
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies(
        semantic_module_id=args.semantic_module_id,
    )
    try:
        report = run_prepare_operation(
            phase_dependencies=phase_dependencies,
            project_root=PROJECT_ROOT,
            routed_aggregate_bundle=args.routed_aggregate_bundle,
            coverage_bundle=args.coverage_bundle,
            block_manifest=args.block_manifest,
            doc_meta_bundle_path=args.doc_meta_bundle,
            analysis_bundle=args.analysis_bundle,
            filter_run_dirs=args.filter_run_dirs,
            doc_meta_dir=args.doc_meta_dir,
            semantic_module_id=phase_dependencies.semantic_module_id,
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
