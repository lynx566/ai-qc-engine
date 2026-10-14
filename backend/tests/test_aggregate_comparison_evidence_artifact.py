"""Formal Aggregate Comparison evidence artifact contract tests."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_comparison_evidence import (
    AGGREGATE_COMPARISON_EVIDENCE_ARTIFACT_TYPE,
    AGGREGATE_COMPARISON_EVIDENCE_FILENAME,
    AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION,
    build_aggregate_comparison_evidence,
    validate_aggregate_comparison_evidence,
)


def _sentence(
    *,
    sentence_id: str = "S0001",
    sentence_alias: str = "T0001",
) -> dict:
    return {
        "sentence_id": sentence_id,
        "sentence_alias": sentence_alias,
        "text": f"text for {sentence_alias}",
    }


def _unit(
    *,
    unit_id: str = "TU0001",
    unit_alias: str = "U0001",
    sentences: list[dict] | None = None,
) -> dict:
    return {
        "unit_id": unit_id,
        "unit_alias": unit_alias,
        "sentences": sentences if sentences is not None else [_sentence()],
    }


def _scope(
    *,
    scope_id: str = "HS0001",
    scope_alias: str = "H0001",
    units: list[dict] | None = None,
) -> dict:
    return {
        "scope_id": scope_id,
        "scope_alias": scope_alias,
        "heading_path": ["Evidence"],
        "units": units if units is not None else [_unit()],
    }


def _participant(
    *,
    role_id: str = "subject",
    scopes: list[dict] | None = None,
) -> dict:
    return {
        "role_id": role_id,
        "aggregate_evidence_source_bundle_id": f"bundle_{role_id}",
        "doc_id": f"doc_{role_id}",
        "file_hash": f"sha256:{role_id}",
        "scopes": scopes if scopes is not None else [_scope()],
    }


def _participant_with_layout(
    *,
    role_id: str,
    scope_alias_start: int,
    unit_alias_start: int,
    sentence_alias_start: int,
    units_per_scope: list[int],
    sentences_per_unit: list[int],
) -> dict:
    scopes: list[dict] = []
    unit_offset = 0
    sentence_offset = 0
    for scope_index, unit_count in enumerate(units_per_scope):
        units: list[dict] = []
        for _ in range(unit_count):
            sentence_count = sentences_per_unit[unit_offset]
            sentences = [
                _sentence(
                    sentence_id=f"S{sentence_offset + index + 1:04d}",
                    sentence_alias=(
                        f"T{sentence_alias_start + sentence_offset + index:04d}"
                    ),
                )
                for index in range(sentence_count)
            ]
            units.append(
                _unit(
                    unit_id=f"TU{unit_offset + 1:04d}",
                    unit_alias=f"U{unit_alias_start + unit_offset:04d}",
                    sentences=sentences,
                )
            )
            unit_offset += 1
            sentence_offset += sentence_count
        scopes.append(
            _scope(
                scope_id=f"HS{scope_index + 1:04d}",
                scope_alias=f"H{scope_alias_start + scope_index:04d}",
                units=units,
            )
        )
    return _participant(role_id=role_id, scopes=scopes)


def _minimal_artifact() -> dict:
    return build_aggregate_comparison_evidence(participants=[_participant()])


def _target(payload: dict, path: tuple[str | int, ...]) -> dict:
    current: object = payload
    for segment in path:
        current = current[segment]  # type: ignore[index]
    assert isinstance(current, dict)
    return current


def test_builder_emits_exact_minimal_formal_shape() -> None:
    artifact = _minimal_artifact()

    assert artifact["artifact_type"] == AGGREGATE_COMPARISON_EVIDENCE_ARTIFACT_TYPE
    assert artifact["schema_version"] == AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION
    assert AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION == "0.1.0"
    assert AGGREGATE_COMPARISON_EVIDENCE_FILENAME == (
        "aggregate_comparison_evidence.json"
    )
    assert set(artifact) == {"artifact_type", "schema_version", "participants"}
    participant = artifact["participants"][0]
    assert set(participant) == {
        "role_id",
        "aggregate_evidence_source_bundle_id",
        "doc_id",
        "file_hash",
        "scopes",
    }
    scope = participant["scopes"][0]
    assert set(scope) == {
        "scope_id",
        "scope_alias",
        "heading_path",
        "units",
    }
    unit = scope["units"][0]
    assert set(unit) == {"unit_id", "unit_alias", "sentences"}
    sentence = unit["sentences"][0]
    assert set(sentence) == {
        "sentence_id",
        "sentence_alias",
        "text",
    }
    assert (scope["scope_id"], scope["scope_alias"]) == ("HS0001", "H0001")
    assert (unit["unit_id"], unit["unit_alias"]) == ("TU0001", "U0001")
    assert (sentence["sentence_id"], sentence["sentence_alias"]) == (
        "S0001",
        "T0001",
    )


def test_aliases_continue_across_participant_boundary() -> None:
    first = _participant_with_layout(
        role_id="subject",
        scope_alias_start=1,
        unit_alias_start=1,
        sentence_alias_start=1,
        units_per_scope=[3, 2, 2],
        sentences_per_unit=[3, 3, 3, 3, 3, 3, 2],
    )
    second = _participant_with_layout(
        role_id="reference",
        scope_alias_start=4,
        unit_alias_start=8,
        sentence_alias_start=21,
        units_per_scope=[1],
        sentences_per_unit=[1],
    )

    artifact = build_aggregate_comparison_evidence(participants=[first, second])

    first_scopes = artifact["participants"][0]["scopes"]
    second_scope = artifact["participants"][1]["scopes"][0]
    assert first_scopes[-1]["scope_alias"] == "H0003"
    assert first_scopes[-1]["units"][-1]["unit_alias"] == "U0007"
    assert (
        first_scopes[-1]["units"][-1]["sentences"][-1]["sentence_alias"]
        == "T0020"
    )
    assert second_scope["scope_alias"] == "H0004"
    assert second_scope["units"][0]["unit_alias"] == "U0008"
    assert second_scope["units"][0]["sentences"][0]["sentence_alias"] == (
        "T0021"
    )
@pytest.mark.parametrize(
    ("path", "field", "invalid_value", "message"),
    [
        (("participants", 0, "scopes", 0), "scope_alias", "H1", "scope_alias"),
        (
            ("participants", 0, "scopes", 0, "units", 0),
            "unit_alias",
            "U00001",
            "unit_alias",
        ),
        (
            ("participants", 0, "scopes", 0, "units", 0, "sentences", 0),
            "sentence_alias",
            "X000001",
            "sentence_alias",
        ),
    ],
)
def test_rejects_invalid_alias_format(
    path: tuple[str | int, ...],
    field: str,
    invalid_value: str,
    message: str,
) -> None:
    artifact = _minimal_artifact()
    _target(artifact, path)[field] = invalid_value

    with pytest.raises(ValueError, match=message):
        validate_aggregate_comparison_evidence(artifact)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("scope_alias", "H0002"),
        ("unit_alias", "U0002"),
        ("sentence_alias", "T0002"),
    ],
)
def test_rejects_alias_gap_at_first_coordinate(
    field: str,
    replacement: str,
) -> None:
    artifact = _minimal_artifact()
    scope = artifact["participants"][0]["scopes"][0]
    targets = {
        "scope_alias": scope,
        "unit_alias": scope["units"][0],
        "sentence_alias": scope["units"][0]["sentences"][0],
    }
    targets[field][field] = replacement

    with pytest.raises(ValueError, match="must be"):
        validate_aggregate_comparison_evidence(artifact)


def test_rejects_alias_reset_across_participants() -> None:
    artifact = _minimal_artifact()
    second = copy.deepcopy(artifact["participants"][0])
    second["role_id"] = "reference"
    second["aggregate_evidence_source_bundle_id"] = "bundle_reference"
    second["doc_id"] = "doc_reference"
    artifact["participants"].append(second)

    with pytest.raises(ValueError, match="scope_alias"):
        validate_aggregate_comparison_evidence(artifact)


@pytest.mark.parametrize(
    ("path", "unexpected_key"),
    [
        (("participants", 0), "slot_id"),
        (("participants", 0), "semantic_module_id"),
        (("participants", 0), "declared_output_path"),
        (("participants", 0), "document_type"),
        (("participants", 0, "scopes", 0), "scope_order"),
        (("participants", 0, "scopes", 0, "units", 0), "unit_order"),
        (
            ("participants", 0, "scopes", 0, "units", 0, "sentences", 0),
            "sentence_order",
        ),
        (("participants", 0, "scopes", 0, "units", 0), "text"),
        (("participants", 0, "scopes", 0, "units", 0), "source"),
        (
            ("participants", 0, "scopes", 0, "units", 0, "sentences", 0),
            "source_block_ids",
        ),
    ],
)
def test_rejects_transport_and_upstream_only_fields(
    path: tuple[str | int, ...],
    unexpected_key: str,
) -> None:
    artifact = _minimal_artifact()
    _target(artifact, path)[unexpected_key] = "unexpected"

    with pytest.raises(ValueError, match="keys mismatch"):
        validate_aggregate_comparison_evidence(artifact)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        (("participants", 0), "doc_id"),
        (("participants", 0, "scopes", 0), "scope_id"),
        (("participants", 0, "scopes", 0, "units", 0), "unit_id"),
        (
            ("participants", 0, "scopes", 0, "units", 0, "sentences", 0),
            "sentence_id",
        ),
        (
            ("participants", 0, "scopes", 0, "units", 0, "sentences", 0),
            "text",
        ),
    ],
)
def test_rejects_empty_required_identity_or_text(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    artifact = _minimal_artifact()
    _target(artifact, path)[field] = ""

    with pytest.raises(ValueError, match=field):
        validate_aggregate_comparison_evidence(artifact)


def test_rejects_duplicate_participant_role() -> None:
    artifact = _minimal_artifact()
    artifact["participants"].append(copy.deepcopy(artifact["participants"][0]))

    with pytest.raises(ValueError, match="duplicate participant role_id"):
        validate_aggregate_comparison_evidence(artifact)


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ((), "participants"),
        (("participants", 0), "scopes"),
        (("participants", 0, "scopes", 0), "units"),
        (("participants", 0, "scopes", 0, "units", 0), "sentences"),
    ],
)
def test_rejects_empty_required_collection(
    path: tuple[str | int, ...],
    field: str,
) -> None:
    artifact = _minimal_artifact()
    _target(artifact, path)[field] = []

    with pytest.raises(ValueError, match=field):
        validate_aggregate_comparison_evidence(artifact)
