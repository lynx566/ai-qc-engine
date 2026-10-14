"""Canonical Aggregate Evidence Comparison materialization tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
    validate_aggregate_comparison_evidence,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    COMPARISON_ALIAS_MAX_INDEX,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_evidence import (
    materialize_aggregate_comparison_evidence,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_adapter import (
    build_aggregate_evidence_comparison_invocation,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceComparisonParticipantEvidence,
    AggregateEvidenceComparisonScope,
    AggregateEvidenceComparisonSentence,
    AggregateEvidenceComparisonSourceProvenance,
    AggregateEvidenceComparisonUnit,
)


def _sentence(*, source_sentence_id: str, text: str):
    return AggregateEvidenceComparisonSentence(
        source_sentence_id=source_sentence_id,
        text=text,
    )


def _unit(*, source_unit_id: str, sentences: tuple):
    return AggregateEvidenceComparisonUnit(
        source_unit_id=source_unit_id,
        sentences=sentences,
    )


def _scope(
    *,
    source_scope_id: str,
    units: tuple,
    semantic_path: tuple[str, ...] | None = None,
):
    return AggregateEvidenceComparisonScope(
        source_scope_id=source_scope_id,
        semantic_path=(
            semantic_path
            if semantic_path is not None
            else (f"Heading {source_scope_id}",)
        ),
        units=units,
    )


def _evidence(*, label: str, scopes: tuple):
    return AggregateEvidenceComparisonParticipantEvidence(
        source_provenance=AggregateEvidenceComparisonSourceProvenance(
            source_artifact_id=f"bundle_{label}",
            doc_id=f"doc_{label}",
            file_hash=f"sha256:{label}",
        ),
        scopes=scopes,
    )


def _materialize(*role_bound_evidence: tuple[str, object]) -> dict:
    invocation = build_aggregate_evidence_comparison_invocation(
        participants=role_bound_evidence
    )
    return materialize_aggregate_comparison_evidence(invocation=invocation)


def _evidence_with_layout(
    *,
    label: str,
    units_per_scope: list[int],
    sentences_per_unit: list[int],
):
    scopes: list[AggregateEvidenceComparisonScope] = []
    unit_offset = 0
    sentence_offset = 0
    for scope_index, unit_count in enumerate(units_per_scope):
        units: list[AggregateEvidenceComparisonUnit] = []
        for _ in range(unit_count):
            sentence_count = sentences_per_unit[unit_offset]
            sentences = tuple(
                _sentence(
                    source_sentence_id=(f"C{unit_offset + 1:04d}:S{index + 1:03d}"),
                    text=f"sentence {sentence_offset + index + 1}",
                )
                for index in range(sentence_count)
            )
            units.append(
                _unit(
                    source_unit_id=f"TU{unit_offset + 1:04d}",
                    sentences=sentences,
                )
            )
            unit_offset += 1
            sentence_offset += sentence_count
        scopes.append(
            _scope(
                source_scope_id=f"HS{scope_index + 1:04d}",
                units=tuple(units),
            )
        )
    return _evidence(label=label, scopes=tuple(scopes))


def test_materializes_canonical_fields_in_declared_collection_order() -> None:
    evidence = _evidence(
        label="subject",
        scopes=(
            _scope(
                source_scope_id="HS0008",
                semantic_path=("First retained scope",),
                units=(
                    _unit(
                        source_unit_id="TU0023",
                        sentences=(
                            _sentence(
                                source_sentence_id="C0088:S002",
                                text="first sentence",
                            ),
                            _sentence(
                                source_sentence_id="C0015:S001",
                                text="second sentence",
                            ),
                        ),
                    ),
                    _unit(
                        source_unit_id="TU0005",
                        sentences=(
                            _sentence(
                                source_sentence_id="C0099:S004",
                                text="third sentence",
                            ),
                        ),
                    ),
                ),
            ),
            _scope(
                source_scope_id="HS0002",
                semantic_path=("Second retained scope",),
                units=(
                    _unit(
                        source_unit_id="TU0100",
                        sentences=(
                            _sentence(
                                source_sentence_id="C0001:S009",
                                text="fourth sentence",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    artifact = _materialize(("subject", evidence))

    participant = artifact["participants"][0]
    assert participant["role_id"] == "subject"
    assert participant["aggregate_evidence_source_bundle_id"] == "bundle_subject"
    assert participant["doc_id"] == "doc_subject"
    assert participant["file_hash"] == "sha256:subject"
    assert [scope["scope_id"] for scope in participant["scopes"]] == [
        "HS0008",
        "HS0002",
    ]
    assert [scope["scope_alias"] for scope in participant["scopes"]] == [
        "H0001",
        "H0002",
    ]
    assert [
        unit["unit_alias"] for scope in participant["scopes"] for unit in scope["units"]
    ] == ["U0001", "U0002", "U0003"]
    assert [
        sentence["sentence_alias"]
        for scope in participant["scopes"]
        for unit in scope["units"]
        for sentence in unit["sentences"]
    ] == ["T0001", "T0002", "T0003", "T0004"]
    assert participant["scopes"][0]["heading_path"] == ["First retained scope"]
    assert participant["scopes"][0]["units"][0]["sentences"][0] == {
        "sentence_id": "C0088:S002",
        "sentence_alias": "T0001",
        "text": "first sentence",
    }
    validate_aggregate_comparison_evidence(artifact)


def test_aliases_continue_across_participants_without_reset() -> None:
    first = _evidence_with_layout(
        label="subject",
        units_per_scope=[3, 2, 2],
        sentences_per_unit=[3, 3, 3, 3, 3, 3, 2],
    )
    second = _evidence_with_layout(
        label="reference",
        units_per_scope=[1],
        sentences_per_unit=[1],
    )

    artifact = _materialize(("subject", first), ("reference", second))

    first_scopes = artifact["participants"][0]["scopes"]
    second_scope = artifact["participants"][1]["scopes"][0]
    assert first_scopes[-1]["scope_alias"] == "H0003"
    assert first_scopes[-1]["units"][-1]["unit_alias"] == "U0007"
    assert first_scopes[-1]["units"][-1]["sentences"][-1]["sentence_alias"] == "T0020"
    assert second_scope["scope_alias"] == "H0004"
    assert second_scope["units"][0]["unit_alias"] == "U0008"
    assert second_scope["units"][0]["sentences"][0]["sentence_alias"] == ("T0021")


def test_projects_only_unchanged_formal_artifact_fields() -> None:
    evidence = _evidence_with_layout(
        label="subject",
        units_per_scope=[1],
        sentences_per_unit=[1],
    )

    artifact = _materialize(("subject", evidence))

    participant = artifact["participants"][0]
    scope = participant["scopes"][0]
    unit = scope["units"][0]
    sentence = unit["sentences"][0]
    assert set(participant) == {
        "role_id",
        "aggregate_evidence_source_bundle_id",
        "doc_id",
        "file_hash",
        "scopes",
    }
    assert set(scope) == {"scope_id", "scope_alias", "heading_path", "units"}
    assert set(unit) == {"unit_id", "unit_alias", "sentences"}
    assert set(sentence) == {"sentence_id", "sentence_alias", "text"}


def test_materialization_is_deterministic_and_formally_valid() -> None:
    evidence = _evidence_with_layout(
        label="subject",
        units_per_scope=[1],
        sentences_per_unit=[2],
    )
    invocation = build_aggregate_evidence_comparison_invocation(
        participants=(("subject", evidence),)
    )

    first = materialize_aggregate_comparison_evidence(invocation=invocation)
    second = materialize_aggregate_comparison_evidence(invocation=invocation)

    assert first == second
    validate_aggregate_comparison_evidence(first)


def test_materialization_fails_when_alias_index_exceeds_contract_limit() -> None:
    evidence = _evidence_with_layout(
        label="subject",
        units_per_scope=[1],
        sentences_per_unit=[COMPARISON_ALIAS_MAX_INDEX + 1],
    )

    with pytest.raises(ValueError, match="exceeds maximum"):
        _materialize(("subject", evidence))
