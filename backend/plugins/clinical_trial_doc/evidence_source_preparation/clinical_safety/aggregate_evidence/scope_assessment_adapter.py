# ruff: noqa: TRY004
"""Scope assessment evidence adapter for canonical ESP assess."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnnotationEvidenceView:
    """Minimal scope evidence payload for assess trace and adapter output."""

    candidate_text: str
    candidate_sentences: tuple[dict[str, Any], ...] = ()
    context_sentences: tuple[dict[str, Any], ...] = ()
    heading_path: tuple[str, ...] = ()
    source_sentence_ids: tuple[str, ...] = ()
    source_block_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScopeAssessmentEvidence:
    evidence_view: AnnotationEvidenceView
    source_unit_ids: tuple[str, ...]
    source_sentence_ids: tuple[str, ...]
    source_block_ids: tuple[str, ...]
    warnings: tuple[str, ...]


def _append_dedup(values: list[str], token: str) -> None:
    if token and token not in values:
        values.append(token)


def _heading_context_sentences(heading_path: list[str]) -> tuple[dict[str, Any], ...]:
    """Synthesize in-memory heading context for assess trace (not Route artifact shape)."""
    context_sentences: list[dict[str, Any]] = []
    cumulative_path: list[str] = []
    for heading in heading_path:
        cumulative_path.append(heading)
        context_sentences.append(
            {
                "kind": "heading",
                "text": heading,
                "heading_path": list(cumulative_path),
            }
        )
    return tuple(context_sentences)


def build_scope_assessment_evidence_view(
    *,
    scope: dict[str, Any],
    assessment_runtime_context: dict[str, Any],
) -> ScopeAssessmentEvidence:
    """Build deterministic scope evidence in heading/unit/sentence input order."""
    heading_path = [str(item) for item in (scope.get("heading_path") or [])]
    units = [
        unit
        for unit in (scope.get("units") or [])
        if isinstance(unit, dict) and str(unit.get("unit_id") or "").strip()
    ]
    provenance_map = assessment_runtime_context.get("unit_provenance") or {}
    if not isinstance(provenance_map, dict):
        provenance_map = {}

    source_unit_ids: list[str] = []
    source_sentence_ids: list[str] = []
    source_block_ids: list[str] = []
    warnings: list[str] = []
    evidence = scope.get("assessment_evidence")
    if not isinstance(evidence, dict):
        raise ValueError("heading scope assessment_evidence must be an object")
    candidate_text = evidence.get("candidate_text")
    if not isinstance(candidate_text, str) or not candidate_text.strip():
        raise ValueError(
            "heading scope assessment_evidence.candidate_text must be a non-empty string"
        )

    candidate_sentences: list[dict[str, Any]] = []

    for unit in units:
        unit_id = str(unit.get("unit_id") or "").strip()
        if not unit_id:
            continue
        _append_dedup(source_unit_ids, unit_id)
        unit_provenance = provenance_map.get(unit_id)
        if not isinstance(unit_provenance, dict):
            warnings.append(f"missing_unit_provenance:{unit_id}")
            unit_provenance = {}

        for sentence in unit.get("sentences") or []:
            if not isinstance(sentence, dict):
                continue
            sentence_id = str(sentence.get("sentence_id") or "").strip()
            text = str(sentence.get("text") or "")
            if sentence_id:
                _append_dedup(source_sentence_ids, sentence_id)
            candidate_sentences.append(
                {
                    "sentence_id": sentence_id or None,
                    "text": text,
                    "heading_path": heading_path,
                }
            )

        for block_id in unit_provenance.get("source_block_ids") or []:
            token = str(block_id or "").strip()
            _append_dedup(source_block_ids, token)

    evidence_view = AnnotationEvidenceView(
        candidate_text=candidate_text,
        candidate_sentences=tuple(candidate_sentences),
        context_sentences=_heading_context_sentences(heading_path),
        heading_path=tuple(heading_path),
        source_sentence_ids=tuple(source_sentence_ids),
        source_block_ids=tuple(source_block_ids),
    )
    return ScopeAssessmentEvidence(
        evidence_view=evidence_view,
        source_unit_ids=tuple(source_unit_ids),
        source_sentence_ids=tuple(source_sentence_ids),
        source_block_ids=tuple(source_block_ids),
        warnings=tuple(warnings),
    )
