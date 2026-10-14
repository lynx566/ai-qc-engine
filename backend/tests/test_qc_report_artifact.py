"""Report contract acceptance and graph invariants; no projection or file reads."""

from __future__ import annotations

import json
import sys
from collections import UserDict
from copy import deepcopy
from importlib import import_module
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _integrity(status="complete", **extra):
    return {
        "status": status,
        "limitations": [] if status == "complete" else ["Result incomplete"],
        **extra,
    }


def _scope_items_for(
    anchor_block_ids: list[str],
    *,
    headings: dict[str, list[str]] | None = None,
    orders: dict[str, int] | None = None,
) -> list[dict]:
    items = []
    for anchor in anchor_block_ids:
        path = (
            headings.get(anchor, [f"Section {anchor}"])
            if headings
            else [f"Section {anchor}"]
        )
        items.append(
            {
                "anchor_block_id": anchor,
                "heading_path": list(path),
                "doc_order_index": orders.get(anchor, 0) if orders else 0,
            }
        )
    return items


def _available_configuration_selection(**kwargs) -> dict:
    auto = list(kwargs["automatic_anchor_block_ids"])
    eff = list(kwargs["effective_anchor_block_ids"])
    added = list(kwargs["added_anchor_block_ids"])
    removed = list(kwargs["removed_anchor_block_ids"])
    headings = kwargs.get("headings")
    orders = kwargs.get("orders")
    return {
        "document_ref": kwargs.get("document_ref", "d1"),
        "slot_id": kwargs.get("slot_id", "source"),
        "filter_job_id": kwargs.get("filter_job_id", "job"),
        "automatic_anchor_block_ids": auto,
        "effective_anchor_block_ids": eff,
        "added_anchor_block_ids": added,
        "removed_anchor_block_ids": removed,
        "automatic_scope_items": _scope_items_for(
            auto, headings=headings, orders=orders
        ),
        "effective_scope_items": _scope_items_for(
            eff, headings=headings, orders=orders
        ),
        "added_scope_items": _scope_items_for(added, headings=headings, orders=orders),
        "removed_scope_items": _scope_items_for(
            removed, headings=headings, orders=orders
        ),
    }


def _anchor(block="C0002", slot="source", doc="doc_one"):
    return {
        "slot_id": slot,
        "doc_id": doc,
        "block_id": block,
        "sentence_id": f"{block}:S001",
    }


def _evidence(ref="e1", block="C0002", doc_ref="d1", slot="source", doc="doc_one"):
    return {
        "evidence_ref": ref,
        "contribution_ref": "c1",
        "document_ref": doc_ref,
        "anchor": _anchor(block, slot, doc),
        "heading_path": ["Safety", block],
        "doc_order_index": 2,
        "original_sentence_text": "A😀B。",
        "block_context": {"kind": "paragraph"},
        "annotation_refs": [],
    }


def _document(ref="d1", slot="source", doc="doc_one"):
    return {
        "document_ref": ref,
        "task_input": {"task_slot_id": slot},
        "participants": [{"contribution_ref": "c1", "slot_id": slot}],
        "doc_id": doc,
        "original_file_name": "source.docx",
        "file_hash": "sha256:" + "a" * 64,
        "expected_document_type": "DSUR",
        "observed_document_type": None,
    }


def _finding(ref="f1", finding_id="L001", evidence_refs=None):
    return {
        "finding_ref": ref,
        "finding_id": finding_id,
        "label": "fail",
        "conclusion": "Conflicting values",
        "comparison_mode_id": "scope_local",
        "owner_context": {
            "contribution_ref": "c1",
            "semantic_module_id": "clinical_safety",
        },
        "evidence_refs": ["e1"] if evidence_refs is None else evidence_refs,
        "source_finding_ids": [finding_id],
    }


def _annotation(kind="edit", ref="a1", block="C0002"):
    entry = {
        "annotation_ref": ref,
        "annotation_id": f"ann_{ref}",
        "contribution_ref": "c1",
        "document_ref": "d1",
        "anchor": _anchor(block),
        "kind": kind,
        "original_sentence_text": "A😀B。",
        "selected_original_text": "😀" if kind != "comment" else "A😀B。",
        "created_at": "2026-10-10T00:00:00Z",
        "updated_at": "2026-10-10T00:01:00Z",
        "related_finding_refs": ["f1"],
        "heading_path": ["Safety", block],
    }
    if kind == "edit":
        entry.update(range={"start_offset": 1, "end_offset": 2}, replacement_text="XY")
    elif kind == "comment":
        entry["content"] = "Please verify"
    else:
        entry["range"] = {"start_offset": 1, "end_offset": 2}
    return entry


