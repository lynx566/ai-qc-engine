"""Pure qualified refs and Finding/evidence/annotation co-location graph."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json


def local_ref(kind, *identity):
    encoded = json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return kind + "_" + sha256(encoded).hexdigest()


def anchor_key(anchor):
    return (anchor.slot_id, anchor.doc_id, anchor.block_id, anchor.sentence_id)


def compose_graph(
    *,
    flow_run_id,
    contribution_ref,
    document_ref,
    module_id,
    result,
    sources,
    annotations,
    reviews,
):
    evidence = {}
    source_models = {}
    related = {}
    for source in sources:
        key = anchor_key(source.anchor)
        if key in source_models and source_models[key] != source:
            raise ValueError("inconsistent source projections")
        source_models[key] = source
        if key in evidence:
            continue
        entry = {
            "evidence_ref": local_ref("evidence", flow_run_id, *key),
            "contribution_ref": contribution_ref,
            "document_ref": document_ref,
            "anchor": asdict(source.anchor),
            "heading_path": list(source.heading_path),
            "doc_order_index": source.doc_order_index,
            "original_sentence_text": source.original_sentence_text,
            "annotation_refs": [],
            "block_context": asdict(source.block_context),
        }
        if source.table_context is not None:
            entry["table_context"] = {
                "rows": [list(row) for row in source.table_context.rows]
            }
        evidence[key] = entry
        related[key] = []
    review_by_id = {review.finding_id: review for review in reviews.findings}
    findings = []
    for finding in result.findings:
        ref = local_ref("finding", flow_run_id, module_id, finding.finding_id)
        refs = []
        for anchor in finding.evidence_refs:
            key = anchor_key(anchor)
            evidence_ref = evidence[key]["evidence_ref"]
            if evidence_ref not in refs:
                refs.append(evidence_ref)
            if ref not in related[key]:
                related[key].append(ref)
        review = review_by_id.get(finding.finding_id)
        entry = {
            "finding_ref": ref,
            "finding_id": finding.finding_id,
            "label": finding.label,
            "conclusion": finding.conclusion,
            "owner_context": {
                "contribution_ref": contribution_ref,
                "semantic_module_id": module_id,
            },
            "evidence_refs": refs,
            "source_finding_ids": list(finding.source_finding_ids),
            "review_disposition": {
                "decision": review.decision if review else "pending",
                "marked": review.marked if review else False,
                "note": review.note if review else None,
                "updated_at": review.updated_at if review else None,
            },
        }
        if finding.comparison_mode_id:
            entry["comparison_mode_id"] = finding.comparison_mode_id
        findings.append(entry)
    projected_annotations, independent = [], []
    legacy_count = 0
    for annotation in annotations:
        if annotation.kind is None:
            legacy_count += 1
            continue
        source = annotation.source
        key = anchor_key(source.anchor)
        if key in source_models and source_models[key] != source:
            raise ValueError("inconsistent evidence and annotation source")
        ref = local_ref("annotation", flow_run_id, annotation.annotation_id)
        entry = {
            "annotation_ref": ref,
            "annotation_id": annotation.annotation_id,
            "contribution_ref": contribution_ref,
            "document_ref": document_ref,
            "anchor": asdict(source.anchor),
            "kind": annotation.kind,
            "original_sentence_text": source.original_sentence_text,
            "selected_original_text": annotation.selected_original_text,
            "heading_path": list(source.heading_path),
            "created_at": annotation.created_at,
            "updated_at": annotation.updated_at,
            "related_finding_refs": related.get(key, []),
        }
        if annotation.range is not None:
            entry["range"] = asdict(annotation.range)
        for field in ("replacement_text", "content"):
            value = getattr(annotation, field)
            if value is not None:
                entry[field] = value
        projected_annotations.append(entry)
        if key in evidence:
            evidence[key]["annotation_refs"].append(ref)
        elif annotation.kind in {"edit", "comment"}:
            independent.append(ref)
    return (
        findings,
        list(evidence.values()),
        projected_annotations,
        independent,
        legacy_count,
    )
