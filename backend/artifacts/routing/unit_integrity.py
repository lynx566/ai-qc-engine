"""Neutral routed-unit structural integrity validation."""

from __future__ import annotations

from typing import Any

from artifacts.taggable_units import validate_aggregate_text_unit_contract


def _is_text_candidate_kind(block_kind: str) -> bool:
    kind = (block_kind or "paragraph").strip().lower()
    return kind in {"paragraph", "list_item"}


def _manifest_block_kind(block: dict[str, Any]) -> str:
    return str(block.get("kind") or block.get("block_kind") or "paragraph").strip().lower()


def _index_manifest_blocks(
    block_manifest: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(block_manifest, dict):
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for group_key in ("blocks", "table_blocks"):
        for block in block_manifest.get(group_key) or []:
            if not isinstance(block, dict):
                continue
            block_id = str(block.get("block_id") or "").strip()
            if block_id:
                indexed[block_id] = block
    return indexed


def _manifest_analysis_text(block: dict[str, Any]) -> str:
    analysis_text = str(block.get("analysis_text") or "").strip()
    if analysis_text:
        return analysis_text
    if _manifest_block_kind(block) == "table":
        return str(block.get("text") or "").strip()
    return ""


def source_block_ids_list(unit: dict[str, Any]) -> list[str]:
    return [str(block_id) for block_id in (unit.get("source_block_ids") or []) if block_id]


def validate_routed_unit_structural_integrity(
    *,
    units: list[dict[str, Any]],
    block_manifest: dict[str, Any] | None = None,
    check_duplicate_aggregate_unit_ids: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Validate neutral unit / sentence / block / manifest structural consistency."""
    manifest_blocks = _index_manifest_blocks(block_manifest)
    issues: list[dict[str, Any]] = []

    empty_primary_body_unit_count = 0
    source_block_without_primary_sentence_count = 0
    manifest_missing_block_count = 0
    manifest_empty_analysis_text_count = 0
    duplicate_aggregate_unit_id_count = 0
    empty_aggregate_unit_id_count = 0
    aggregate_unit_count = 0
    aggregate_contract_violation_count = 0
    aggregate_provenance_violation_count = 0
    unit_source_block_count = 0

    seen_aggregate_unit_ids: dict[str, int] = {}
    for unit in units:
        unit_kind = str(unit.get("unit_kind") or "text_unit")
        route = str(unit.get("route") or "")
        if unit_kind != "text_unit" or route != "aggregate":
            continue
        unit_id = str(unit.get("unit_id") or "").strip()
        if not unit_id:
            empty_aggregate_unit_id_count += 1
            issues.append(
                {
                    "code": "aggregate_unit_missing_unit_id",
                    "severity": "error",
                }
            )
            continue
        seen_aggregate_unit_ids[unit_id] = seen_aggregate_unit_ids.get(unit_id, 0) + 1

    if check_duplicate_aggregate_unit_ids:
        for unit_id, count in sorted(seen_aggregate_unit_ids.items()):
            if count <= 1:
                continue
            duplicate_aggregate_unit_id_count += 1
            issues.append(
                {
                    "code": "aggregate_unit_duplicate_unit_id",
                    "severity": "error",
                    "unit_id": unit_id,
                    "duplicate_count": count,
                }
            )

    for unit in units:
        unit_kind = str(unit.get("unit_kind") or "text_unit")
        unit_id = str(unit.get("unit_id") or "")
        if unit_kind == "table_unit":
            continue

        primary_sentences = [
            sentence
            for sentence in (unit.get("sentences") or [])
            if isinstance(sentence, dict)
        ]
        if primary_sentences:
            from artifacts.routing.primary_sentence_contract import (
                routed_body_text_from_sentences,
            )

            body_text = routed_body_text_from_sentences(
                primary_sentences,
                source_stage=str(unit.get("source_stage") or "") or None,
            )
            if not body_text.strip():
                empty_primary_body_unit_count += 1
                issues.append(
                    {
                        "code": "empty_primary_body_unit",
                        "severity": "error",
                        "unit_id": unit_id,
                    }
                )
        else:
            empty_primary_body_unit_count += 1
            issues.append(
                {
                    "code": "empty_primary_body_unit",
                    "severity": "error",
                    "unit_id": unit_id,
                }
            )

        source_block_ids = [
            str(block_id)
            for block_id in (unit.get("source_block_ids") or [])
            if block_id
        ]
        unit_source_block_count += len(source_block_ids)

        primary_sentences = [
            sentence
            for sentence in (unit.get("sentences") or [])
            if isinstance(sentence, dict)
        ]
        sentence_block_ids = {
            str(sentence.get("source_block_id") or "")
            for sentence in primary_sentences
            if sentence.get("source_block_id")
        }
        for block_id in source_block_ids:
            if block_id not in sentence_block_ids:
                source_block_without_primary_sentence_count += 1
                issues.append(
                    {
                        "code": "unit_source_block_without_primary_sentence",
                        "severity": "error",
                        "unit_id": unit_id,
                        "block_id": block_id,
                    }
                )

        if primary_sentences:
            expected_ids = [
                str(sentence.get("sentence_id") or "") for sentence in primary_sentences
            ]
            if not expected_ids or any(not token for token in expected_ids):
                issues.append(
                    {
                        "code": "unit_sentence_id_mismatch",
                        "severity": "error",
                        "unit_id": unit_id,
                    }
                )

        if not manifest_blocks:
            continue
        for block_id in source_block_ids:
            manifest_block = manifest_blocks.get(block_id)
            if manifest_block is None:
                manifest_missing_block_count += 1
                issues.append(
                    {
                        "code": "manifest_block_missing",
                        "severity": "error",
                        "unit_id": unit_id,
                        "block_id": block_id,
                    }
                )
                continue
            block_kind = _manifest_block_kind(manifest_block)
            if not _is_text_candidate_kind(block_kind):
                continue
            if not _manifest_analysis_text(manifest_block):
                manifest_empty_analysis_text_count += 1
                issues.append(
                    {
                        "code": "manifest_block_empty_analysis_text",
                        "severity": "error",
                        "unit_id": unit_id,
                        "block_id": block_id,
                    }
                )

    for unit in units:
        unit_kind = str(unit.get("unit_kind") or "text_unit")
        route = str(unit.get("route") or "")
        if unit_kind != "text_unit" or route != "aggregate":
            continue
        aggregate_unit_count += 1
        unit_id = str(unit.get("unit_id") or "")
        contract_issues = validate_aggregate_text_unit_contract(
            unit,
            unit_id=unit_id,
            source_label=f"unit:{unit_id or '<unknown>'}",
        )
        for issue in contract_issues:
            if issue.get("code") == "aggregate_unit_contract_violation":
                aggregate_contract_violation_count += 1
            else:
                aggregate_provenance_violation_count += 1
            issues.append(issue)

    return issues, {
        "unit_source_block_count": unit_source_block_count,
        "empty_primary_body_unit_count": empty_primary_body_unit_count,
        "source_block_without_primary_sentence_count": source_block_without_primary_sentence_count,
        "manifest_missing_block_count": manifest_missing_block_count,
        "manifest_empty_analysis_text_count": manifest_empty_analysis_text_count,
        "aggregate_unit_count": aggregate_unit_count,
        "aggregate_contract_violation_count": aggregate_contract_violation_count,
        "aggregate_provenance_violation_count": aggregate_provenance_violation_count,
        "empty_aggregate_unit_id_count": empty_aggregate_unit_id_count,
        "duplicate_aggregate_unit_id_count": duplicate_aggregate_unit_id_count,
    }
