"""Pure integrity composition; a complete result is not a pass verdict."""

from __future__ import annotations

from typing import Any, Mapping


def integrity(status="complete", limitations=(), **provenance):
    return {
        "status": status,
        "limitations": list(dict.fromkeys(limitations)),
        **provenance,
    }


def aggregate_integrity(*children, limitations=(), forced_status=None):
    rank = {"complete": 0, "partial": 1, "unavailable": 2, "failed": 3}
    statuses = [child["status"] for child in children]
    if limitations:
        statuses.append("partial")
    if forced_status:
        statuses.append(forced_status)
    status = max(statuses or ["complete"], key=rank.__getitem__)
    return integrity(
        status,
        [text for child in children for text in child["limitations"]]
        + list(limitations),
    )


def is_lossless_consolidation_fallback(result: Any) -> bool:
    """Product-final passthrough with consolidation fallback provenance."""

    return (
        result.finalization_status == "completed_with_fallback"
        and bool(result.fallback_comparison_modes)
    )


def result_domain_integrity(result: Any) -> Mapping[str, Any]:
    scopes = result.scope_results
    statuses = [scope.execution_status for scope in scopes]
    limitations: list[str] = []
    status = "complete"
    if not statuses:
        status = "unavailable"
        limitations.append("缺少核查覆盖信息，无法确认结果是否完整。")
    elif any(value != "complete" for value in statuses):
        status = "failed" if all(value == "failed" for value in statuses) else "partial"
        limitations.append("部分内容未完成核查，结果未覆盖全部计划范围。")
    comparison_run_status = result.comparison_run_status
    if comparison_run_status == "failed":
        if status == "complete":
            status = "failed"
        limitations.append("本次比较执行失败，现有问题记录仅代表已保存的结果。")
    elif comparison_run_status == "partial_failure":
        if not is_lossless_consolidation_fallback(result):
            if status == "complete":
                status = "partial"
            limitations.append(
                "本次核查执行未完整成功，现有问题记录仅代表已保存的结果。"
            )
    elif comparison_run_status not in {None, "success"}:
        if status == "complete":
            status = "partial"
        limitations.append("本次核查执行未完整成功，现有问题记录仅代表已保存的结果。")
    if result.fallback_comparison_modes:
        limitations.append("部分问题未完成自动合并，已保留全部未合并的问题记录。")
    return integrity(
        status,
        limitations,
        finalization_status=result.finalization_status,
        fallback_comparison_modes=list(result.fallback_comparison_modes),
    )


def contribution_flow_execution_adjustments(
    flow_outcome: str, domain_integrity: Mapping[str, Any], result: Any
) -> tuple[str | None, list[str]]:
    """Map persisted Flow outcome to contribution integrity; never rewrite execution."""

    if flow_outcome == "failed":
        return "failed", ["核查执行失败，报告仅代表已经保存的结果。"]
    return None, []
