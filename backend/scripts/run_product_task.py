"""Developer CLI for persisted Product Task journeys."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(DEFAULT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_PROJECT_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc import (
    load_document_consistency_qc_result,
    resume_installed_clinical_trial_document_consistency_qc,
)
from application.document_consistency_qc.resume_request import (
    DocumentConsistencyQcResumeRequest,
)
from execution_flow.document_consistency_qc.candidate_scope_checkpoint import (
    automatic_candidate_scope_selections,
)
from execution_flow.document_consistency_qc.flow_loader import (
    load_flow_run_execution,
    resolve_paused_candidate_scope_slots,
)
from task.clinical_trial_doc_qc.definitions import PRODUCT_TASK_DEFINITION_BY_ID
from task.clinical_trial_doc_qc.start import (
    plan_installed_product_task_start,
    start_installed_product_task,
)
from task.clinical_trial_doc_qc.task_run_read import (
    TaskRunFlowRefRecord,
    TaskRunPageContext,
    load_task_run_page_context,
)


def _regular_file(value: str, *, option: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file():
        raise SystemExit(f"{option} must reference an existing regular file: {path}")
    return path


def _build_start_inputs(
    args: argparse.Namespace,
) -> tuple[dict[str, Path], dict[str, Path | None]]:
    slot_ids = tuple(
        slot.slot_id for slot in PRODUCT_TASK_DEFINITION_BY_ID[args.task].input_slots
    )
    if slot_ids == ("source",):
        if args.source_a or args.source_b or args.privacy_config_a or args.privacy_config_b:
            raise SystemExit(
                "single-document Product Tasks accept only --source and --privacy-config"
            )
        if not args.source:
            raise SystemExit("single-document Product Tasks require --source")
        source = _regular_file(args.source, option="--source")
        privacy = (
            _regular_file(args.privacy_config, option="--privacy-config")
            if args.privacy_config
            else None
        )
        return {"source": source}, {"source": privacy}

    if slot_ids == ("source_a", "source_b"):
        if args.source or args.privacy_config:
            raise SystemExit(
                "dsur_updated_ib_qc accepts only --source-a/--source-b and "
                "their suffixed privacy options"
            )
        if not args.source_a or not args.source_b:
            raise SystemExit("dsur_updated_ib_qc requires --source-a and --source-b")
        if bool(args.privacy_config_a) != bool(args.privacy_config_b):
            raise SystemExit(
                "provide both --privacy-config-a and --privacy-config-b, or neither"
            )
        sources = {
            "source_a": _regular_file(args.source_a, option="--source-a"),
            "source_b": _regular_file(args.source_b, option="--source-b"),
        }
        privacy_paths = {
            "source_a": (
                _regular_file(args.privacy_config_a, option="--privacy-config-a")
                if args.privacy_config_a
                else None
            ),
            "source_b": (
                _regular_file(args.privacy_config_b, option="--privacy-config-b")
                if args.privacy_config_b
                else None
            ),
        }
        return sources, privacy_paths

    raise SystemExit(f"unsupported Product Task input topology: {slot_ids!r}")


def _project_root(args: argparse.Namespace) -> Path:
    return Path(args.project_root).resolve() if args.project_root else DEFAULT_PROJECT_ROOT


def _require_product_child(context: TaskRunPageContext) -> TaskRunFlowRefRecord:
    if len(context.flow_runs) != 1:
        raise SystemExit(
            f"TaskRun must own exactly one child Flow, found {len(context.flow_runs)}"
        )
    child = context.flow_runs[0]
    if child.flow_id != "document_consistency_qc":
        raise SystemExit(f"TaskRun child has unsupported flow_id: {child.flow_id}")
    return child


def _state_output(
    *,
    context: TaskRunPageContext,
    flow_run_summary_path: Path,
) -> dict[str, Any]:
    child = _require_product_child(context)
    return {
        "task_run_id": context.task_run_id,
        "task_id": context.task_id,
        "flow_run_id": child.flow_run_id,
        "product_phase": context.state.product_phase,
        "flow_outcome": context.state.flow_outcome,
        "requires_user_action": context.state.requires_user_action,
        "result_available": context.state.result_available,
        "flow_run_summary_path": flow_run_summary_path.resolve().as_posix(),
        "result_loaded": False,
    }


def _start_product_task(args: argparse.Namespace) -> dict[str, Any]:
    project_root = _project_root(args)
    slot_inputs, privacy_paths = _build_start_inputs(args)
    composition = build_installed_document_consistency_qc_application_composition()
    planned = plan_installed_product_task_start(
        composition=composition,
        task_id=args.task,
        upload_slot_ids=slot_inputs,
    )
    started = start_installed_product_task(
        composition=composition,
        planned=planned,
        slot_inputs=slot_inputs,
        source_language=args.source_language,
        participant_privacy_paths=privacy_paths,
        project_root=project_root,
    )
    context = load_task_run_page_context(
        project_root=project_root,
        task_run_id=started.task_run_id,
    )
    return _state_output(
        context=context,
        flow_run_summary_path=started.child_flow.flow_run_summary_path,
    )


def _load_result_summary(
    payload: dict[str, Any],
    *,
    project_root: Path,
    flow_run_id: str,
    requested: bool,
) -> None:
    if not requested or not payload["result_available"]:
        return
    result = load_document_consistency_qc_result(
        project_root=project_root,
        flow_run_id=flow_run_id,
    )
    payload["result_loaded"] = True
    payload["finding_count"] = len(result.findings)


def _resume_product_task(
    *,
    project_root: Path,
    task_run_id: str,
    load_result: bool,
) -> dict[str, Any]:
    before = load_task_run_page_context(
        project_root=project_root,
        task_run_id=task_run_id,
    )
    child = _require_product_child(before)
    execution = load_flow_run_execution(
        project_root=project_root,
        flow_run_id=child.flow_run_id,
    )
    paused_slots = resolve_paused_candidate_scope_slots(execution)
    decisions_by_slot = {
        slot.slot_id: automatic_candidate_scope_selections(
            filter_job_ids=tuple(slot.filter_job_ids),
            filter_jobs=tuple(slot.filter_jobs),
        )
        for slot in paused_slots
    }
    composition = build_installed_document_consistency_qc_application_composition()
    resumed = resume_installed_clinical_trial_document_consistency_qc(
        composition=composition,
        request=DocumentConsistencyQcResumeRequest(
            flow_run_id=child.flow_run_id,
            candidate_scope_decisions_by_slot=decisions_by_slot,
            project_root=project_root,
            participant_privacy_paths={
                slot.slot_id: None for slot in execution.slot_provenance
            },
        ),
    )
    after = load_task_run_page_context(
        project_root=project_root,
        task_run_id=task_run_id,
    )
    payload = _state_output(
        context=after,
        flow_run_summary_path=resumed.flow_report.flow_run_summary_path,
    )
    _load_result_summary(
        payload,
        project_root=project_root,
        flow_run_id=child.flow_run_id,
        requested=load_result,
    )
    return payload


def _emit(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _add_output_arguments(
    parser: argparse.ArgumentParser,
    *,
    load_result_default: bool,
) -> None:
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument(
        "--load-result",
        action=argparse.BooleanOptionalAction,
        default=load_result_default,
    )


def _add_start_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task", choices=sorted(PRODUCT_TASK_DEFINITION_BY_ID), required=True)
    parser.add_argument("--source")
    parser.add_argument("--source-a")
    parser.add_argument("--source-b")
    parser.add_argument("--source-language", choices=("zh",), default="zh")
    parser.add_argument("--privacy-config")
    parser.add_argument("--privacy-config-a")
    parser.add_argument("--privacy-config-b")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run persisted Product Task journeys from local source files.",
        allow_abbrev=False,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start", allow_abbrev=False)
    _add_start_arguments(start)
    _add_output_arguments(start, load_result_default=False)

    resume = commands.add_parser("resume", allow_abbrev=False)
    resume.add_argument("--task-run-id", required=True)
    resume.add_argument("--candidate-scope", choices=("unchanged",), required=True)
    _add_output_arguments(resume, load_result_default=False)

    run = commands.add_parser("run", allow_abbrev=False)
    _add_start_arguments(run)
    _add_output_arguments(run, load_result_default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.command == "start":
        payload = _start_product_task(args)
        _load_result_summary(
            payload,
            project_root=_project_root(args),
            flow_run_id=payload["flow_run_id"],
            requested=args.load_result,
        )
    elif args.command == "resume":
        payload = _resume_product_task(
            project_root=_project_root(args),
            task_run_id=args.task_run_id,
            load_result=args.load_result,
        )
    elif args.command == "run":
        started = _start_product_task(args)
        if (
            started["flow_outcome"] != "paused_at_candidate_scope"
            or started["requires_user_action"] is not True
        ):
            raise SystemExit(
                "Product Start did not persist the expected Candidate Scope pause"
            )
        payload = _resume_product_task(
            project_root=_project_root(args),
            task_run_id=str(started["task_run_id"]),
            load_result=args.load_result,
        )
    else:
        raise SystemExit(f"command is not implemented yet: {args.command}")
    _emit(payload, json_output=args.json_output)


if __name__ == "__main__":
    main()
