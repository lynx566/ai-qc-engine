"""Task-owned report of the persisted current state; no storage or renderer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from application.task_run import load_task_run
from application.clinical_trial_doc_consistency_qc.result_read import (
    load_document_consistency_qc_result,
)
from application.clinical_trial_doc_consistency_qc.content_domain_presentation import (
    content_domain_display_label,
)
from application.document_consistency_qc.candidate_scope_read import (
    load_final_candidate_scope_configuration,
)
from application.document_consistency_qc.configuration_scope_projection import (
    project_configuration_selection_scope_display,
)
from application.document_consistency_qc.canonical_source_read import (
    CanonicalAnnotationProjectionError,
    load_canonical_documents,
    load_canonical_source_annotations,
    project_canonical_sources,
)
from application.document_consistency_qc.document_read import (
    DocumentReadError,
    DocumentReadIdentityError,
    resolve_slot_extract_bundle,
)
from application.document_consistency_qc.finding_review import load_finding_review_state
from application.document_consistency_qc.report_context import load_report_flow_context
from artifacts.qc_report import build_qc_report, validate_qc_report
from runtime.run_layout import utc_now_iso
from task.clinical_trial_doc_qc.installation import INSTALLED_PRODUCT_TASK_BY_ID
from task.clinical_trial_doc_qc.presentation import (
    DOCUMENT_CONSISTENCY_QC_FUNCTION_DISPLAY,
    PRODUCT_TASK_PRESENTATION_BY_ID,
)
from task.clinical_trial_doc_qc.report_graph import anchor_key, compose_graph, local_ref
from task.clinical_trial_doc_qc.report_integrity import (
    aggregate_integrity,
    contribution_flow_execution_adjustments,
    result_domain_integrity,
)
from task.clinical_trial_doc_qc.task_input import (
    load_task_input_manifest,
    task_input_source_file_path,
)


class QcReportReadError(Exception):
    """Report identity or persisted input validation failed."""


class QcReportUnavailableError(QcReportReadError):
    """Core Result or source is unavailable; no report payload is fabricated."""


class QcReportConsistencyError(QcReportReadError):
    """Saved inputs changed during composition; caller may retry."""


@dataclass(frozen=True)
class _Inputs:
    project_root: Path
    task: Any
    task_input: Any
    flow: Any
    documents: Any
    result: Any
    configuration: Any
    sources: Any
    annotations: Any
    unusable_annotation_ids: tuple[str, ...]
    reviews: Any


def _read_inputs(*, project_root: Path, task_run_id: str) -> _Inputs:
    task = load_task_run(project_root=project_root, task_run_id=task_run_id)
    inputs = load_task_input_manifest(
        project_root=project_root, task_run_id=task_run_id
    )
    installation = INSTALLED_PRODUCT_TASK_BY_ID.get(task["task_id"])
    if installation is None or task["task_id"] not in PRODUCT_TASK_PRESENTATION_BY_ID:
        raise QcReportReadError("当前任务类型不支持报告读取。")
    if len(task["flow_runs"]) != 1:
        raise QcReportUnavailableError("报告需要一个明确关联的核查执行。")
    child = task["flow_runs"][0]
    if child["flow_id"] != installation.child_flow.flow_id:
        raise QcReportReadError("任务与核查执行的身份不一致。")
    flow_id = child["flow_run_id"]
    flow = load_report_flow_context(project_root=project_root, flow_run_id=flow_id)
    if (
        flow.flow_id != child["flow_id"]
        or flow.capability_id != installation.child_flow.capability_id
    ):
        raise QcReportReadError("任务与核查执行的类型不一致。")
    documents = load_canonical_documents(project_root=project_root, flow_run_id=flow_id)
    if (
        len(documents) != 1
        or len(installation.child_flow.input_bindings) != 1
        or len(inputs["inputs"]) != 1
    ):
        raise QcReportUnavailableError("当前报告仅支持单文档核查结果。")
    binding = installation.child_flow.input_bindings[0]
    document = documents[0]
    admitted = inputs["inputs"][0]
    if (
        document.flow_run_id != flow_id
        or document.slot_id != binding.participant_slot_id
        or admitted["task_slot_id"] != binding.task_slot_id
        or admitted["file_hash"] != document.file_hash
        or admitted["original_file_name"] != document.original_file_name
    ):
        raise QcReportReadError("任务输入与核查文档身份不一致。")
    expected_source = task_input_source_file_path(
        project_root=project_root,
        task_run_id=task_run_id,
        task_slot_id=binding.task_slot_id,
        original_file_name=admitted["original_file_name"],
    )
    if (project_root / admitted["source_ref"]).resolve() != expected_source.resolve():
        raise QcReportReadError("任务输入来源不属于当前任务。")
    result = load_document_consistency_qc_result(
        project_root=project_root, flow_run_id=flow_id
    )
    if (
        result.flow_run_id != flow_id
        or result.flow_id != flow.flow_id
        or result.capability_id != flow.capability_id
        or result.flow_status != flow.outcome
    ):
        raise QcReportReadError("结果与核查执行身份或状态不一致。")
    if len(flow.participants) != 1 or flow.participants[0][:2] != (
        document.slot_id,
        document.doc_id,
    ):
        raise QcReportReadError("结果参与文档与核查执行不一致。")
    module_id = flow.participants[0][2]
    if not module_id or any(
        scope.semantic_module_id != module_id for scope in result.scope_results
    ):
        raise QcReportReadError("无法确定结果的唯一内容领域归属。")
    if any(
        slot != document.slot_id or module != module_id
        for slot, module in flow.route_modules
    ):
        raise QcReportReadError("报告不支持存在歧义的内容领域归属。")
    for scope in result.scope_results:
        if (scope.slot_id, scope.doc_id) != (document.slot_id, document.doc_id):
            raise QcReportReadError("覆盖范围与核查文档不一致。")
    try:
        configuration = load_final_candidate_scope_configuration(
            project_root=project_root, flow_run_id=flow_id
        )
    except DocumentReadIdentityError:
        raise
    except DocumentReadError:
        configuration = None
    if configuration is not None and any(
        (row.flow_run_id, row.slot_id, row.doc_id)
        != (flow_id, document.slot_id, document.doc_id)
        for row in configuration
    ):
        raise QcReportReadError("最终配置与核查执行身份不一致。")
    anchors = {}
    for finding in result.findings:
        for anchor in finding.evidence_refs:
            anchors.setdefault(anchor_key(anchor), anchor)
    sources = project_canonical_sources(
        project_root=project_root, flow_run_id=flow_id, anchors=tuple(anchors.values())
    )
    unusable = ()
    try:
        annotations = load_canonical_source_annotations(
            project_root=project_root, flow_run_id=flow_id
        )
    except CanonicalAnnotationProjectionError as exc:
        if exc.flow_run_id != flow_id:
            raise QcReportReadError("审阅记录与核查执行身份不一致。") from exc
        annotations, unusable = exc.annotations, exc.unusable_annotation_ids
    for source in tuple(sources) + tuple(
        annotation.source for annotation in annotations
    ):
        if source.document != document:
            raise QcReportReadError("原文来源与核查文档不一致。")
    reviews = load_finding_review_state(project_root=project_root, flow_run_id=flow_id)
    if reviews.flow_run_id != flow_id:
        raise QcReportReadError("问题审阅状态与核查执行身份不一致。")
    return _Inputs(
        project_root,
        task,
        inputs,
        flow,
        documents,
        result,
        configuration,
        sources,
        annotations,
        unusable,
        reviews,
    )


def _compose(saved: _Inputs) -> dict:
    task, flow, result = saved.task, saved.flow, saved.result
    document = saved.documents[0]
    extract_bundle = resolve_slot_extract_bundle(
        project_root=saved.project_root,
        flow_run_id=flow.flow_run_id,
        slot_id=document.slot_id,
    )
    admitted = saved.task_input["inputs"][0]
    presentation = PRODUCT_TASK_PRESENTATION_BY_ID[task["task_id"]]
    contribution_ref = local_ref("contribution", flow.flow_id, flow.flow_run_id)
    document_ref = local_ref(
        "document",
        task["task_run_id"],
        admitted["task_slot_id"],
        document.doc_id,
        document.file_hash,
    )
    module_id = flow.participants[0][2]
    try:
        findings, evidence, annotations, independent, legacy_count = compose_graph(
            flow_run_id=flow.flow_run_id,
            contribution_ref=contribution_ref,
            document_ref=document_ref,
            module_id=module_id,
            result=result,
            sources=saved.sources,
            annotations=saved.annotations,
            reviews=saved.reviews,
        )
    except ValueError as exc:
        raise QcReportConsistencyError(
            "原文与审阅来源发生变化，请重试生成报告。"
        ) from exc
    config = {
        "availability": "unavailable",
        "persisted_decision_at": None,
        "selections": [],
    }
    limitations = []
    if saved.configuration:
        times = {row.persisted_decision_at for row in saved.configuration}
        if len(times) != 1:
            raise QcReportReadError("最终配置决定时间不一致。")
        config = {
            "availability": "available",
            "persisted_decision_at": next(iter(times)),
            "selections": [
                {
                    "document_ref": document_ref,
                    "slot_id": row.slot_id,
                    "filter_job_id": row.filter_job_id,
                    **{
                        key: list(getattr(row, key))
                        for key in (
                            "automatic_anchor_block_ids",
                            "effective_anchor_block_ids",
                            "added_anchor_block_ids",
                            "removed_anchor_block_ids",
                        )
                    },
                    **project_configuration_selection_scope_display(
                        extract_bundle,
                        automatic_anchor_block_ids=row.automatic_anchor_block_ids,
                        effective_anchor_block_ids=row.effective_anchor_block_ids,
                        added_anchor_block_ids=row.added_anchor_block_ids,
                        removed_anchor_block_ids=row.removed_anchor_block_ids,
                    ),
                }
                for row in saved.configuration
            ],
        }
    else:
        limitations.append("本次核查的最终章节配置不可用，报告仅包含已保存的结果。")
    if legacy_count:
        limitations.append("存在无法确定类型的历史审阅记录，未纳入报告中的批注。")
    if saved.unusable_annotation_ids:
        limitations.append(
            "部分已保存的审阅记录无法与当前原文对应，未纳入报告中的批注。"
        )
    domain_integrity = result_domain_integrity(result)
    forced, execution_limitations = contribution_flow_execution_adjustments(
        flow.outcome, domain_integrity, result
    )
    limitations.extend(execution_limitations)
    contribution_integrity = aggregate_integrity(
        domain_integrity, limitations=limitations, forced_status=forced
    )
    contribution_integrity.update(
        finalization_status=result.finalization_status,
        fallback_comparison_modes=list(result.fallback_comparison_modes),
    )
    outcome = "paused" if flow.outcome == "paused_at_candidate_scope" else flow.outcome
    expected_type = next(
        (
            slot.expected_document_type
            for slot in presentation.input_slots
            if slot.slot_id == admitted["task_slot_id"]
        ),
        None,
    )
    return build_qc_report(
        report_id=local_ref("report", task["task_run_id"]),
        generated_at=utc_now_iso(),
        task={
            **{
                key: task[key]
                for key in ("task_run_id", "task_id", "created_at", "updated_at")
            },
            "display_name": presentation.display_name,
        },
        documents=[
            {
                "document_ref": document_ref,
                "task_input": {"task_slot_id": admitted["task_slot_id"]},
                "participants": [
                    {"contribution_ref": contribution_ref, "slot_id": document.slot_id}
                ],
                "doc_id": document.doc_id,
                "original_file_name": document.original_file_name,
                "file_hash": document.file_hash,
                "expected_document_type": expected_type,
                "observed_document_type": None,
            }
        ],
        contributions=[
            {
                "contribution_ref": contribution_ref,
                "flow_id": flow.flow_id,
                "flow_run_id": flow.flow_run_id,
                "capability_id": flow.capability_id,
                "function_display": dict(DOCUMENT_CONSISTENCY_QC_FUNCTION_DISPLAY),
                "execution": {
                    "outcome": outcome,
                    "created_at": flow.created_at,
                    "completed_at": flow.completed_at,
                },
                "content_domains": [
                    {
                        "semantic_module_id": module_id,
                        "display_name": content_domain_display_label(module_id),
                        "finding_refs": [
                            finding["finding_ref"] for finding in findings
                        ],
                        "coverage": [
                            {
                                "document_ref": document_ref,
                                "slot_id": scope.slot_id,
                                "scope_id": scope.scope_id,
                                "heading_path": list(scope.heading_path),
                                "execution_status": scope.execution_status,
                            }
                            for scope in result.scope_results
                        ],
                        "integrity": domain_integrity,
                    }
                ],
                "configuration": config,
                "integrity": contribution_integrity,
            }
        ],
        findings=findings,
        source_evidence=evidence,
        source_annotations=annotations,
        independent_review_record_refs=independent,
        integrity=aggregate_integrity(contribution_integrity),
    )


def load_qc_report(*, project_root: Path, task_run_id: str) -> dict:
    """Read twice in a fixed order, rejecting changed saved inputs; no persistence.

    This is the saved current state at generation time, not transaction snapshot
    isolation or audit history. Identity failures never degrade into partial data.
    """
    try:
        saved = _read_inputs(project_root=project_root, task_run_id=task_run_id)
        verified = _read_inputs(project_root=project_root, task_run_id=task_run_id)
        if saved != verified:
            raise QcReportConsistencyError(
                "保存状态在读取期间发生变化，请重试生成报告。"
            )
        payload = _compose(saved)
        validate_qc_report(payload)
        return payload
    except QcReportReadError:
        raise
    except DocumentReadIdentityError as exc:
        raise QcReportReadError("保存记录与当前任务或核查文档的身份不一致。") from exc
    except Exception as exc:
        raise QcReportUnavailableError(
            "保存的核查结果或必要来源不可用，无法生成报告。"
        ) from exc


__all__ = [
    "load_qc_report",
    "QcReportReadError",
    "QcReportUnavailableError",
    "QcReportConsistencyError",
]