def _report():
    return {
        "report_id": "report_one",
        "generated_at": "2026-10-10T00:02:00Z",
        "task": {
            "task_run_id": "task_run_one",
            "task_id": "internal_dsur_qc",
            "display_name": "DSUR QC",
            "created_at": "2026-10-10T00:00:00Z",
            "updated_at": None,
        },
        "documents": [_document()],
        "contributions": [
            {
                "contribution_ref": "c1",
                "flow_id": "document_consistency_qc",
                "flow_run_id": "document_consistency_qc_one",
                "capability_id": "internal_dsur",
                "function_display": {"name": "Writing accuracy and consistency"},
                "execution": {
                    "outcome": "success",
                    "created_at": "2026-10-10T00:00:00Z",
                    "completed_at": "2026-10-10T00:01:00Z",
                },
                "content_domains": [
                    {
                        "semantic_module_id": "clinical_safety",
                        "display_name": "Clinical safety",
                        "finding_refs": ["f1"],
                        "coverage": [],
                        "integrity": _integrity(),
                    }
                ],
                "configuration": {
                    "availability": "unavailable",
                    "persisted_decision_at": None,
                    "selections": [],
                },
                "integrity": _integrity(
                    finalization_status="completed", fallback_comparison_modes=[]
                ),
            }
        ],
        "findings": [_finding()],
        "source_evidence": [_evidence()],
        "source_annotations": [],
        "independent_review_record_refs": [],
        "integrity": _integrity(),
    }


@pytest.fixture
def contract():
    return import_module("artifacts.qc_report")


def _build(contract, payload):
    return contract.build_qc_report(**payload)


def test_single_document_report_round_trips_without_normalizing_source_text(contract):
    source = _report()
    source["source_evidence"][0]["original_sentence_text"] = " A😀B。 "
    built = _build(contract, source)
    assert built["artifact_type"] == "qc_report"
    assert built["schema_version"] == "0.1.0"
    assert built["source_evidence"][0]["original_sentence_text"] == " A😀B。 "
    contract.validate_qc_report(json.loads(json.dumps(built, ensure_ascii=False)))
    built["documents"][0]["participants"][0]["slot_id"] = "changed"
    assert source["documents"][0]["participants"][0]["slot_id"] == "source"


def test_annotation_heading_path_is_required_detached_and_canonical(contract):
    source = _report()
    annotation = _annotation()
    source["source_annotations"] = [annotation]
    source["source_evidence"][0]["annotation_refs"] = ["a1"]
    annotation.pop("heading_path", None)
    with pytest.raises(ValueError, match="heading_path"):
        _build(contract, source)
    annotation["heading_path"] = list(source["source_evidence"][0]["heading_path"])
    current = _build(contract, source)
    assert current["source_annotations"][0]["heading_path"] == ["Safety", "C0002"]
    annotation["heading_path"].append("changed")
    assert current["source_annotations"][0]["heading_path"] == ["Safety", "C0002"]
    current["source_annotations"][0]["heading_path"] = ["wrong source location"]
    with pytest.raises(ValueError, match="heading_path"):
        contract.validate_qc_report(current)


@pytest.mark.parametrize("heading", [None, [], "Section", [""], [12]])
def test_annotation_heading_path_rejects_invalid_location(contract, heading):
    source = _report()
    annotation = _annotation()
    annotation["heading_path"] = heading
    source["source_annotations"] = [annotation]
    source["source_evidence"][0]["annotation_refs"] = ["a1"]
    with pytest.raises((TypeError, ValueError)):
        _build(contract, source)


def test_independent_annotation_heading_cannot_be_empty(contract):
    source = _report()
    annotation = _annotation(block="C0008")
    annotation.update(heading_path=[], related_finding_refs=[])
    source["source_annotations"] = [annotation]
    source["independent_review_record_refs"] = ["a1"]
    with pytest.raises(ValueError, match="heading_path"):
        _build(contract, source)


