"""CLI adapter for the aggregate-evidence assessment runtime operation."""

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
from llm.provider_cli import register_llm_cli_arguments
from runtime.assessment_registry import (
    ASSESSMENT_LLM_CHOICES,
    ASSESSMENT_PROFILE_CHOICES,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.operations import (
    run_assess_operation,
)
from scripts.stage_runners.common import ensure_project_on_path
from scripts.stage_runners.evidence_source_preparation.aggregate_evidence.assess_runner_common import (
    resolve_llm_profile_args,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assess aggregate evidence heading scopes.")
    parser.add_argument("--assessment-input", required=True)
    parser.add_argument("--assessment-runtime-context", default=None)
    parser.add_argument(
        "--assessment-profile",
        dest="assessment_profile",
        default=None,
        help=f"Canonical choices: {', '.join(ASSESSMENT_PROFILE_CHOICES)}",
    )
    register_llm_cli_arguments(
        parser,
        llm_required=True,
        allowed_modes=ASSESSMENT_LLM_CHOICES,
    )
    parser.add_argument("--out", "--output-dir", dest="output_dir", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--no-llm-debug-artifacts", action="store_true")
    parser.add_argument("--allow-api-parse-fallback", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    resolve_llm_profile_args(args)
    return args


def main(argv: list[str] | None = None) -> None:
    ensure_project_on_path()
    args = parse_args(argv)
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies()
    try:
        report = run_assess_operation(
            phase_dependencies=phase_dependencies,
            project_root=PROJECT_ROOT,
            assessment_input=args.assessment_input,
            assessment_runtime_context=args.assessment_runtime_context,
            assessment_profile=args.assessment_profile,
            llm_mode=args.llm,
            llm_profile=args.llm_profile,
            thinking=args.thinking,
            output_dir=args.output_dir,
            output_root=args.output_root,
            run_id=args.run_id,
            no_llm_debug_artifacts=args.no_llm_debug_artifacts,
            allow_api_parse_fallback=args.allow_api_parse_fallback,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    except RuntimeError as exc:
        print(f"error: {exc}")
        raise SystemExit(1) from exc
    for message in report.messages:
        print(message)
    if report.result.run_status == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
