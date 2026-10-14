"""Persisted report inputs, without report graph assembly."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from application.document_consistency_qc.candidate_scope_read import (
    load_final_candidate_scope_configuration,
)
from application.document_consistency_qc.canonical_source_read import (
    load_canonical_source_annotations,
    project_canonical_sources,
)
from application.document_consistency_qc.document_read import DocumentReadError
from artifacts.source_annotation_state import build_source_annotation_state_payload
from runtime.io import load_json, save_json
from tests.candidate_scope_isolation import mark_canonical_flow_completed
from tests.test_internal_result_read import _default_extract_blocks
from tests.test_source_annotation_application import _write_fixture


def anchor(**changes):
    return {
        "slot_id": "source",
        "doc_id": "doc_test",
        "block_id": "C0002",
        "sentence_id": "C0002:S001",
        **changes,
    }


@pytest.fixture
def source_flow(tmp_path):
    blocks = _default_extract_blocks()
    blocks[1]["raw_text"] = " A😀B 原文 "
    blocks[1]["sentences"][0]["raw_text"] = " A😀B 原文 "
    blocks[1]["sentences"][0]["normalized_text"] = "wrong normalized"
    blocks[1]["analysis_text"] = "wrong analysis"
    flow = _write_fixture(tmp_path, extract_blocks=blocks)
    comparison = (
        tmp_path
        / "runs/document_consistency_qc/test_internal_result/participants/source/evidence_comparison"
    )
    for path in comparison.iterdir():
        path.unlink()  # These readers require no Findings/Result artifacts.
    return tmp_path, flow


def test_sources_raw_locations_and_sections(source_flow):
    root, flow = source_flow
    result = project_canonical_sources(
        project_root=root,
        flow_run_id=flow,
        anchors=[anchor(), anchor(block_id="C0004", sentence_id="C0004:S001")],
    )
    assert result[0].original_sentence_text == " A😀B 原文 "
    assert result[0].heading_path == ("Scope A",)
    assert result[1].heading_path == ("Scope B",)
    assert result[0].doc_order_index == 2
    assert result[0].document.doc_id == "doc_test"
    assert result[0].block_context.original_block_text == " A😀B 原文 "


@pytest.mark.parametrize(
    "changes",
    [
        {"slot_id": "other"},
        {"doc_id": "other"},
        {"block_id": "C9999", "sentence_id": "C9999:S001"},
        {"sentence_id": "C0002:S999"},
        {"sentence_id": "T0001"},
        {"sentence_id": "C0003:S001"},
    ],
)
def test_source_missing_and_mismatch(source_flow, changes):
    root, flow = source_flow
    with pytest.raises(DocumentReadError):
        project_canonical_sources(
            project_root=root, flow_run_id=flow, anchors=[anchor(**changes)]
        )


def test_same_local_id_different_documents_and_flow_isolation(source_flow):
    root, flow = source_flow
    flow_root = root / "runs/document_consistency_qc/test_internal_result"
    summary_path = flow_root / "flow_run_summary.json"
    summary = load_json(summary_path)
    slot = {**summary["slots"][0], "slot_id": "other", "doc_id": "doc_other"}
    summary["slots"].append(slot)
    save_json(summary_path, summary)
    bundle = load_json(flow_root / "participants/source/extract/bundle.json")
    bundle["doc_id"] = "doc_other"
    bundle["content_blocks"][1]["sentences"][0]["raw_text"] = "Other raw"
    other_path = flow_root / "participants/other/extract/bundle.json"
    other_path.parent.mkdir(parents=True)
    save_json(other_path, bundle)
    sources = project_canonical_sources(
        project_root=root,
        flow_run_id=flow,
        anchors=[anchor(), anchor(slot_id="other", doc_id="doc_other")],
    )
    assert [s.original_sentence_text for s in sources] == [" A😀B 原文 ", "Other raw"]
    with pytest.raises(DocumentReadError):
        project_canonical_sources(
            project_root=root,
            flow_run_id="document_consistency_qc_absent",
            anchors=[anchor()],
        )


def test_table_context(source_flow):
    root, flow = source_flow
    path = (
        root
        / "runs/document_consistency_qc/test_internal_result/participants/source/extract/bundle.json"
    )
    bundle = load_json(path)
    bundle["content_blocks"][1]["kind"] = "table"
    bundle["content_blocks"][1]["meta"] = {"raw_rows": [["A", "B"], ["1", "2"]]}
    save_json(path, bundle)
    result = project_canonical_sources(
        project_root=root, flow_run_id=flow, anchors=[anchor()]
    )[0]
    assert result.table_context.rows == (("A", "B"), ("1", "2"))
    assert result.block_context.kind == "table"


def persist_annotation(root, flow, *, kind="comment", ranged=True, changes=None):
    entry = {
        "annotation_id": "ann_test",
        "anchor": anchor(),
        "kind": kind,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
    if ranged:
        entry["range"] = {"start_offset": 2, "end_offset": 3}
    if kind == "edit":
        entry["replacement_text"] = "replacement fragment"
    elif kind == "comment":
        entry["content"] = "Independent review"
    entry.update(changes or {})
    path = (
        root
        / "runs/document_consistency_qc/test_internal_result/source_annotations/annotations.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(
        path,
        build_source_annotation_state_payload(
            flow_run_id=flow, annotations={"ann_test": entry}
        ),
    )


@pytest.mark.parametrize(
    "kind,ranged",
    [("edit", True), ("comment", True), ("comment", False), ("highlight", True)],
)
def test_annotations_share_source_and_unicode_ranges(source_flow, kind, ranged):
    root, flow = source_flow
    persist_annotation(root, flow, kind=kind, ranged=ranged)
    result = load_canonical_source_annotations(project_root=root, flow_run_id=flow)[0]
    evidence = project_canonical_sources(
        project_root=root, flow_run_id=flow, anchors=[anchor()]
    )[0]
    assert result.source == evidence
    assert result.selected_original_text == (
        "😀" if ranged else evidence.original_sentence_text
    )
    assert result.annotation_id == "ann_test"
    assert result.kind == kind
    assert result.replacement_text == (
        "replacement fragment" if kind == "edit" else None
    )
    assert result.created_at == "2026-01-01T00:00:00Z"
    assert "revised_sentence" not in asdict(result)


@pytest.mark.parametrize(
    "failure", ["doc", "range", "block_kind", "no_raw", "duplicate_sentence"]
)
def test_annotation_revalidates_extract(source_flow, failure):
    root, flow = source_flow
    persist_annotation(
        root,
        flow,
        changes={"anchor": anchor(doc_id="other")} if failure == "doc" else None,
    )
    path = (
        root
        / "runs/document_consistency_qc/test_internal_result/participants/source/extract/bundle.json"
    )
    bundle = load_json(path)
    block = bundle["content_blocks"][1]
    if failure == "range":
        block["sentences"][0]["raw_text"] = "A"
    elif failure == "block_kind":
        block["kind"] = "table"
    elif failure == "no_raw":
        del block["sentences"][0]["raw_text"]
    elif failure == "duplicate_sentence":
        block["sentences"].append(dict(block["sentences"][0]))
    save_json(path, bundle)
    with pytest.raises(DocumentReadError):
        load_canonical_source_annotations(project_root=root, flow_run_id=flow)


@pytest.fixture
def completed_config(paused_flow):
    config, flow, slot_id = paused_flow
    path = (
        config.workspace_root
        / "runs/document_consistency_qc"
        / flow.removeprefix("document_consistency_qc_")
        / "flow_run_summary.json"
    )

    def relocate(value):
        if isinstance(value, dict):
            return {key: relocate(item) for key, item in value.items()}
        if isinstance(value, list):
            return [relocate(item) for item in value]
        if isinstance(value, str) and "/runs/document_consistency_qc/" in value:
            return (
                config.workspace_root
                / (
                    "runs/document_consistency_qc/"
                    + value.split("/runs/document_consistency_qc/", 1)[1]
                )
            ).as_posix()
        return value

    save_json(path, relocate(load_json(path)))
    mark_canonical_flow_completed(config, flow, persist_decision=True)
    return config, flow, slot_id, path


def test_final_configuration_unchanged_and_no_setup_dependency(
    completed_config, monkeypatch
):
    config, flow, _, _ = completed_config
    from application.clinical_trial_doc_consistency_qc import capability_bindings

    monkeypatch.setattr(
        capability_bindings,
        "INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS",
        {},
    )
    rows = load_final_candidate_scope_configuration(
        project_root=config.workspace_root, flow_run_id=flow
    )
    assert rows
    for row in rows:
        assert row.flow_run_id == flow
        assert row.automatic_anchor_block_ids == row.effective_anchor_block_ids
        assert row.added_anchor_block_ids == row.removed_anchor_block_ids == ()
        assert row.persisted_decision_at


@pytest.mark.parametrize(
    "failure", ["flow", "slot", "upstream", "resolved", "anchors", "document"]
)
def test_configuration_rejects_mismatch(completed_config, failure):
    config, flow, _, summary_path = completed_config
    summary = load_json(summary_path)
    path = Path(summary["slots"][0]["candidate_scope_decision_path"])
    decision = load_json(path)
    selection = decision["candidate_selections"][0]
    if failure in {"flow", "slot"}:
        decision["flow_run_id" if failure == "flow" else "slot_id"] = "other"
    elif failure == "upstream":
        selection["resolution"]["upstream_bundle_ref"] = "runs/other.json"
    elif failure == "resolved":
        selection["resolved_bundle_ref"] = "runs/other.json"
    elif failure == "anchors":
        selection["anchor_block_ids"] = ["C9999"]
    else:
        resolved_path = config.workspace_root / selection["resolved_bundle_ref"]
        bundle = load_json(resolved_path)
        bundle["doc_id"] = "other"
        save_json(resolved_path, bundle)
    save_json(path, decision)
    with pytest.raises(DocumentReadError):
        load_final_candidate_scope_configuration(
            project_root=config.workspace_root, flow_run_id=flow
        )


def test_configuration_persisted_normalization_and_deltas(completed_config):
    from execution_flow.document_consistency_qc.candidate_scope_checkpoint import (
        build_candidate_scope_decision_payload,
        materialize_candidate_scope_zone_matches,
        persist_candidate_scope_decision,
    )
    from execution_flow.document_consistency_qc.candidate_scope_selection import (
        anchor_ids_from_zone_bundle,
        build_review_heading_ownership,
    )
    from execution_flow.document_consistency_qc.contracts import (
        FilterJobCandidateScopeSelection,
    )
    from execution_flow.document_consistency_qc.flow_loader import (
        load_flow_run_execution,
    )
    from application.clinical_trial_doc_consistency_qc.capability_bindings import (
        INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS as defaults,
    )

    config, flow, _, _ = completed_config
    root = config.workspace_root
    execution = load_flow_run_execution(project_root=root, flow_run_id=flow)
    slot = execution.slot_provenance[0]
    analysis = load_json(Path(slot.analysis_bundle_path))
    automatic = {
        job.filter_job_id: set(
            anchor_ids_from_zone_bundle(load_json(Path(job.zone_match_bundle_path)))
        )
        for job in slot.filter_jobs
    }
    default = defaults.get((execution.capability_id, slot.slot_id))
    owners = build_review_heading_ownership(
        automatic, analysis_bundle=analysis, manual_default_filter_job_id=default
    )
    headings = [
        b
        for b in analysis["content_blocks"]
        if b.get("kind") == "heading" and b["block_id"] in owners
    ]
    pairs = [
        (p, c)
        for p in headings
        for c in headings
        if len(c["heading_path"]) > len(p["heading_path"])
        and c["heading_path"][: len(p["heading_path"])] == p["heading_path"]
        and owners[p["block_id"]] == owners[c["block_id"]]
        and p["block_id"] not in automatic[owners[p["block_id"]]]
        and automatic[owners[p["block_id"]]]
    ]
    assert pairs, "fixture must exercise a changed parent/child selection"
    parent, child = pairs[0]
    job_id = owners[parent["block_id"]]
    selections = tuple(
        FilterJobCandidateScopeSelection(
            filter_job_id=key,
            anchor_block_ids=tuple(
                {parent["block_id"], child["block_id"]} if key == job_id else ids
            ),
        )
        for key, ids in automatic.items()
    )
    resolved = materialize_candidate_scope_zone_matches(
        filter_job_ids=slot.filter_job_ids,
        filter_jobs=slot.filter_jobs,
        selections=selections,
        analysis_bundle=analysis,
        block_manifest=load_json(Path(slot.block_manifest_path)),
        flow_root=execution.output_dir,
        slot_id=slot.slot_id,
        doc_id=slot.doc_id,
        project_root=root,
        manual_default_filter_job_id=default,
    )
    persist_candidate_scope_decision(
        flow_root=execution.output_dir,
        slot_id=slot.slot_id,
        payload=build_candidate_scope_decision_payload(
            flow_run_id=flow,
            slot_id=slot.slot_id,
            filter_job_ids=slot.filter_job_ids,
            resolved_jobs=resolved,
        ),
    )
    row = next(
        row
        for row in load_final_candidate_scope_configuration(
            project_root=root, flow_run_id=flow
        )
        if row.filter_job_id == job_id
    )
    assert row.effective_anchor_block_ids == (parent["block_id"],)
    assert child["block_id"] not in row.added_anchor_block_ids
    assert set(row.added_anchor_block_ids) == {parent["block_id"]} - automatic[job_id]
    assert set(row.removed_anchor_block_ids) == automatic[job_id] - {parent["block_id"]}
    assert row.added_anchor_block_ids and row.removed_anchor_block_ids


def test_result_reader_canonical_refs_are_accepted(tmp_path):
    from application.clinical_trial_doc_consistency_qc.result_read import (
        load_document_consistency_qc_result,
    )

    flow = _write_fixture(tmp_path)
    result = load_document_consistency_qc_result(
        project_root=tmp_path, flow_run_id=flow
    )
    sources = project_canonical_sources(
        project_root=tmp_path,
        flow_run_id=flow,
        anchors=result.findings[0].evidence_refs,
    )
    assert sources[0].anchor == type(sources[0].anchor)(**anchor())
    assert sources[0].original_sentence_text == "Sentence A"


def test_legacy_untyped_annotation_preserves_unavailable_semantics(source_flow):
    root, flow = source_flow
    entry = {
        "annotation_id": "ann_legacy",
        "anchor": anchor(),
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    path = (
        root
        / "runs/document_consistency_qc/test_internal_result/source_annotations/annotations.json"
    )
    path.parent.mkdir(parents=True)
    payload = build_source_annotation_state_payload(
        flow_run_id=flow, annotations={"ann_legacy": entry}
    )
    payload["schema_version"] = "0.1.0"
    save_json(path, payload)
    result = load_canonical_source_annotations(project_root=root, flow_run_id=flow)[0]
    assert result.kind is None
    assert result.selected_original_text is None
    assert result.source.original_sentence_text == " A😀B 原文 "


def test_duplicate_participant_identity_rejected(source_flow):
    root, flow = source_flow
    path = (
        root / "runs/document_consistency_qc/test_internal_result/flow_run_summary.json"
    )
    summary = load_json(path)
    summary["slots"].append(dict(summary["slots"][0]))
    save_json(path, summary)
    with pytest.raises(DocumentReadError):
        project_canonical_sources(
            project_root=root, flow_run_id=flow, anchors=[anchor()]
        )


@pytest.mark.parametrize("failure", ["doc", "hash", "missing", "duplicate_block"])
def test_extract_boundary_rejects_missing_or_wrong_identity(source_flow, failure):
    root, flow = source_flow
    path = (
        root
        / "runs/document_consistency_qc/test_internal_result/participants/source/extract/bundle.json"
    )
    bundle = load_json(path)
    if failure == "missing":
        path.unlink()
    else:
        if failure == "doc":
            bundle["doc_id"] = "another_document"
        elif failure == "hash":
            bundle["file_hash"] = "sha256:" + "0" * 64
        else:
            bundle["content_blocks"].append(dict(bundle["content_blocks"][1]))
        save_json(path, bundle)
    with pytest.raises(DocumentReadError):
        project_canonical_sources(
            project_root=root, flow_run_id=flow, anchors=[anchor()]
        )


def test_configuration_missing_final_decision_does_not_guess_automatic(
    completed_config,
):
    config, flow, _, summary_path = completed_config
    summary = load_json(summary_path)
    summary["slots"][0]["candidate_scope_decision_path"] = None
    save_json(summary_path, summary)
    with pytest.raises(DocumentReadError):
        load_final_candidate_scope_configuration(
            project_root=config.workspace_root, flow_run_id=flow
        )