def test_finding_preserves_multiple_sections_and_evidence_order(contract):
    source = _report()
    source["source_evidence"].append(_evidence("e2", "C0008"))
    source["findings"][0]["evidence_refs"] = ["e2", "e1"]
    built = _build(contract, source)
    assert built["findings"][0]["evidence_refs"] == ["e2", "e1"]
    assert (
        built["source_evidence"][0]["heading_path"]
        != built["source_evidence"][1]["heading_path"]
    )


def test_cross_document_shape_allows_same_local_sentence_identity(contract):
    source = _report()
    source["documents"].append(_document("d2", "source_b", "doc_two"))
    source["source_evidence"].append(
        _evidence("e2", "C0002", "d2", "source_b", "doc_two")
    )
    source["findings"][0]["evidence_refs"] = ["e1", "e2"]
    source["findings"][0]["comparison_mode_id"] = "ib_to_dsur"
    built = _build(contract, source)
    assert len(built["documents"]) == 2
    assert (
        built["source_evidence"][0]["anchor"]["sentence_id"]
        == built["source_evidence"][1]["anchor"]["sentence_id"]
    )


def test_shared_annotation_is_one_entity_with_two_derived_finding_relations(contract):
    source = _report()
    source["findings"].append(_finding("f2", "L002"))
    source["contributions"][0]["content_domains"][0]["finding_refs"].append("f2")
    annotation = _annotation()
    annotation["related_finding_refs"] = ["f1", "f2"]
    source["source_annotations"] = [annotation]
    source["source_evidence"][0]["annotation_refs"] = ["a1"]
    built = _build(contract, source)
    assert len(built["source_annotations"]) == 1
    assert built["source_annotations"][0]["related_finding_refs"] == ["f1", "f2"]


def test_independent_annotation_without_finding_or_evidence(contract):
    source = _report()
    source["findings"] = []
    source["source_evidence"] = []
    source["contributions"][0]["content_domains"][0]["finding_refs"] = []
    annotation = _annotation("comment")
    annotation["related_finding_refs"] = []
    source["source_annotations"] = [annotation]
    source["independent_review_record_refs"] = ["a1"]
    built = _build(contract, source)
    assert built["source_annotations"][0]["selected_original_text"] == "A😀B。"


@pytest.mark.parametrize("kind", ["edit", "comment", "highlight"])
def test_current_annotation_kinds_and_historical_sentence_comment(contract, kind):
    source = _report()
    source["source_annotations"] = [_annotation(kind)]
    source["source_evidence"][0]["annotation_refs"] = ["a1"]
    built = _build(contract, source)
    annotation = built["source_annotations"][0]
    if kind == "comment":
        assert "range" not in annotation
        assert annotation["content"] == "Please verify"
    elif kind == "edit":
        assert annotation["selected_original_text"] == "😀"
        assert annotation["replacement_text"] == "XY"
        assert "revised_sentence_text" not in annotation


def test_range_comment_uses_original_unicode_code_points(contract):
    source = _report()
    annotation = _annotation("comment")
    annotation.update(
        range={"start_offset": 1, "end_offset": 2}, selected_original_text="😀"
    )
    source["source_annotations"] = [annotation]
    source["source_evidence"][0]["annotation_refs"] = ["a1"]
    _build(contract, source)


@pytest.mark.parametrize("decision", ["pending", "confirmed", "ignored"])
def test_current_review_decisions_remain_metadata(contract, decision):
    source = _report()
    source["findings"][0]["review_disposition"] = {
        "decision": decision,
        "marked": False,
        "note": "Finding-level note",
        "updated_at": None,
    }
    built = _build(contract, source)
    assert built["findings"][0]["review_disposition"]["decision"] == decision


def test_configuration_keeps_default_effective_and_delta_in_participant_context(
    contract,
):
    source = _report()
    source["contributions"][0]["configuration"] = {
        "availability": "available",
        "persisted_decision_at": "2026-10-10T00:00:30Z",
        "selections": [
            _available_configuration_selection(
                filter_job_id="dsur_clinical_safety",
                automatic_anchor_block_ids=["C0001", "C0005"],
                effective_anchor_block_ids=["C0001", "C0008"],
                added_anchor_block_ids=["C0008"],
                removed_anchor_block_ids=["C0005"],
                headings={
                    "C0001": ["Scope A"],
                    "C0005": ["Scope B"],
                    "C0008": ["Scope B", "Nested"],
                },
            )
        ],
    }
    built = _build(contract, source)
    selection = built["contributions"][0]["configuration"]["selections"][0]
    assert selection["added_anchor_block_ids"] == ["C0008"]
    assert selection["added_scope_items"][0]["heading_path"] == ["Scope B", "Nested"]


