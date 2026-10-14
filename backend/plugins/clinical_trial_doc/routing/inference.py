"""Heading-path route inference for clinical trial document routing."""

from __future__ import annotations

from dataclasses import dataclass

from artifacts.routing.types import Route

TABLE_TERMS: tuple[str, ...] = (
    "累计汇总表",
    "测量值列表",
    "异常实验室值",
    "汇总表",
    "行列表",
    "受试者列表",
    "试验参与者列表",
    "患者列表",
    "表",
    "列表",
)

CASE_TERMS: tuple[str, ...] = (
    "病例叙述",
    "个例叙述",
    "死亡受试者",
    "死亡试验参与者",
    "退出研究受试者",
    "退出研究试验参与者",
    "临床重要异常值",
    "个例",
    "病例",
    "叙述",
)

AGGREGATE_TERMS: tuple[str, ...] = (
    "各实验室参数的评价",
    "安全性相关观察",
    "严重不良反应",
    "严重不良事件",
    "安全性结果",
    "安全性分析",
    "安全性总结",
    "随时间变化",
    "不良事件",
    "不良反应",
    "生命体征",
    "体格检查",
    "发生率",
    "概述",
    "总结",
    "汇总",
    "评价",
    "评估",
    "分析",
    "死亡",
    "停药",
    "退出",
)

_TEXT_BLOCK_KINDS = frozenset({"paragraph", "list_item"})
_TABLE_STRUCTURE_KINDS = frozenset({"table", "table_caption", "table_note"})


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    route_basis: str
    route_matched_terms: tuple[str, ...]


def _heading_text(heading_path: tuple[str, ...]) -> str:
    # Use nearest heading context (leaf + parent) to reduce
    # false positives from distant ancestor headings.
    return " ".join(heading_path[-2:])


def _match_terms(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    matched = [term for term in terms if term in text]
    return tuple(matched)


def default_text_route_basis(*, zone_key: str | None = None) -> str:
    """Route basis for paragraph/list text with no heading-path term match."""
    if (zone_key or "").strip():
        return "selected_zone_default_text"
    return "heading_path_default_under_selected_zone"


def infer_route_from_heading(
    *,
    heading_path: tuple[str, ...],
    block_kind: str,
    zone_key: str | None = None,
) -> RouteDecision:
    """
    Infer preliminary tag_prepare route from structural block kind and heading path.

    Priority: table > case > aggregate > unknown/default.
    """
    kind = (block_kind or "paragraph").strip().lower()
    text = _heading_text(heading_path)

    if kind == "table":
        return RouteDecision(
            route="table",
            route_basis="block_kind",
            route_matched_terms=(),
        )

    if kind in ("table_caption", "table_note"):
        return RouteDecision(
            route="table",
            route_basis="block_kind",
            route_matched_terms=(kind,),
        )

    table_matched = _match_terms(text, TABLE_TERMS)
    if table_matched:
        return RouteDecision(
            route="table",
            route_basis="route_matched_terms",
            route_matched_terms=table_matched,
        )

    case_matched = _match_terms(text, CASE_TERMS)
    if case_matched:
        return RouteDecision(
            route="case",
            route_basis="route_matched_terms",
            route_matched_terms=case_matched,
        )

    aggregate_matched = _match_terms(text, AGGREGATE_TERMS)
    if aggregate_matched:
        return RouteDecision(
            route="aggregate",
            route_basis="route_matched_terms",
            route_matched_terms=aggregate_matched,
        )

    if kind in _TEXT_BLOCK_KINDS:
        return RouteDecision(
            route="aggregate",
            route_basis=default_text_route_basis(zone_key=zone_key),
            route_matched_terms=(),
        )

    if kind == "heading":
        return RouteDecision(
            route="unknown",
            route_basis="heading_context_only",
            route_matched_terms=(),
        )

    return RouteDecision(
        route="unknown",
        route_basis="no_route_match",
        route_matched_terms=(),
    )


def is_text_unit_assembly_kind(block_kind: str) -> bool:
    kind = (block_kind or "paragraph").strip().lower()
    return kind not in _TABLE_STRUCTURE_KINDS


def is_text_candidate_kind(block_kind: str) -> bool:
    kind = (block_kind or "paragraph").strip().lower()
    return kind in _TEXT_BLOCK_KINDS
