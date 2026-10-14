"""Human-readable preview projection for Aggregate Evidence assessment input."""

from __future__ import annotations

from typing import Any

from artifacts.routing.primary_sentence_contract import routed_body_text_from_sentences
from artifacts.routing import ROUTES

_PREVIEW_TEXT_CHARS = 200


def _table_body_preview(unit: dict[str, Any], *, text_preview_chars: int) -> str:
    for component in unit.get("components") or []:
        if not isinstance(component, dict):
            continue
        if component.get("component_role") != "table_body":
            continue
        text = str(component.get("text") or "")
        preview = text[:text_preview_chars]
        if len(text) > text_preview_chars:
            preview += "…"
        return preview
    return ""


def _caption_preview(unit: dict[str, Any], *, text_preview_chars: int) -> str:
    for component in unit.get("components") or []:
        if not isinstance(component, dict):
            continue
        if component.get("component_role") != "caption":
            continue
        text = str(component.get("text") or "")
        preview = text[:text_preview_chars]
        if len(text) > text_preview_chars:
            preview += "…"
        return preview
    return ""


def _preview_text_for_unit(unit: dict[str, Any], *, text_preview_chars: int) -> str:
    sentences = unit.get("sentences") or []
    if isinstance(sentences, list) and sentences:
        text = routed_body_text_from_sentences(
            sentences,
            source_stage=str(unit.get("source_stage") or "") or None,
        )
    else:
        text = str(unit.get("candidate_text") or "")
    preview = text[:text_preview_chars]
    if len(text) > text_preview_chars:
        preview += "…"
    return preview


def _preview_entry(
    unit: dict[str, Any],
    *,
    text_preview_chars: int,
) -> dict[str, Any]:
    if unit.get("unit_kind") == "table_unit":
        components = unit.get("components") or []
        entry: dict[str, Any] = {
            "unit_id": unit.get("unit_id"),
            "route": unit.get("route"),
            "heading_path": list(unit.get("heading_path") or []),
            "source_table_ids": list(unit.get("source_table_ids") or []),
            "component_roles": [
                str(component.get("component_role") or "")
                for component in components
                if isinstance(component, dict) and component.get("component_role")
            ],
            "component_status": dict(unit.get("component_status") or {}),
            "caption_preview": _caption_preview(unit, text_preview_chars=text_preview_chars),
            "text_preview": _table_body_preview(unit, text_preview_chars=text_preview_chars),
        }
        return entry

    entry = {
        "unit_id": unit.get("unit_id"),
        "unit_kind": unit.get("unit_kind"),
        "route": unit.get("route"),
        "route_basis": unit.get("route_basis"),
        "route_matched_terms": list(unit.get("route_matched_terms") or []),
        "heading_path": list(unit.get("heading_path") or []),
        "source_block_ids": list(unit.get("source_block_ids") or []),
        "context_block_ids": list(unit.get("context_block_ids") or []),
        "text_preview": _preview_text_for_unit(unit, text_preview_chars=text_preview_chars),
    }
    sentences = unit.get("sentences") or []
    if isinstance(sentences, list):
        entry["sentence_count"] = len(sentences)
    else:
        entry["sentence_count"] = 0
    entry["context_block_count"] = len(unit.get("context_block_ids") or [])
    return entry


def build_llm_input_preview(
    llm_input_preview_source: dict[str, Any],
    *,
    text_preview_chars: int = _PREVIEW_TEXT_CHARS,
) -> dict[str, Any]:
    """Human-readable preview grouped by route; table bodies are truncated."""
    route_inputs = llm_input_preview_source.get("route_inputs") or {}
    route_counts = dict(llm_input_preview_source.get("route_counts") or {})
    route_previews: dict[str, list[dict[str, Any]]] = {}
    for route in ROUTES:
        route_bundle = route_inputs.get(route) or {}
        route_previews[route] = [
            _preview_entry(unit, text_preview_chars=text_preview_chars)
            for unit in route_bundle.get("units") or []
            if isinstance(unit, dict)
        ]

    return {
        "doc_id": llm_input_preview_source.get("doc_id"),
        "zone_key": llm_input_preview_source.get("zone_key"),
        "route_counts": route_counts,
        "route_previews": route_previews,
    }