def test_zero_findings_incomplete_result_survives_serialization(contract):
    source = _report()
    source["findings"] = []
    source["source_evidence"] = []
    source["contributions"][0]["content_domains"][0]["finding_refs"] = []
    source["integrity"] = _integrity("partial")
    source["contributions"][0]["integrity"] = _integrity(
        "partial", finalization_status=None, fallback_comparison_modes=[]
    )
    source["contributions"][0]["content_domains"][0]["integrity"] = _integrity(
        "unavailable"
    )
    built = json.loads(json.dumps(_build(contract, source)))
    assert built["findings"] == []
    assert built["integrity"]["status"] == "partial"
    assert (
        built["contributions"][0]["content_domains"][0]["integrity"]["status"]
        == "unavailable"
    )
    contract.validate_qc_report(built)


def test_finalization_fallback_has_renderer_facing_explanation(contract):
    source = _report()
    source["contributions"][0]["integrity"].update(
        finalization_status="completed_with_fallback",
        fallback_comparison_modes=["focus_comparison"],
        limitations=[
            "Some findings could not be consolidated; retained final results are included."
        ],
    )
    _build(contract, source)


def test_success_execution_with_complete_integrity_is_valid(contract):
    _build(contract, _report())


def test_partial_execution_with_complete_integrity_is_valid_with_limitations(contract):
    source = _report()
    source["contributions"][0]["execution"]["outcome"] = "partial"
    source["contributions"][0]["integrity"].update(
        finalization_status="completed_with_fallback",
        fallback_comparison_modes=["focus_comparison"],
        limitations=[
            "Execution degraded; consolidation fallback retained all final findings."
        ],
    )
    built = _build(contract, source)
    assert built["contributions"][0]["execution"]["outcome"] == "partial"
    assert built["contributions"][0]["integrity"]["status"] == "complete"


def test_complete_integrity_rejects_failed_execution(contract):
    source = _report()
    source["contributions"][0]["execution"]["outcome"] = "failed"
    with pytest.raises(ValueError, match="failed execution"):
        _build(contract, source)


def test_complete_integrity_with_partial_execution_requires_limitations(contract):
    source = _report()
    source["contributions"][0]["execution"]["outcome"] = "partial"
    source["contributions"][0]["integrity"]["limitations"] = []
    with pytest.raises(ValueError, match="partial execution requires limitations"):
        _build(contract, source)


@pytest.mark.parametrize(
    "entity,field",
    [
        ("documents", "document_ref"),
        ("contributions", "contribution_ref"),
        ("findings", "finding_ref"),
        ("source_evidence", "evidence_ref"),
        ("source_annotations", "annotation_ref"),
    ],
)
def test_duplicate_entities_rejected(contract, entity, field):
    source = _report()
    if entity == "source_annotations":
        source[entity] = [_annotation()]
    source[entity].append(deepcopy(source[entity][0]))
    with pytest.raises(ValueError, match="duplicate"):
        _build(contract, source)


@pytest.mark.parametrize(
    "target",
    [
        "participant",
        "owner",
        "domain",
        "evidence",
        "document",
        "annotation",
        "related_finding",
        "independent",
        "configuration",
        "coverage",
    ],
)
def test_dangling_references_rejected(contract, target):
    source = _report()
    if target == "participant":
        source["documents"][0]["participants"][0]["contribution_ref"] = "missing"
    elif target == "owner":
        source["findings"][0]["owner_context"]["contribution_ref"] = "missing"
    elif target == "domain":
        source["contributions"][0]["content_domains"][0]["finding_refs"] = ["missing"]
    elif target == "evidence":
        source["findings"][0]["evidence_refs"] = ["missing"]
    elif target == "document":
        source["source_evidence"][0]["document_ref"] = "missing"
    elif target == "annotation":
        source["source_evidence"][0]["annotation_refs"] = ["missing"]
    elif target == "related_finding":
        source["source_annotations"] = [_annotation()]
        source["source_evidence"][0]["annotation_refs"] = ["a1"]
        source["source_annotations"][0]["related_finding_refs"] = ["missing"]
    elif target == "independent":
        source["independent_review_record_refs"] = ["missing"]
    elif target == "configuration":
        source["contributions"][0]["configuration"] = {
            "availability": "available",
            "persisted_decision_at": "time",
            "selections": [
                _available_configuration_selection(
                    document_ref="missing",
                    automatic_anchor_block_ids=[],
                    effective_anchor_block_ids=[],
                    added_anchor_block_ids=[],
                    removed_anchor_block_ids=[],
                )
            ],
        }
    else:
        source["contributions"][0]["content_domains"][0]["coverage"] = [
            {
                "document_ref": "missing",
                "slot_id": "source",
                "scope_id": "scope1",
                "heading_path": [],
                "execution_status": "complete",
            }
        ]
    with pytest.raises(ValueError, match="dangling reference"):
        _build(contract, source)


