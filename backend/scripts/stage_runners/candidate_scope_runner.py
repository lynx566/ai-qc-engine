from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.candidate_scope_stage import (
    CandidateScopeStageInvocation,
    run_candidate_scope_stage,
)
from runtime.io import load_json
from runtime.run_ids import utc_run_stamp
from runtime.run_layout import allocate_session_dir
from scripts.stage_runners.common import ensure_project_on_path, resolve_artifact_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply heading-level candidate scope overrides to automatic Filter output "
            "and persist effective zone_match + coverage bundles."
        )
    )
    parser.add_argument(
        "--zone-match-bundle",
        required=True,
        help="Path to immutable automatic zone_match_bundle.json from Filter.",
    )
    parser.add_argument(
        "--analysis-bundle",
        required=True,
        help="Path to prepare_analysis analysis_bundle.json.",
    )
    parser.add_argument(
        "--override",
        required=True,
        help="Path to candidate_scope_override.json or inline JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory override (new run directory by default).",
    )
    return parser.parse_args()


def main() -> int:
    ensure_project_on_path()
    args = parse_args()

    zone_match_path = resolve_artifact_file(args.zone_match_bundle)
    analysis_path = resolve_artifact_file(args.analysis_bundle)
    override_path = resolve_artifact_file(args.override)
    override_payload = load_json(override_path)

    stamp = utc_run_stamp()
    runs_root = PROJECT_ROOT / "runs"
    session_dir = allocate_session_dir(
        runs_root,
        stage="candidate_scope",
        context=str(override_payload.get("doc_id") or "unknown"),
        stamp=stamp,
    )

    invocation = CandidateScopeStageInvocation(
        stamp=stamp,
        session_dir=session_dir,
        runs_root=runs_root,
        git_root=PROJECT_ROOT.parent,
        custom_output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
    )

    result = run_candidate_scope_stage(
        automatic_zone_match_bundle_path=zone_match_path,
        analysis_bundle_path=analysis_path,
        candidate_scope_override=override_payload,
        invocation=invocation,
        paths_base=PROJECT_ROOT,
    )

    print(json.dumps({"run_id": result.run_id, "output_dir": str(result.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
