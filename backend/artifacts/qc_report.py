"""Pure TaskRun report contract, independent of projection, storage and rendering.

References are report-local opaque strings; formal identities remain separate.
Finding identity is qualified by contribution and semantic module. Chapters only
locate canonical Extract evidence. Annotation relations describe co-location on
evidence, never an explicit user binding to a Finding. No count implies pass.
See docs/architecture/qc_report_contract.md for the frozen v0.1.0 semantics.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.finding_review_state import REVIEW_DECISIONS
from artifacts.source_annotation_state import (
    SOURCE_ANNOTATION_KINDS,
    validate_source_annotation_entry,
    validate_source_sentence_anchor,
)
from core.document.doc_identity import validate_file_hash_format

QC_REPORT_ARTIFACT_TYPE = "qc_report"
QC_REPORT_SCHEMA_VERSION = "0.1.0"
REPORT_INTEGRITY_STATUSES = frozenset({"complete", "partial", "failed", "unavailable"})
_FINDING_ID = re.compile(r"^L[0-9]{3}$")
_TASK_RUN_ID = re.compile(r"^task_run_[A-Za-z0-9][A-Za-z0-9_]*$")


def _object(
    value: Any, path: str, required: str, optional: str = ""
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be an object")
    required_keys, optional_keys = set(required.split()), set(optional.split())
    missing = required_keys - set(value)
    unknown = set(value) - required_keys - optional_keys
    if missing or unknown:
        raise ValueError(
            f"{path} keys mismatch; missing={sorted(missing)!r}, unknown={sorted(unknown)!r}"
        )
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be non-empty text")
    if value != value.strip():
        raise ValueError(f"{path} must be trimmed")
    return value


def _raw_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be non-empty raw text")
    return value


def _nullable_text(value: Any, path: str) -> None:
    if value is not None:
        _text(value, path)


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{path} must be an array")
    return value


def _strings(value: Any, path: str, *, unique: bool = True) -> list[str]:
    values = [
        _text(item, f"{path}[{index}]")
        for index, item in enumerate(_array(value, path))
    ]
    if unique and len(values) != len(set(values)):
        raise ValueError(f"{path} contains duplicate references or identities")
    return values


def _enum(value: Any, choices: frozenset[str], path: str) -> str:
    text = _text(value, path)
    if text not in choices:
        raise ValueError(f"{path} must be one of {sorted(choices)!r}")
    return text


def _nonnegative_int(value: Any, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path} must be a nonnegative integer")


def _index(value: Any, key: str, path: str) -> dict[str, Mapping[str, Any]]:
    result = {}
    for index, item in enumerate(_array(value, path)):
        if not isinstance(item, Mapping):
            raise TypeError(f"{path}[{index}] must be an object")
        identity = _text(item.get(key), f"{path}[{index}].{key}")
        if identity in result:
            raise ValueError(f"{path} has duplicate {key}: {identity!r}")
        result[identity] = item
    return result


def _resolve(index: Mapping[str, Any], ref: str, path: str) -> Any:
    if ref not in index:
        raise ValueError(f"{path} has dangling reference {ref!r}")
    return index[ref]


def _unique_identity(seen: set[Any], identity: Any, path: str) -> None:
    if identity in seen:
        raise ValueError(f"{path} has duplicate qualified identity {identity!r}")
    seen.add(identity)


def _integrity(value: Any, path: str) -> str:
    item = _object(
        value,
        path,
        "status limitations",
        "finalization_status fallback_comparison_modes",
    )
    status = _enum(item["status"], REPORT_INTEGRITY_STATUSES, f"{path}.status")
    limitations = _strings(item["limitations"], f"{path}.limitations", unique=False)
    if status != "complete" and not limitations:
        raise ValueError(
            f"{path} incomplete integrity requires a human-readable limitation"
        )
    finalization = item.get("finalization_status")
    if finalization is not None:
        _enum(
            finalization,
            frozenset({"completed", "completed_with_fallback"}),
            f"{path}.finalization_status",
        )
    fallback = _strings(
        item.get("fallback_comparison_modes", []), f"{path}.fallback_comparison_modes"
    )
    if bool(fallback) != (finalization == "completed_with_fallback"):
        raise ValueError(
            f"{path} finalization status and fallback information disagree"
        )
    if fallback and not limitations:
        raise ValueError(f"{path} fallback requires a human-readable limitation")
    return status


def _require_not_hidden(parent: str, children: Sequence[str], path: str) -> None:
    if parent == "complete" and any(child != "complete" for child in children):
        raise ValueError(
            f"{path} complete integrity cannot hide an incomplete child result"
        )


def _document(value: Mapping[str, Any], path: str) -> None:
    _object(
        value,
        path,
        "document_ref task_input participants doc_id original_file_name file_hash expected_document_type observed_document_type",
    )
    _text(value["doc_id"], f"{path}.doc_id")
    _text(value["original_file_name"], f"{path}.original_file_name")
    validate_file_hash_format(_text(value["file_hash"], f"{path}.file_hash"))
    _nullable_text(value["expected_document_type"], f"{path}.expected_document_type")
    _nullable_text(value["observed_document_type"], f"{path}.observed_document_type")
    task_input = _object(value["task_input"], f"{path}.task_input", "task_slot_id")
    _text(task_input["task_slot_id"], f"{path}.task_input.task_slot_id")
    participants = _array(value["participants"], f"{path}.participants")
    if not participants:
        raise ValueError(f"{path}.participants must be non-empty")
    for participant in participants:
        _object(participant, f"{path}.participant", "contribution_ref slot_id")
        for key in ("contribution_ref", "slot_id"):
            _text(participant[key], f"{path}.participant.{key}")


def _scope_items(
    items: Any,
    anchor_ids: Sequence[str],
    path: str,
) -> None:
    rows = _array(items, path)
    if len(rows) != len(anchor_ids):
        raise ValueError(
            f"{path} must have one scope item per anchor_block_id "
            f"({len(rows)} != {len(anchor_ids)})"
        )
    for index, row in enumerate(rows):
        item_path = f"{path}[{index}]"
        item = _object(row, item_path, "anchor_block_id heading_path doc_order_index")
        _nonnegative_int(item["doc_order_index"], f"{item_path}.doc_order_index")
        anchor = _text(item["anchor_block_id"], f"{item_path}.anchor_block_id")
        if anchor != anchor_ids[index]:
            raise ValueError(
                f"{item_path}.anchor_block_id must match "
                f"{path.replace('_scope_items', '_anchor_block_ids')}[{index}]"
            )
        heading_path = _strings(
            item["heading_path"], f"{item_path}.heading_path", unique=False
        )
        if not heading_path:
            raise ValueError(f"{item_path}.heading_path must be non-empty")


def _configuration(value: Any, path: str) -> None:
    config = _object(value, path, "availability persisted_decision_at selections")
    availability = _enum(
        config["availability"],
        frozenset({"available", "unavailable"}),
        f"{path}.availability",
    )
    _nullable_text(config["persisted_decision_at"], f"{path}.persisted_decision_at")
    selections = _array(config["selections"], f"{path}.selections")
    if availability == "unavailable":
        if selections or config["persisted_decision_at"] is not None:
            raise ValueError(
                f"{path} unavailable configuration cannot claim persisted selections"
            )
    elif config["persisted_decision_at"] is None or not selections:
        raise ValueError(
            f"{path} available configuration requires decision time and selections"
        )
    seen: set[Any] = set()
    for selection in selections:
        selection_path = f"{path}.selection"
        _object(
            selection,
            selection_path,
            "document_ref slot_id filter_job_id "
            "automatic_anchor_block_ids effective_anchor_block_ids "
            "added_anchor_block_ids removed_anchor_block_ids "
            "automatic_scope_items effective_scope_items "
            "added_scope_items removed_scope_items",
        )
        for key in ("document_ref", "slot_id", "filter_job_id"):
            _text(selection[key], f"{selection_path}.{key}")
        _unique_identity(seen, (selection["slot_id"], selection["filter_job_id"]), path)
        sets = {}
        anchor_lists: dict[str, list[str]] = {}
        for key in ("automatic", "effective", "added", "removed"):
            anchor_lists[key] = _strings(
                selection[f"{key}_anchor_block_ids"],
                f"{selection_path}.{key}_anchor_block_ids",
            )
            sets[key] = set(anchor_lists[key])
        if (
            sets["added"] != sets["effective"] - sets["automatic"]
            or sets["removed"] != sets["automatic"] - sets["effective"]
        ):
            raise ValueError(
                f"{path} added/removed selections disagree with automatic/effective selections"
            )
        for key in ("automatic", "effective", "added", "removed"):
            _scope_items(
                selection[f"{key}_scope_items"],
                anchor_lists[key],
                f"{selection_path}.{key}_scope_items",
            )


def _contribution(value: Mapping[str, Any], path: str) -> None:
    _object(
        value,
        path,
        "contribution_ref flow_id flow_run_id capability_id function_display execution content_domains configuration integrity",
    )
    for key in ("flow_id", "flow_run_id", "capability_id"):
        _text(value[key], f"{path}.{key}")
    display = _object(
        value["function_display"], f"{path}.function_display", "name", "description"
    )
    _text(display["name"], f"{path}.function_display.name")
    if "description" in display:
        _text(display["description"], f"{path}.function_display.description")
    execution = _object(
        value["execution"], f"{path}.execution", "outcome created_at completed_at"
    )
    _enum(
        execution["outcome"],
        frozenset({"success", "partial", "failed", "paused", "unknown"}),
        f"{path}.execution.outcome",
    )
    for key in ("created_at", "completed_at"):
        _nullable_text(execution[key], f"{path}.execution.{key}")
    domains = _index(
        value["content_domains"], "semantic_module_id", f"{path}.content_domains"
    )
    if not domains:
        raise ValueError(f"{path}.content_domains must be non-empty")
    states = []
    for domain in domains.values():
        _object(
            domain,
            f"{path}.domain",
            "semantic_module_id display_name finding_refs coverage integrity",
        )
        _text(domain["display_name"], f"{path}.domain.display_name")
        _strings(domain["finding_refs"], f"{path}.domain.finding_refs")
        states.append(_integrity(domain["integrity"], f"{path}.domain.integrity"))
        coverage_seen: set[Any] = set()
        coverage = _array(domain["coverage"], f"{path}.domain.coverage")
        for scope in coverage:
            _object(
                scope,
                f"{path}.scope",
                "document_ref slot_id scope_id heading_path execution_status",
            )
            for key in ("document_ref", "slot_id", "scope_id"):
                _text(scope[key], f"{path}.scope.{key}")
            _strings(scope["heading_path"], f"{path}.scope.heading_path", unique=False)
            _unique_identity(
                coverage_seen,
                (scope["document_ref"], scope["slot_id"], scope["scope_id"]),
                path,
            )
            status = _enum(
                scope["execution_status"],
                frozenset({"complete", "partial", "failed", "not_checked"}),
                f"{path}.scope.execution_status",
            )
            if domain["integrity"]["status"] == "complete" and status != "complete":
                raise ValueError(
                    f"{path} complete domain cannot hide incomplete scope coverage"
                )
    state = _integrity(value["integrity"], f"{path}.integrity")
    _require_not_hidden(state, states, path)
    outcome = execution["outcome"]
    contribution_limitations = _strings(
        value["integrity"]["limitations"],
        f"{path}.integrity.limitations",
        unique=False,
    )
    if state == "complete" and outcome == "failed":
        raise ValueError(
            f"{path} complete integrity cannot represent a failed execution"
        )
    if state == "complete" and outcome == "partial" and not contribution_limitations:
        raise ValueError(
            f"{path} complete integrity with partial execution requires limitations"
        )
    _configuration(value["configuration"], f"{path}.configuration")


def _finding(value: Mapping[str, Any], path: str) -> None:
    _object(
        value,
        path,
        "finding_ref finding_id label conclusion owner_context evidence_refs",
        "comparison_mode_id source_finding_ids review_disposition",
    )
    if _FINDING_ID.fullmatch(_text(value["finding_id"], f"{path}.finding_id")) is None:
        raise ValueError(f"{path}.finding_id must match product-final Lddd identity")
    _enum(value["label"], frozenset({"fail", "need_review"}), f"{path}.label")
    if not _raw_text(value["conclusion"], f"{path}.conclusion").strip():
        raise ValueError(f"{path}.conclusion must be nonblank product-final text")
    owner = _object(
        value["owner_context"],
        f"{path}.owner_context",
        "contribution_ref semantic_module_id",
    )
    for key in ("contribution_ref", "semantic_module_id"):
        _text(owner[key], f"{path}.owner_context.{key}")
    if not _strings(value["evidence_refs"], f"{path}.evidence_refs"):
        raise ValueError(f"{path}.evidence_refs must be non-empty")
    if "comparison_mode_id" in value:
        _text(value["comparison_mode_id"], f"{path}.comparison_mode_id")
    if "source_finding_ids" in value:
        lineage = _strings(value["source_finding_ids"], f"{path}.source_finding_ids")
        if not lineage or any(
            _FINDING_ID.fullmatch(identity) is None for identity in lineage
        ):
            raise ValueError(
                f"{path}.source_finding_ids must be non-empty product-final lineage IDs"
            )
    if "review_disposition" in value:
        review = _object(
            value["review_disposition"],
            f"{path}.review_disposition",
            "decision marked note updated_at",
        )
        _enum(
            review["decision"], REVIEW_DECISIONS, f"{path}.review_disposition.decision"
        )
        if not isinstance(review["marked"], bool):
            raise TypeError(f"{path}.review_disposition.marked must be boolean")
        for key in ("note", "updated_at"):
            _nullable_text(review[key], f"{path}.review_disposition.{key}")


def _source(value: Mapping[str, Any], path: str, *, annotation: bool) -> None:
    if annotation:
        _object(
            value,
            path,
            "annotation_ref annotation_id contribution_ref document_ref anchor kind original_sentence_text selected_original_text created_at updated_at related_finding_refs heading_path",
            "range replacement_text content",
        )
        _enum(value["kind"], SOURCE_ANNOTATION_KINDS, f"{path}.kind")
        _text(value["annotation_id"], f"{path}.annotation_id")
        entry = {
            key: value[key]
            for key in ("annotation_id", "anchor", "kind", "created_at", "updated_at")
        }
        for key in ("range", "replacement_text", "content"):
            if key in value:
                entry[key] = value[key]
        if "range" in value:
            _object(value["range"], f"{path}.range", "start_offset end_offset")
        validate_source_annotation_entry(entry, annotation_id=value["annotation_id"])
        for key in ("created_at", "updated_at"):
            _text(value[key], f"{path}.{key}")
        _strings(value["related_finding_refs"], f"{path}.related_finding_refs")
        if not _strings(value["heading_path"], f"{path}.heading_path", unique=False):
            raise ValueError(f"{path}.heading_path must be non-empty")
    else:
        _object(
            value,
            path,
            "evidence_ref contribution_ref document_ref anchor heading_path doc_order_index original_sentence_text annotation_refs",
            "block_context table_context",
        )
        _strings(value["heading_path"], f"{path}.heading_path", unique=False)
        _nonnegative_int(value["doc_order_index"], f"{path}.doc_order_index")
        _strings(value["annotation_refs"], f"{path}.annotation_refs")
        if "block_context" in value:
            context = _object(
                value["block_context"],
                f"{path}.block_context",
                "kind",
                "original_block_text",
            )
            _text(context["kind"], f"{path}.block_context.kind")
            if "original_block_text" in context:
                _raw_text(
                    context["original_block_text"],
                    f"{path}.block_context.original_block_text",
                )
        if "table_context" in value:
            context = _object(value["table_context"], f"{path}.table_context", "rows")
            rows = _array(context["rows"], f"{path}.table_context.rows")
            if not rows:
                raise ValueError(f"{path}.table_context.rows must be non-empty")
            for row in rows:
                if not _array(row, f"{path}.table_context.row") or any(
                    not isinstance(cell, str) for cell in row
                ):
                    raise ValueError(
                        f"{path}.table_context rows must contain text cells"
                    )
    for key in ("contribution_ref", "document_ref"):
        _text(value[key], f"{path}.{key}")
    anchor = _object(
        value["anchor"], f"{path}.anchor", "slot_id doc_id block_id sentence_id"
    )
    for key in anchor:
        _text(anchor[key], f"{path}.anchor.{key}")
    validate_source_sentence_anchor(anchor)
    raw = _raw_text(value["original_sentence_text"], f"{path}.original_sentence_text")
    if annotation:
        selected = _raw_text(
            value["selected_original_text"], f"{path}.selected_original_text"
        )
        if value.get("range") is None:
            expected = raw
        else:
            start, end = value["range"]["start_offset"], value["range"]["end_offset"]
            if end > len(raw):
                raise ValueError(f"{path}.range exceeds canonical raw source text")
            expected = raw[start:end]
        if selected != expected:
            raise ValueError(
                f"{path}.selected_original_text disagrees with canonical raw source text/range"
            )


def _source_identity(value: Mapping[str, Any]) -> tuple[str, ...]:
    anchor = value["anchor"]
    return (
        value["contribution_ref"],
        value["document_ref"],
        anchor["slot_id"],
        anchor["doc_id"],
        anchor["block_id"],
        anchor["sentence_id"],
    )


def _participant_document(
    documents: Mapping[str, Any],
    participants: Mapping[Any, str],
    *,
    contribution_ref: str,
    document_ref: str,
    slot_id: str,
    path: str,
) -> Mapping[str, Any]:
    document = _resolve(documents, document_ref, path)
    if participants.get((contribution_ref, slot_id)) != document_ref:
        raise ValueError(
            f"{path} document is not the declared contribution participant slot"
        )
    return document


def _validate_graph(
    documents: Mapping[str, Any],
    contributions: Mapping[str, Any],
    findings: Mapping[str, Any],
    evidence: Mapping[str, Any],
    annotations: Mapping[str, Any],
    independent: list[str],
) -> None:
    participant_documents: dict[Any, str] = {}
    task_slots: set[Any] = set()
    for ref, document in documents.items():
        _unique_identity(
            task_slots, document["task_input"]["task_slot_id"], "documents.task_input"
        )
        for participant in document["participants"]:
            contribution_ref = participant["contribution_ref"]
            _resolve(contributions, contribution_ref, "documents.participants")
            key = (contribution_ref, participant["slot_id"])
            if key in participant_documents:
                raise ValueError(
                    "documents.participants has duplicate participant slot identity"
                )
            participant_documents[key] = ref

    flow_ids: set[Any] = set()
    domains: dict[Any, Any] = {}
    for ref, contribution in contributions.items():
        _unique_identity(
            flow_ids,
            (contribution["flow_id"], contribution["flow_run_id"]),
            "contributions",
        )
        if not any(key[0] == ref for key in participant_documents):
            raise ValueError("contribution has no document participant")
        for domain in contribution["content_domains"]:
            domains[(ref, domain["semantic_module_id"])] = domain
            for scope in domain["coverage"]:
                _participant_document(
                    documents,
                    participant_documents,
                    contribution_ref=ref,
                    document_ref=scope["document_ref"],
                    slot_id=scope["slot_id"],
                    path="coverage",
                )
        for selection in contribution["configuration"]["selections"]:
            _participant_document(
                documents,
                participant_documents,
                contribution_ref=ref,
                document_ref=selection["document_ref"],
                slot_id=selection["slot_id"],
                path="configuration",
            )

    source_ids: set[Any] = set()
    annotation_ids: set[Any] = set()
    annotations_by_source: dict[Any, set[str]] = {}
    raw_text_by_source: dict[Any, str] = {}
    heading_path_by_source: dict[Any, list[str]] = {}
    for collection, is_annotation in ((evidence, False), (annotations, True)):
        for ref, source in collection.items():
            _resolve(
                contributions, source["contribution_ref"], "source.contribution_ref"
            )
            document = _participant_document(
                documents,
                participant_documents,
                contribution_ref=source["contribution_ref"],
                document_ref=source["document_ref"],
                slot_id=source["anchor"]["slot_id"],
                path="source",
            )
            if document["doc_id"] != source["anchor"]["doc_id"]:
                raise ValueError(
                    "source anchor doc_id disagrees with document identity"
                )
            identity = _source_identity(source)
            raw = source["original_sentence_text"]
            if identity in raw_text_by_source and raw_text_by_source[identity] != raw:
                raise ValueError(
                    "records at one canonical anchor disagree on raw source text"
                )
            raw_text_by_source[identity] = raw
            if "heading_path" in source:
                heading_path = source["heading_path"]
                if (
                    identity in heading_path_by_source
                    and heading_path_by_source[identity] != heading_path
                ):
                    raise ValueError(
                        "records at one canonical anchor disagree on heading_path"
                    )
                heading_path_by_source[identity] = heading_path
            if is_annotation:
                _unique_identity(
                    annotation_ids,
                    (source["contribution_ref"], source["annotation_id"]),
                    "annotations",
                )
                annotations_by_source.setdefault(identity, set()).add(ref)
            else:
                _unique_identity(source_ids, identity, "evidence")

    for source in evidence.values():
        for ref in source["annotation_refs"]:
            annotation = _resolve(annotations, ref, "evidence.annotation_refs")
            if _source_identity(source) != _source_identity(annotation):
                raise ValueError(
                    "evidence annotation does not share its canonical source identity"
                )
            if source["original_sentence_text"] != annotation["original_sentence_text"]:
                raise ValueError(
                    "evidence and annotation canonical raw source text disagree"
                )
            if (
                "range" in annotation
                and source.get("block_context", {}).get("kind", "paragraph")
                != "paragraph"
            ):
                raise ValueError("ranged annotations require paragraph source context")
        if set(source["annotation_refs"]) != annotations_by_source.get(
            _source_identity(source), set()
        ):
            raise ValueError(
                "evidence.annotation_refs must include all records at its canonical source anchor"
            )

    finding_ids: set[Any] = set()
    claimed_lineage: set[Any] = set()
    expected_domain_findings: dict[Any, set[str]] = {key: set() for key in domains}
    related: dict[str, set[str]] = {ref: set() for ref in annotations}
    for ref, finding in findings.items():
        owner = finding["owner_context"]
        domain_key = (owner["contribution_ref"], owner["semantic_module_id"])
        _resolve(domains, domain_key, "finding.owner_context")
        _unique_identity(finding_ids, (*domain_key, finding["finding_id"]), "findings")
        for source_finding_id in finding.get("source_finding_ids", []):
            _unique_identity(
                claimed_lineage, (*domain_key, source_finding_id), "Finding lineage"
            )
        expected_domain_findings[domain_key].add(ref)
        for evidence_ref in finding["evidence_refs"]:
            source = _resolve(evidence, evidence_ref, "finding.evidence_refs")
            if source["contribution_ref"] != owner["contribution_ref"]:
                raise ValueError("Finding evidence belongs to a different contribution")
            for annotation_ref in source["annotation_refs"]:
                related[annotation_ref].add(ref)
    for key, domain in domains.items():
        for ref in domain["finding_refs"]:
            _resolve(findings, ref, "content_domain.finding_refs")
        if set(domain["finding_refs"]) != expected_domain_findings[key]:
            raise ValueError(
                "content domain Finding references disagree with owner context"
            )
    for ref, annotation in annotations.items():
        for finding_ref in annotation["related_finding_refs"]:
            _resolve(findings, finding_ref, "annotation.related_finding_refs")
        if set(annotation["related_finding_refs"]) != related[ref]:
            raise ValueError(
                "annotation related Findings must equal its evidence-derived associations"
            )
    for ref in independent:
        _resolve(annotations, ref, "independent_review_record_refs")
    expected_independent = {
        ref
        for ref, annotation in annotations.items()
        if annotation["kind"] in {"edit", "comment"} and not related[ref]
    }
    if set(independent) != expected_independent:
        raise ValueError(
            "independent review references must exactly list unassociated edit/comment records"
        )


def validate_qc_report(payload: Mapping[str, Any]) -> None:
    """Validate local shapes and all report references without reading artifacts.

    Arrays retain producer order. The validator never sorts, normalizes source
    text, derives revisions, computes a verdict, or mutates the supplied mapping.
    """
    _object(
        payload,
        "report",
        "artifact_type schema_version report_id generated_at task documents contributions findings source_evidence source_annotations independent_review_record_refs integrity",
    )
    if payload["artifact_type"] != QC_REPORT_ARTIFACT_TYPE:
        raise ValueError("report artifact_type mismatch")
    if payload["schema_version"] != QC_REPORT_SCHEMA_VERSION:
        raise ValueError("report schema_version mismatch")
    for key in ("report_id", "generated_at"):
        _text(payload[key], f"report.{key}")
    task = _object(
        payload["task"],
        "task",
        "task_run_id task_id display_name created_at updated_at",
    )
    for key in ("task_run_id", "task_id", "display_name"):
        _text(task[key], f"task.{key}")
    if _TASK_RUN_ID.fullmatch(task["task_run_id"]) is None:
        raise ValueError("task.task_run_id must be a canonical TaskRun identifier")
    for key in ("created_at", "updated_at"):
        _nullable_text(task[key], f"task.{key}")
    documents = _index(payload["documents"], "document_ref", "documents")
    contributions = _index(
        payload["contributions"], "contribution_ref", "contributions"
    )
    findings = _index(payload["findings"], "finding_ref", "findings")
    evidence = _index(payload["source_evidence"], "evidence_ref", "source_evidence")
    annotations = _index(
        payload["source_annotations"], "annotation_ref", "source_annotations"
    )
    if not documents or not contributions:
        raise ValueError(
            "report requires documents and contributions; document count has no upper bound"
        )
    for ref, document in documents.items():
        _document(document, f"documents[{ref}]")
    for ref, contribution in contributions.items():
        _contribution(contribution, f"contributions[{ref}]")
    for ref, finding in findings.items():
        _finding(finding, f"findings[{ref}]")
    for ref, source in evidence.items():
        _source(source, f"source_evidence[{ref}]", annotation=False)
    for ref, annotation in annotations.items():
        _source(annotation, f"source_annotations[{ref}]", annotation=True)
    independent = _strings(
        payload["independent_review_record_refs"], "independent_review_record_refs"
    )
    _require_not_hidden(
        _integrity(payload["integrity"], "report.integrity"),
        [
            contribution["integrity"]["status"]
            for contribution in contributions.values()
        ],
        "report",
    )
    _validate_graph(
        documents, contributions, findings, evidence, annotations, independent
    )


def build_qc_report(
    *,
    report_id: str,
    generated_at: str,
    task: Mapping[str, Any],
    documents: Sequence[Mapping[str, Any]],
    contributions: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
    source_evidence: Sequence[Mapping[str, Any]],
    source_annotations: Sequence[Mapping[str, Any]],
    independent_review_record_refs: Sequence[str],
    integrity: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a detached validated mapping; no defaults infer result completeness."""
    payload = _detach_mapping(
        {
            "artifact_type": QC_REPORT_ARTIFACT_TYPE,
            "schema_version": QC_REPORT_SCHEMA_VERSION,
            "report_id": report_id,
            "generated_at": generated_at,
            "task": dict(task),
            "documents": list(documents),
            "contributions": list(contributions),
            "findings": list(findings),
            "source_evidence": list(source_evidence),
            "source_annotations": list(source_annotations),
            "independent_review_record_refs": list(independent_review_record_refs),
            "integrity": dict(integrity),
        }
    )
    validate_qc_report(payload)
    return payload


def _detach_mapping(value: Any) -> Any:
    """Materialize accepted mappings/lists as detached JSON containers."""
    if isinstance(value, Mapping):
        return {key: _detach_mapping(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_detach_mapping(item) for item in value]
    return value


__all__ = [
    "QC_REPORT_ARTIFACT_TYPE",
    "QC_REPORT_SCHEMA_VERSION",
    "REPORT_INTEGRITY_STATUSES",
    "build_qc_report",
    "validate_qc_report",
]