@pytest.mark.parametrize("field", ["evidence_refs", "source_finding_ids"])
def test_duplicate_finding_references_rejected(contract, field):
    source = _report()
    source["findings"][0][field] *= 2
    with pytest.raises(ValueError, match="duplicate"):
        _build(contract, source)


@pytest.mark.parametrize(
    "field",
    ["annotation_refs", "related_finding_refs", "independent_review_record_refs"],
)
def test_duplicate_annotation_references_rejected(contract, field):
    source = _report()
    source["source_annotations"] = [_annotation()]
    source["source_evidence"][0]["annotation_refs"] = ["a1"]
    if field == "annotation_refs":
        source["source_evidence"][0][field] *= 2
    elif field == "related_finding_refs":
        source["source_annotations"][0][field] *= 2
    else:
        source[field] = ["a1", "a1"]
    with pytest.raises(ValueError, match="duplicate"):
        _build(contract, source)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_anchor",
        "bare_alias",
        "wrong_block",
        "wrong_document",
        "wrong_slot",
        "wrong_owner_module",
        "missing_domain_backlink",
        "wrong_annotation_anchor",
        "wrong_related_findings",
        "missing_independent",
        "linked_independent",
        "range_text",
        "range_overflow",
        "negative_order",
        "resolved",
        "pass",
        "hidden_partial",
        "unexplained_partial",
        "unexplained_fallback",
        "bad_hash",
        "unknown_version",
        "chapter_owner",
        "function_id",
    ],
)
def test_semantic_contradictions_rejected(contract, mutation):
    source = _report()
    evidence = source["source_evidence"][0]
    contribution = source["contributions"][0]
    finding = source["findings"][0]
    if mutation == "missing_anchor":
        del evidence["anchor"]["slot_id"]
    elif mutation == "bare_alias":
        evidence["anchor"]["sentence_id"] = "T0001"
    elif mutation == "wrong_block":
        evidence["anchor"]["block_id"] = "C0009"
    elif mutation == "wrong_document":
        evidence["anchor"]["doc_id"] = "doc_other"
    elif mutation == "wrong_slot":
        evidence["anchor"]["slot_id"] = "source_b"
    elif mutation == "wrong_owner_module":
        finding["owner_context"]["semantic_module_id"] = "unknown"
    elif mutation == "missing_domain_backlink":
        contribution["content_domains"][0]["finding_refs"] = []
    elif mutation in {
        "wrong_annotation_anchor",
        "wrong_related_findings",
        "linked_independent",
        "range_text",
        "range_overflow",
    }:
        source["source_annotations"] = [_annotation()]
        evidence["annotation_refs"] = ["a1"]
        annotation = source["source_annotations"][0]
        if mutation == "wrong_annotation_anchor":
            annotation["anchor"] = _anchor("C0008")
        elif mutation == "wrong_related_findings":
            annotation["related_finding_refs"] = []
        elif mutation == "linked_independent":
            source["independent_review_record_refs"] = ["a1"]
        elif mutation == "range_text":
            annotation["selected_original_text"] = "B"
        else:
            annotation["range"]["end_offset"] = 99
    elif mutation == "missing_independent":
        source["source_annotations"] = [_annotation("comment", block="C0008")]
        source["source_annotations"][0]["related_finding_refs"] = []
    elif mutation == "negative_order":
        evidence["doc_order_index"] = -1
    elif mutation == "resolved":
        finding["review_disposition"] = {
            "decision": "resolved",
            "marked": False,
            "note": None,
            "updated_at": None,
        }
    elif mutation == "pass":
        source["integrity"]["status"] = "pass"
    elif mutation == "hidden_partial":
        contribution["integrity"] = _integrity("partial")
    elif mutation == "unexplained_partial":
        source["integrity"] = {"status": "partial", "limitations": []}
    elif mutation == "unexplained_fallback":
        contribution["integrity"].update(
            finalization_status="completed_with_fallback",
            fallback_comparison_modes=["scope_local"],
        )
    elif mutation == "bad_hash":
        source["documents"][0]["file_hash"] = "not-a-hash"
    elif mutation == "unknown_version":
        built = _build(contract, source)
        built["schema_version"] = "99"
        with pytest.raises(ValueError):
            contract.validate_qc_report(built)
        return
    elif mutation == "chapter_owner":
        finding["chapter_id"] = "chapter1"
    else:
        contribution["function_id"] = "invented"
    with pytest.raises((TypeError, ValueError)):
        _build(contract, source)


