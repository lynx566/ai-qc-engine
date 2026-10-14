"""Aggregate evidence assembly semantics and ownership tests."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.heading_scope_eligibility import (
    HEADING_SCOPE_ELIGIBILITY_STATUSES,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assemble_aggregate_evidence_source_bundle import (
    assemble_aggregate_evidence_source_bundle,
)
from tests.current_aggregate_assemble_test_helpers import (
    build_current_aggregate_assemble_inputs,
)

ARTIFACT_PATH = (
    BACKEND_ROOT
    / "artifacts/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/aggregate_evidence_source_bundle.py"
)
STEP_PATH = BACKEND_ROOT / "steps/evidence_source_preparation.py"
ASSEMBLER_PATH = (
    BACKEND_ROOT
    / "plugins/clinical_trial_doc/evidence_source_preparation/clinical_safety/aggregate_evidence"
    / "assemble_aggregate_evidence_source_bundle.py"
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def test_artifact_has_no_plugin_or_runtime_dependency() -> None:
    imports = _imports(ARTIFACT_PATH)
    assert not any(name.startswith(("plugins.", "runtime.", "scripts.")) for name in imports)


def test_step_imports_only_neutral_operation_contracts() -> None:
    source = STEP_PATH.read_text(encoding="utf-8")
    assert "evidence_source_preparation.aggregate_evidence" not in source
    assert "plugins.clinical_trial_doc.evidence_source_preparation" not in source
    assert "operations.evidence_source_preparation.contracts" in source


def test_eligibility_policy_and_document_mapping_are_not_artifact_owned() -> None:
    source = ARTIFACT_PATH.read_text(encoding="utf-8")
    assert "INCLUDED_ELIGIBILITY_STATUSES" not in source
    assert "DOCUMENT_TYPE_MAP" not in source
    assert "resolve_scope_origin" not in source
    plugin_source = ASSEMBLER_PATH.read_text(encoding="utf-8")
    assert "INCLUDED_ELIGIBILITY_STATUSES" in plugin_source


def test_review_ambiguous_is_retained_without_copying_decision_metadata() -> None:
    assessment_input, runtime_context, scope_assessments, eligibility = (
        build_current_aggregate_assemble_inputs(
            assessment_overrides={"HS0001": {"safety_role": "unknown"}},
        )
    )
    result = assemble_aggregate_evidence_source_bundle(
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
        scope_assessments=scope_assessments,
        heading_scope_eligibility=eligibility,
    )
    first = result.aggregate_evidence_source_bundle["heading_scopes"][0]
    assert first["scope_id"] == "HS0001"
    assert "eligibility" not in first
    assert "annotation_hints" not in first


@pytest.mark.parametrize(
    "status",
    sorted(status for status in HEADING_SCOPE_ELIGIBILITY_STATUSES if status.startswith("excluded_")),
)
def test_excluded_statuses_are_omitted(status: str) -> None:
    target_scope_id = "HS0001"
    assessment_input, runtime_context, scope_assessments, eligibility = (
        build_current_aggregate_assemble_inputs(
            eligibility_status_overrides={target_scope_id: status},
        )
    )
    result = assemble_aggregate_evidence_source_bundle(
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
        scope_assessments=scope_assessments,
        heading_scope_eligibility=eligibility,
    )
    assert target_scope_id not in {
        scope["scope_id"]
        for scope in result.aggregate_evidence_source_bundle["heading_scopes"]
    }


def test_evidence_keeps_text_order_and_block_provenance() -> None:
    assessment_input, runtime_context, scope_assessments, eligibility = (
        build_current_aggregate_assemble_inputs()
    )
    result = assemble_aggregate_evidence_source_bundle(
        assessment_input=assessment_input,
        assessment_runtime_context=runtime_context,
        scope_assessments=scope_assessments,
        heading_scope_eligibility=eligibility,
    )
    for scope in result.aggregate_evidence_source_bundle["heading_scopes"]:
        for expected_unit_order, unit in enumerate(scope["units"]):
            provenance = runtime_context["unit_provenance"][unit["unit_id"]]
            assert unit["unit_order"] == expected_unit_order
            assert unit["text"] == provenance["candidate_text"]
            assert unit["source"]["block_ids"] == provenance["source_block_ids"]
            assert [sentence["sentence_order"] for sentence in unit["sentences"]] == list(
                range(len(unit["sentences"]))
            )
def test_excluded_scope_remains_resolvable_through_upstream_provenance() -> None:
    _, runtime_context, scope_assessments, eligibility = (
        build_current_aggregate_assemble_inputs()
    )
    assert runtime_context["source_refs"]["source_routed_unit_bundle_ref"]
    assert runtime_context["source_refs"]["source_routing_manifest_ref"]
    excluded_entry = next(
        entry
        for entry in eligibility["scope_eligibility_entries"]
        if entry["eligibility_decision"]["status"].startswith("excluded_")
    )
    assessment_entry = next(
        entry
        for entry in scope_assessments["scope_assessments"]
        if entry["scope_id"] == excluded_entry["scope_id"]
    )
    assert assessment_entry["source_unit_ids"] == excluded_entry["source_unit_ids"]
    for unit_id in excluded_entry["source_unit_ids"]:
        provenance = runtime_context["unit_provenance"][unit_id]
        assert provenance["source_block_ids"]
        assert provenance["sentence_source_block_ids"]
        assert provenance["text_refs"]
        assert provenance["route_basis"]
        assert "route_matched_terms" in provenance
