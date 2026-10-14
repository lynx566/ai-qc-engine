"""CLI adapter for Comparison Finding Verification LLM execution."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[6]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.provider_cli import (
    register_llm_cli_arguments,
    validate_configured_llm_cli_args,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    DEFAULT_LLM_SEED,
    run_comparison_finding_verification_execution,
)
from scripts.stage_runners.common import ensure_project_on_path
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification_mock_provider import (
    ComparisonFindingVerificationStandaloneMockProvider,
)

_STANDALONE_LLM_MODES = ("mock", "api")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute Comparison Finding Verification jobs from a completed "
            "Assessment execution run using promoted prompts and the existing LLM provider."
        )
    )
    parser.add_argument(
        "--assessment-run-dir",
        required=True,
        help=(
            "Path to a comparison_finding_assessment execution run directory "
            "containing run_summary.json and findings.json"
        ),
    )
    register_llm_cli_arguments(
        parser,
        llm_required=True,
        allowed_modes=_STANDALONE_LLM_MODES,
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_LLM_SEED,
        help="Provider seed for API execution (default: 1234).",
    )
    parser.add_argument(
        "--max-concurrency",
        type=_positive_int,
        default=None,
        help=(
            "Maximum concurrently executing jobs; omitted runs all verification "
            "jobs concurrently."
        ),
    )
    args = parser.parse_args(argv)
    validate_configured_llm_cli_args(args)
    return args


def main(argv: list[str] | None = None) -> None:
    ensure_project_on_path()
    args = parse_args(argv)
    provider = (
        ComparisonFindingVerificationStandaloneMockProvider()
        if args.llm == "mock"
        else None
    )
    try:
        report = run_comparison_finding_verification_execution(
            project_root=PROJECT_ROOT,
            assessment_run_dir=args.assessment_run_dir,
            llm_mode=args.llm,
            llm_profile=args.llm_profile,
            thinking=args.thinking,
            seed=args.seed,
            output_dir=args.output_dir,
            run_id=args.run_id,
            max_concurrency=args.max_concurrency,
            provider=provider,
        )
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc
    for message in report.messages:
        print(message)


if __name__ == "__main__":
    main()
