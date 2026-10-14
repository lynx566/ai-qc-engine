from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.clinical_trial_doc.prepare_analysis import (
    build_clinical_prepare_analysis_standalone_invocation,
)
from runtime.prepare_analysis import (
    PrepareAnalysisExecutionContext,
    run_prepare_analysis_operation,
)
from runtime.prepare_analysis.context import (
    PREPARE_ANALYSIS_LANGUAGE_CHOICES,
)

BUNDLE_FILENAME = "bundle.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare analysis_bundle from an Extract bundle.json."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--bundle", type=str, metavar="PATH")
    input_group.add_argument("--bundle-dir", type=str, metavar="DIR")
    parser.add_argument("--clinical-program", type=str, default=None, metavar="ID")
    parser.add_argument(
        "--language",
        choices=list(PREPARE_ANALYSIS_LANGUAGE_CHOICES),
        help="Document language (default: bundle document_meta.language)",
    )
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--privacy-detectors", metavar="LIST", default=None)
    parser.add_argument(
        "--privacy-after-extract-detectors", metavar="LIST", default=None
    )
    date_shift = parser.add_mutually_exclusive_group()
    date_shift.add_argument(
        "--date-shift",
        dest="date_shift_explicit",
        action="store_const",
        const=True,
    )
    date_shift.add_argument(
        "--no-date-shift",
        dest="date_shift_explicit",
        action="store_const",
        const=False,
    )
    parser.set_defaults(date_shift_explicit=None)
    args = parser.parse_args()

    from privacy.config import resolve_after_extract_cli

    try:
        args.privacy_after_extract_detectors = resolve_after_extract_cli(
            privacy_detectors=args.privacy_detectors,
            privacy_after_extract_detectors=args.privacy_after_extract_detectors,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main() -> None:
    args = parse_args()
    execution = PrepareAnalysisExecutionContext(
        project_root=PROJECT_ROOT,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    try:
        invocation = build_clinical_prepare_analysis_standalone_invocation(
            clinical_program_id=args.clinical_program,
            language=args.language,
            bundle_path=args.bundle,
            bundle_dir=args.bundle_dir,
            privacy_after_extract_detectors=args.privacy_after_extract_detectors,
            date_shift_explicit=args.date_shift_explicit,
        )
        report = run_prepare_analysis_operation(
            execution=execution,
            prepare_analysis_config_id=invocation.prepare_analysis_config_id,
            config_registry=invocation.config_registry,
            request_options=invocation.request_options,
            bundle_path=args.bundle,
            bundle_dir=args.bundle_dir,
            runtime_context_label=invocation.runtime_context_label,
        )
    except (ValueError, RuntimeError, TypeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    for message in report.messages:
        print(message)


if __name__ == "__main__":
    main()
