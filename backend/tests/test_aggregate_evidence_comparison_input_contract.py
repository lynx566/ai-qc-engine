"""Canonical Aggregate Evidence Comparison in-memory input tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence import input_types as contracts


def _sentence(source_sentence_id: str = "S-1", text: str = "sentence"):
    return contracts.AggregateEvidenceComparisonSentence(
        source_sentence_id=source_sentence_id,
        text=text,
    )


def _unit(
    source_unit_id: str = "U-1",
    sentences: tuple | None = None,
):
    return contracts.AggregateEvidenceComparisonUnit(
        source_unit_id=source_unit_id,
        sentences=sentences if sentences is not None else (_sentence(),),
    )


def _scope(
    source_scope_id: str = "H-1",
    semantic_path: tuple[str, ...] = ("Safety",),
    units: tuple | None = None,
):
    return contracts.AggregateEvidenceComparisonScope(
        source_scope_id=source_scope_id,
        semantic_path=semantic_path,
        units=units if units is not None else (_unit(),),
    )


def _evidence(scopes: tuple | None = None):
    return contracts.AggregateEvidenceComparisonParticipantEvidence(
        source_provenance=contracts.AggregateEvidenceComparisonSourceProvenance(
            source_artifact_id="bundle-1",
            doc_id="doc-1",
            file_hash="sha256:1",
        ),
        scopes=scopes if scopes is not None else (_scope(),),
    )


def test_role_binding_builds_the_only_canonical_invocation_shape() -> None:
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_adapter import (
        build_aggregate_evidence_comparison_invocation,
    )

    first = _evidence()
    second = _evidence(scopes=(_scope(source_scope_id="H-2"),))

    invocation = build_aggregate_evidence_comparison_invocation(
        participants=(("subject", first), ("reference", second))
    )

    assert tuple(item.role_id for item in invocation.participants) == (
        "subject",
        "reference",
    )
    assert invocation.participants[0].source_provenance is first.source_provenance
    assert invocation.participants[0].scopes is first.scopes
    assert tuple(invocation.participants[0].__dataclass_fields__) == (
        "role_id",
        "source_provenance",
        "scopes",
    )
    assert not hasattr(invocation.participants[0], "source_bundle")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_artifact_id", ""),
        ("doc_id", " "),
        ("file_hash", ""),
    ],
)
def test_source_provenance_rejects_empty_identity_fields(
    field: str,
    value: str,
) -> None:
    values = {
        "source_artifact_id": "bundle-1",
        "doc_id": "doc-1",
        "file_hash": "sha256:1",
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        contracts.AggregateEvidenceComparisonSourceProvenance(**values)


def test_canonical_hierarchy_rejects_empty_collections_and_text() -> None:
    with pytest.raises(ValueError, match="text"):
        _sentence(text=" ")
    with pytest.raises(ValueError, match="sentences"):
        _unit(sentences=())
    with pytest.raises(ValueError, match="semantic_path"):
        _scope(semantic_path=())
    with pytest.raises(ValueError, match="units"):
        _scope(units=())
    with pytest.raises(ValueError, match="scopes"):
        _evidence(scopes=())


def test_canonical_hierarchy_rejects_empty_source_ids_and_role() -> None:
    with pytest.raises(ValueError, match="source_sentence_id"):
        _sentence(source_sentence_id="")
    with pytest.raises(ValueError, match="source_unit_id"):
        _unit(source_unit_id=" ")
    with pytest.raises(ValueError, match="source_scope_id"):
        _scope(source_scope_id="")
    with pytest.raises(ValueError, match="role_id"):
        contracts.AggregateEvidenceComparisonParticipant(
            role_id=" ",
            source_provenance=_evidence().source_provenance,
            scopes=_evidence().scopes,
        )


def test_canonical_hierarchy_rejects_duplicate_local_source_ids() -> None:
    duplicate_sentences = (_sentence("S-1"), _sentence("S-1", "other"))
    with pytest.raises(ValueError, match="duplicate source_sentence_id"):
        _unit(sentences=duplicate_sentences)

    duplicate_units = (_unit("U-1"), _unit("U-1"))
    with pytest.raises(ValueError, match="duplicate source_unit_id"):
        _scope(units=duplicate_units)

    duplicate_scopes = (_scope("H-1"), _scope("H-1"))
    with pytest.raises(ValueError, match="duplicate source_scope_id"):
        _evidence(scopes=duplicate_scopes)


def test_invocation_rejects_empty_and_duplicate_participant_roles() -> None:
    participant = contracts.AggregateEvidenceComparisonParticipant(
        role_id="subject",
        source_provenance=_evidence().source_provenance,
        scopes=_evidence().scopes,
    )

    with pytest.raises(ValueError, match="participants"):
        contracts.AggregateEvidenceComparisonInvocation(participants=())
    with pytest.raises(ValueError, match="duplicate participant role_id"):
        contracts.AggregateEvidenceComparisonInvocation(
            participants=(participant, participant)
        )
