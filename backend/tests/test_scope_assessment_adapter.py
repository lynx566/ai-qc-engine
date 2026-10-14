from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assessment_adapter import (
    build_scope_assessment_evidence_view,
)


def _scope_payload() -> dict:
    return {
        "scope_id": "HS0001",
        "heading_path": ["8", "8.1 已完成试验"],
        "assessment_evidence": {
            "candidate_text": "第三句\n第一句\n\n第二句\n第一句重复",
        },
        "units": [
            {
                "unit_id": "TU0002",
                "sentences": [
                    {"sentence_id": "C0010:S003", "text": "第三句"},
                    {"sentence_id": "C0020:S001", "text": "第一句"},
                ],
            },
            {
                "unit_id": "TU0001",
                "sentences": [
                    {"sentence_id": "C0010:S002", "text": "第二句"},
                    {"sentence_id": "C0010:S001", "text": "第一句重复"},
                ],
            },
        ],
    }


def _runtime_context() -> dict:
    return {
        "unit_provenance": {
            "TU0002": {"source_block_ids": ["C0010", "C0020"]},
            "TU0001": {"source_block_ids": ["C0010"]},
        }
    }


def test_scope_adapter_preserves_unit_and_sentence_order() -> None:
    result = build_scope_assessment_evidence_view(
        scope=_scope_payload(),
        assessment_runtime_context=_runtime_context(),
    )
    assert result.source_unit_ids == ("TU0002", "TU0001")
    assert result.source_sentence_ids == (
        "C0010:S003",
        "C0020:S001",
        "C0010:S002",
        "C0010:S001",
    )
    assert result.evidence_view.candidate_text == "第三句\n第一句\n\n第二句\n第一句重复"
    assert [s["sentence_id"] for s in result.evidence_view.candidate_sentences] == [
        "C0010:S003",
        "C0020:S001",
        "C0010:S002",
        "C0010:S001",
    ]


def test_scope_adapter_dedups_same_canonical_sentence_across_units() -> None:
    scope = {
        "scope_id": "HS0002",
        "heading_path": ["8"],
        "assessment_evidence": {"candidate_text": "共享句\n共享句"},
        "units": [
            {
                "unit_id": "TU0001",
                "sentences": [{"sentence_id": "C0004:S001", "text": "共享句"}],
            },
            {
                "unit_id": "TU0002",
                "sentences": [{"sentence_id": "C0004:S001", "text": "共享句"}],
            },
        ],
    }
    runtime = {
        "unit_provenance": {
            "TU0001": {"source_block_ids": ["C0004"]},
            "TU0002": {"source_block_ids": ["C0004"]},
        }
    }
    result = build_scope_assessment_evidence_view(
        scope=scope,
        assessment_runtime_context=runtime,
    )
    assert result.source_sentence_ids == ("C0004:S001",)
    assert [s["sentence_id"] for s in result.evidence_view.candidate_sentences] == [
        "C0004:S001",
        "C0004:S001",
    ]


def test_scope_adapter_does_not_collapse_distinct_canonical_sentences() -> None:
    """Distinct Extract sentences must not dedup even if Route would reuse S0001 locally."""

    scope = {
        "scope_id": "HS0003",
        "heading_path": ["8"],
        "assessment_evidence": {"candidate_text": "A\nB"},
        "units": [
            {
                "unit_id": "TU0001",
                "sentences": [{"sentence_id": "C0010:S001", "text": "A"}],
            },
            {
                "unit_id": "TU0002",
                "sentences": [{"sentence_id": "C0020:S001", "text": "B"}],
            },
        ],
    }
    runtime = {
        "unit_provenance": {
            "TU0001": {"source_block_ids": ["C0010"]},
            "TU0002": {"source_block_ids": ["C0020"]},
        }
    }
    result = build_scope_assessment_evidence_view(
        scope=scope,
        assessment_runtime_context=runtime,
    )
    assert result.source_sentence_ids == ("C0010:S001", "C0020:S001")


def test_scope_adapter_keeps_heading_in_context_not_candidate_text() -> None:
    result = build_scope_assessment_evidence_view(
        scope=_scope_payload(),
        assessment_runtime_context=_runtime_context(),
    )
    assert "8.1 已完成试验" not in result.evidence_view.candidate_text
    assert [item["text"] for item in result.evidence_view.context_sentences] == [
        "8",
        "8.1 已完成试验",
    ]


def test_scope_adapter_source_block_ids_aggregate_in_unit_order() -> None:
    result = build_scope_assessment_evidence_view(
        scope=_scope_payload(),
        assessment_runtime_context=_runtime_context(),
    )
    assert result.source_block_ids == ("C0010", "C0020")


def test_scope_adapter_missing_provenance_adds_warning_and_keeps_scope() -> None:
    runtime = {"unit_provenance": {"TU0002": {"source_block_ids": ["C0010"]}}}
    result = build_scope_assessment_evidence_view(
        scope=_scope_payload(),
        assessment_runtime_context=runtime,
    )
    assert result.source_unit_ids == ("TU0002", "TU0001")
    assert result.source_block_ids == ("C0010",)
    assert "missing_unit_provenance:TU0001" in result.warnings


def test_scope_adapter_requires_assessment_evidence_candidate_text() -> None:
    scope = _scope_payload()
    del scope["assessment_evidence"]
    with pytest.raises(ValueError, match="assessment_evidence"):
        build_scope_assessment_evidence_view(
            scope=scope,
            assessment_runtime_context=_runtime_context(),
        )


def test_scope_adapter_does_not_join_scope_candidate_text() -> None:
    module_path = (
        BACKEND_ROOT
        / "plugins"
        / "clinical_trial_doc"
        / "evidence_source_preparation"
        / "clinical_safety"
        / "aggregate_evidence"
        / "scope_assessment_adapter.py"
    )
    source = module_path.read_text(encoding="utf-8")
    assert '"\\n".join(sentence_texts)' not in source
    assert '"\\n".join(' not in source
    assert '"\\n\\n".join(' not in source


def test_scope_adapter_is_deterministic_for_same_input() -> None:
    one = build_scope_assessment_evidence_view(
        scope=_scope_payload(),
        assessment_runtime_context=_runtime_context(),
    )
    two = build_scope_assessment_evidence_view(
        scope=_scope_payload(),
        assessment_runtime_context=_runtime_context(),
    )
    assert one == two


def test_scope_adapter_does_not_import_legacy_or_rules_modules() -> None:
    module_path = (
        BACKEND_ROOT
        / "plugins"
        / "clinical_trial_doc"
        / "evidence_source_preparation"
        / "clinical_safety"
        / "aggregate_evidence"
        / "scope_assessment_adapter.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    forbidden_prefixes = (
        "core.tagging.annotation_semantic_rules",
        "core.tagging.semantic_postprocess",
        "core.tagging.taggers.evidence_resolver",
        "artifacts.evidence_source_preparation.aggregate_annotations",
        "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assess",
        "core.match",
        "scripts.stage_runners",
        "core.run_layout",
    )
    for name in imported:
        assert not any(name == prefix or name.startswith(f"{prefix}.") for prefix in forbidden_prefixes), name
