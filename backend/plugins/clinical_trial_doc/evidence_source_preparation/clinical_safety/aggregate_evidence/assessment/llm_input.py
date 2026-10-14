"""Plugin-owned LLM-input preparation for aggregate heading-scope assessment."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    build_scope_assessment_task_manifest,
    validate_compact_assessment_input_shape,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    heading_scope_signature,
)

_MODEL_SCOPE_ID_PATTERN = re.compile(r"^S\d{4}$")


@dataclass(frozen=True, slots=True)
class ScopeAssessmentLlmInput:
    """In-memory assess execution bundle; alias map is not persisted to artifacts."""

    prompt_input_bundle: dict[str, Any]
    alias_to_scope_id: dict[str, str]


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _ordered_unit_ids(scope: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _require_str(unit.get("unit_id"), field="heading_scopes.units.unit_id")
        for unit in (scope.get("units") or [])
        if isinstance(unit, dict)
    )


def _stable_scope_provenance_blocks(
    *,
    unit_ids: Sequence[str],
    unit_provenance: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    blocks: set[str] = set()
    for unit_id in unit_ids:
        provenance = unit_provenance.get(str(unit_id))
        if not isinstance(provenance, Mapping):
            continue
        for block_id in provenance.get("context_block_ids") or []:
            token = str(block_id or "").strip()
            if token:
                blocks.add(token)
    return tuple(sorted(blocks))


def scope_semantic_sort_key(
    scope: Mapping[str, Any],
    *,
    unit_provenance: Mapping[str, Mapping[str, Any]],
    zone_key: str,
) -> tuple[Any, ...]:
    """Semantic ordering key; must not depend on HS ids, TU ids, or artifact index."""
    heading_path = scope.get("heading_path")
    if not isinstance(heading_path, list):
        raise ValueError("heading_scopes.heading_path must be a list")

    evidence = scope.get("assessment_evidence")
    if not isinstance(evidence, Mapping):
        raise ValueError("heading_scopes.assessment_evidence must be an object")
    candidate_text = str(evidence.get("candidate_text") or "")

    unit_ids = _ordered_unit_ids(scope)
    if not unit_ids:
        raise ValueError("heading_scopes.units must be non-empty for semantic sort")

    first_provenance = unit_provenance.get(unit_ids[0])
    if not isinstance(first_provenance, Mapping):
        first_provenance = {}

    pseudo_unit = {
        "source_zone_key": str(first_provenance.get("source_zone_key") or zone_key or ""),
        "heading_path": [str(item) for item in heading_path],
        "context_block_ids": [
            str(block_id)
            for block_id in (first_provenance.get("context_block_ids") or [])
            if block_id
        ],
    }
    signature = heading_scope_signature(pseudo_unit)
    stable_blocks = _stable_scope_provenance_blocks(
        unit_ids=unit_ids,
        unit_provenance=unit_provenance,
    )
    return (signature, candidate_text, stable_blocks)


def _sort_hs_tasks_for_model_input(
    hs_tasks: Sequence[Mapping[str, Any]],
    *,
    assessment_input: Mapping[str, Any],
    assessment_runtime_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    scope_by_id: dict[str, Mapping[str, Any]] = {}
    for scope in assessment_input.get("heading_scopes") or []:
        if not isinstance(scope, Mapping):
            continue
        scope_id = str(scope.get("scope_id") or "").strip()
        if scope_id:
            scope_by_id[scope_id] = scope

    provenance_map = assessment_runtime_context.get("unit_provenance") or {}
    if not isinstance(provenance_map, Mapping):
        raise ValueError("assessment_runtime_context.unit_provenance must be an object")

    zone_key = str(assessment_input.get("zone_key") or "")
    sortable: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for task in hs_tasks:
        if not isinstance(task, Mapping):
            raise ValueError("scope assessment task manifest entries must be objects")
        scope_id = _require_str(task.get("scope_id"), field="scope_id")
        scope = scope_by_id.get(scope_id)
        if scope is None:
            raise ValueError(f"missing heading scope {scope_id!r} in assessment_input")
        key = scope_semantic_sort_key(
            scope,
            unit_provenance=provenance_map,
            zone_key=zone_key,
        )
        sortable.append((key, dict(task)))

    sortable.sort(key=lambda item: item[0])
    return [task for _key, task in sortable]


def _assign_model_local_scope_ids(
    sorted_tasks: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    model_tasks: list[dict[str, Any]] = []
    alias_to_scope_id: dict[str, str] = {}
    for index, task in enumerate(sorted_tasks, start=1):
        canonical_scope_id = _require_str(task.get("scope_id"), field="scope_id")
        model_scope_id = f"S{index:04d}"
        if not _MODEL_SCOPE_ID_PATTERN.fullmatch(model_scope_id):
            raise ValueError(f"invalid model-local scope_id {model_scope_id!r}")
        alias_to_scope_id[model_scope_id] = canonical_scope_id
        model_tasks.append(
            {
                "scope_id": model_scope_id,
                "heading_path": [str(item) for item in (task.get("heading_path") or [])],
                "candidate_text": str(task.get("candidate_text") or ""),
            }
        )
    return model_tasks, alias_to_scope_id


def build_scope_aware_prompt_input(
    assessment_input: Mapping[str, Any],
    assessment_runtime_context: Mapping[str, Any],
) -> ScopeAssessmentLlmInput:
    """Project compact assessment_input into model-visible prompt input."""
    validate_compact_assessment_input_shape(assessment_input)

    hs_tasks = build_scope_assessment_task_manifest(assessment_input)
    sorted_tasks = _sort_hs_tasks_for_model_input(
        hs_tasks,
        assessment_input=assessment_input,
        assessment_runtime_context=assessment_runtime_context,
    )
    model_heading_scopes, alias_to_scope_id = _assign_model_local_scope_ids(sorted_tasks)

    doc_meta = assessment_input.get("doc_meta") or {}
    if not isinstance(doc_meta, Mapping):
        raise ValueError("doc_meta must be an object")

    prompt_input: dict[str, Any] = {
        "llm_input_bundle_id": _require_str(
            assessment_input.get("llm_input_bundle_id"),
            field="llm_input_bundle_id",
        ),
        "doc_meta": {"study_drug": doc_meta.get("study_drug")},
        "instructions": str(assessment_input.get("instructions") or ""),
        "heading_scopes": model_heading_scopes,
    }
    for optional_key in ("assessment_profile_ref", "expected_schema"):
        if optional_key in assessment_input:
            prompt_input[optional_key] = assessment_input[optional_key]

    return ScopeAssessmentLlmInput(
        prompt_input_bundle=prompt_input,
        alias_to_scope_id=alias_to_scope_id,
    )
