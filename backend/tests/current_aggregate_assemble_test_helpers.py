"""Small current-contract inputs for aggregate-evidence assemble tests."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    build_assessment_runtime_context_envelope,
    build_assessment_runtime_context_id,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    build_heading_scope_eligibility_envelope,
    build_in_memory_source_scope_assessments_ref,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    ASSESSMENT_INPUT_SCHEMA_VERSION,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    build_scope_assessments_envelope,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.heading_scope_eligibility_policy import (
    build_heading_scope_eligibility_entries,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    attach_assessment_evidence_to_heading_scopes,
    build_heading_scopes_from_aggregate_units,
    build_unit_provenance_map,
)

_ASSESSMENT_PROFILE = "clinical_safety_aggregate_heading_scope_assessment_zh"


def _current_unit(
    *,
    unit_id: str,
    heading: str,
    context_block_id: str,
    source_block_id: str,
    sentence_texts: Sequence[str],
) -> dict[str, Any]:
    sentences = [
        {
            "sentence_id": f"{unit_id}_S{index:02d}",
            "text": text,
            "source_block_id": source_block_id,
        }
        for index, text in enumerate(sentence_texts, start=1)
    ]
    return {
        "unit_id": unit_id,
        "unit_kind": "text_unit",
        "route": "aggregate",
        "route_basis": "clinical_safety_default_text",
        "heading_path": [heading],
        "sentences": sentences,
        "source_block_ids": [source_block_id],
        "context_block_ids": [context_block_id],
        "all_source_block_ids": [context_block_id, source_block_id],
        "candidate_block_kinds": ["paragraph"],
        "text_refs": [{"block_id": source_block_id}],
        "source_stage": "filter",
        "source_zone_key": "ib_clinical_safety_zh",
        "route_matched_terms": ["safety"],
        "source_component_ids": [],
        "overview_decompose_bundle_id": None,
    }


def _default_units() -> list[dict[str, Any]]:
    return [
        _current_unit(
            unit_id="TU0001",
            heading="Safety findings",
            context_block_id="C0100",
            source_block_id="C0101",
            sentence_texts=("First safety sentence.", "Second safety sentence."),
        ),
        _current_unit(
            unit_id="TU0002",
            heading="Safety findings",
            context_block_id="C0100",
            source_block_id="C0102",
            sentence_texts=("Follow-up safety sentence.",),
        ),
        _current_unit(
            unit_id="TU0003",
            heading="Administrative context",
            context_block_id="C0200",
            source_block_id="C0201",
            sentence_texts=("Administrative text.",),
        ),
        _current_unit(
            unit_id="TU0004",
            heading="Additional safety findings",
            context_block_id="C0300",
            source_block_id="C0301",
            sentence_texts=("Additional safety text.",),
        ),
    ]


def _merge_mapping(target: dict[str, Any], override: Mapping[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _merge_mapping(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def build_current_aggregate_assemble_inputs(
    *,
    aggregate_units: Sequence[Mapping[str, Any]] | None = None,
    assessment_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    eligibility_status_overrides: Mapping[str, str] | None = None,
    doc_type: str = "IB",
    doc_id: str = "current_assemble",
    file_hash: str = "sha256:current-assemble",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build the four current in-memory artifacts consumed by assemble."""
    units = [dict(unit) for unit in (aggregate_units or _default_units())]
    heading_scopes = build_heading_scopes_from_aggregate_units(units)
    attach_assessment_evidence_to_heading_scopes(heading_scopes, units)

    llm_input_bundle_id = f"llm_input_{doc_id}"
    runtime_context_id = build_assessment_runtime_context_id(
        llm_input_bundle_id=llm_input_bundle_id,
    )
    assessment_input: dict[str, Any] = {
        "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
        "stage": "evidence_source_preparation",
        "phase": "prepare",
        "source_stage": "route",
        "llm_input_bundle_id": llm_input_bundle_id,
        "route": "aggregate",
        "doc_id": doc_id,
        "zone_key": "ib_clinical_safety_zh",
        "file_hash": file_hash,
        "doc_meta": {"doc_type": doc_type},
        "instructions": "test aggregate evidence assembly",
        "assessment_profile_ref": _ASSESSMENT_PROFILE,
        "heading_scopes": heading_scopes,
        "runtime_context_ref": {"runtime_context_id": runtime_context_id},
    }
    runtime_context = build_assessment_runtime_context_envelope(
        llm_input_bundle_id=llm_input_bundle_id,
        runtime_context_id=runtime_context_id,
        doc_id=doc_id,
        file_hash=file_hash,
        route_stats={"unit_count": len(units)},
        unit_provenance=build_unit_provenance_map(units),
        source_routed_unit_bundle_ref={
            "routed_unit_bundle_id": "routed_current_assemble",
            "path": "routed_units_aggregate.json",
        },
        source_routing_manifest_ref={
            "routing_manifest_id": "routing_current_assemble",
            "path": "routing_manifest.json",
        },
    )

    canonical_assessments: list[dict[str, Any]] = []
    for scope in heading_scopes:
        scope_id = str(scope["scope_id"])
        assessment: dict[str, Any] = {
            "scope_id": scope_id,
            "heading_path": list(scope["heading_path"]),
            "source_unit_ids": [str(unit["unit_id"]) for unit in scope["units"]],
            "product_context_role": "target_study_drug",
            "unit_form": "aggregate",
            "safety_role": (
                "safety_context" if scope_id == "HS0002" else "primary_safety_finding"
            ),
            "route_qc": {
                "route_mismatch": False,
                "suggested_route": None,
                "reason": None,
            },
            "post_llm_validation_flags": [],
        }
        override = (assessment_overrides or {}).get(scope_id)
        if override is not None:
            _merge_mapping(assessment, override)
        canonical_assessments.append(assessment)

    scope_assessments = build_scope_assessments_envelope(
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
        canonical_scope_assessments=canonical_assessments,
        assessment_profile_name=_ASSESSMENT_PROFILE,
        prompt_name="current_aggregate_assemble_test",
        prompt_version="1.0.0",
        llm_mode="mock",
        llm_profile=None,
    )
    eligibility_entries = build_heading_scope_eligibility_entries(
        scope_assessments=scope_assessments["scope_assessments"],
    )
    for entry in eligibility_entries:
        override_status = (eligibility_status_overrides or {}).get(str(entry["scope_id"]))
        if override_status is not None:
            entry["eligibility_decision"]["status"] = override_status
    eligibility = build_heading_scope_eligibility_envelope(
        scope_assessments_payload=scope_assessments,
        scope_eligibility_entries=eligibility_entries,
        source_scope_assessments_ref=build_in_memory_source_scope_assessments_ref(
            scope_assessments_payload=scope_assessments,
        ),
    )
    return assessment_input, runtime_context, scope_assessments, eligibility