def test_context_qualified_finding_and_annotation_ids_can_repeat_in_another_flow(
    contract,
):
    source = _report()
    second = deepcopy(source["contributions"][0])
    second.update(contribution_ref="c2", flow_run_id="document_consistency_qc_two")
    second["content_domains"][0]["finding_refs"] = ["f2"]
    source["contributions"].append(second)
    source["documents"][0]["participants"].append(
        {"contribution_ref": "c2", "slot_id": "source"}
    )
    finding = _finding("f2")
    finding["owner_context"]["contribution_ref"] = "c2"
    finding["evidence_refs"] = ["e2"]
    source["findings"].append(finding)
    evidence = _evidence("e2")
    evidence.update(contribution_ref="c2", annotation_refs=["a2"])
    source["source_evidence"].append(evidence)
    source["source_evidence"][0]["annotation_refs"] = ["a1"]
    annotation = _annotation()
    second_annotation = deepcopy(annotation)
    second_annotation.update(
        annotation_ref="a2", contribution_ref="c2", related_finding_refs=["f2"]
    )
    source["source_annotations"] = [annotation, second_annotation]
    built = _build(contract, source)
    assert [item["finding_id"] for item in built["findings"]] == ["L001", "L001"]
    assert [item["annotation_id"] for item in built["source_annotations"]] == [
        "ann_a1",
        "ann_a1",
    ]


@pytest.mark.parametrize(
    "identity",
    ["finding", "annotation", "evidence", "flow", "task_slot", "participant"],
)
def test_duplicate_qualified_identity_with_different_refs_rejected(contract, identity):
    source = _report()
    if identity == "finding":
        source["findings"].append(_finding("f2"))
        source["contributions"][0]["content_domains"][0]["finding_refs"].append("f2")
    elif identity == "annotation":
        source["source_annotations"] = [_annotation(), _annotation(ref="a2")]
        source["source_annotations"][1]["annotation_id"] = "ann_a1"
    elif identity == "evidence":
        source["source_evidence"].append(_evidence("e2"))
    elif identity == "flow":
        second = deepcopy(source["contributions"][0])
        second["contribution_ref"] = "c2"
        source["contributions"].append(second)
    elif identity == "task_slot":
        source["documents"].append(_document("d2", doc="doc_two"))
    else:
        source["documents"][0]["participants"].append(
            {"contribution_ref": "c1", "slot_id": "source"}
        )
    with pytest.raises(ValueError, match="duplicate"):
        _build(contract, source)


def test_finding_cannot_reference_another_contribution_evidence(contract):
    source = _report()
    second = deepcopy(source["contributions"][0])
    second.update(contribution_ref="c2", flow_run_id="another_run")
    second["content_domains"][0]["finding_refs"] = []
    source["contributions"].append(second)
    source["documents"][0]["participants"].append(
        {"contribution_ref": "c2", "slot_id": "source"}
    )
    source["source_evidence"][0]["contribution_ref"] = "c2"
    with pytest.raises(ValueError, match="different contribution"):
        _build(contract, source)


def test_domain_complete_cannot_hide_failed_scope(contract):
    source = _report()
    source["contributions"][0]["content_domains"][0]["coverage"] = [
        {
            "document_ref": "d1",
            "slot_id": "source",
            "scope_id": "scope1",
            "heading_path": ["Safety"],
            "execution_status": "failed",
        }
    ]
    with pytest.raises(ValueError, match="incomplete scope"):
        _build(contract, source)


def test_configuration_delta_must_match_final_and_default_sets(contract):
    source = _report()
    source["contributions"][0]["configuration"] = {
        "availability": "available",
        "persisted_decision_at": "time",
        "selections": [
            _available_configuration_selection(
                automatic_anchor_block_ids=["C0001"],
                effective_anchor_block_ids=["C0008"],
                added_anchor_block_ids=[],
                removed_anchor_block_ids=[],
            )
        ],
    }
    with pytest.raises(ValueError, match="added/removed"):
        _build(contract, source)


def test_configuration_scope_items_must_match_anchor_order(contract):
    source = _report()
    source["contributions"][0]["configuration"] = {
        "availability": "available",
        "persisted_decision_at": "time",
        "selections": [
            _available_configuration_selection(
                automatic_anchor_block_ids=["C0001", "C0005"],
                effective_anchor_block_ids=["C0001", "C0005"],
                added_anchor_block_ids=[],
                removed_anchor_block_ids=[],
            )
        ],
    }
    source["contributions"][0]["configuration"]["selections"][0][
        "automatic_scope_items"
    ][0]["anchor_block_id"] = "C0005"
    with pytest.raises(ValueError, match="anchor_block_id must match"):
        _build(contract, source)


@pytest.mark.parametrize("order", [None, -1, True, 1.5, "1"])
def test_configuration_scope_doc_order_is_required_nonnegative_integer(contract, order):
    source = _report()
    row = _available_configuration_selection(
        automatic_anchor_block_ids=["C0001"],
        effective_anchor_block_ids=["C0001"],
        added_anchor_block_ids=[],
        removed_anchor_block_ids=[],
    )
    source["contributions"][0]["configuration"] = {
        "availability": "available",
        "persisted_decision_at": "time",
        "selections": [row],
    }
    item = row["automatic_scope_items"][0]
    if order is None:
        item.pop("doc_order_index")
    else:
        item["doc_order_index"] = order
    with pytest.raises((TypeError, ValueError), match="doc_order_index"):
        _build(contract, source)


def test_independent_records_at_same_anchor_cannot_disagree_on_raw_text(contract):
    source = _report()
    first = _annotation("comment", block="C0008")
    first["related_finding_refs"] = []
    second = _annotation("comment", ref="a2", block="C0008")
    second.update(
        original_sentence_text="different source",
        selected_original_text="different source",
        related_finding_refs=[],
    )
    source["source_annotations"] = [first, second]
    source["independent_review_record_refs"] = ["a1", "a2"]
    with pytest.raises(ValueError, match="raw source text"):
        _build(contract, source)


def test_lineage_cannot_be_claimed_twice_in_one_product_result_context(contract):
    source = _report()
    source["findings"].append(_finding("f2", "L002"))
    source["findings"][1]["source_finding_ids"] = ["L001"]
    source["contributions"][0]["content_domains"][0]["finding_refs"].append("f2")
    with pytest.raises(ValueError, match="lineage"):
        _build(contract, source)


def test_builder_materializes_entity_and_nested_mappings_for_json_serialization(
    contract,
):
    source = _report()
    source["documents"][0] = UserDict(source["documents"][0])
    source["documents"][0]["participants"][0] = UserDict(
        source["documents"][0]["participants"][0]
    )
    source["source_evidence"][0]["anchor"] = UserDict(
        source["source_evidence"][0]["anchor"]
    )
    built = _build(contract, source)
    reloaded = json.loads(json.dumps(built))
    assert reloaded["documents"][0]["participants"] == [
        {"contribution_ref": "c1", "slot_id": "source"}
    ]
    assert reloaded["source_evidence"][0]["anchor"]["sentence_id"] == "C0002:S001"
    built["documents"][0]["participants"][0]["slot_id"] = "changed"
    assert source["documents"][0]["participants"][0]["slot_id"] == "source"


def test_blank_conclusion_is_not_a_product_final_finding(contract):
    source = _report()
    source["findings"][0]["conclusion"] = " \n "
    with pytest.raises(ValueError, match="conclusion"):
        _build(contract, source)
