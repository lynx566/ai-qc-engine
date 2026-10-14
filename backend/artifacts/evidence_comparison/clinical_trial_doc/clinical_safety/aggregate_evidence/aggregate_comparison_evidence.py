"""Formal aggregate_comparison_evidence artifact contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    _ALIAS_PATTERNS,
    _ALIAS_PREFIXES,
    comparison_alias_format_description,
    format_comparison_alias,
)

AGGREGATE_COMPARISON_EVIDENCE_FILENAME = "aggregate_comparison_evidence.json"
AGGREGATE_COMPARISON_EVIDENCE_ARTIFACT_TYPE = "aggregate_comparison_evidence"
AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION = "0.1.0"

_ROOT_KEYS = frozenset({"artifact_type", "schema_version", "participants"})
_PARTICIPANT_KEYS = frozenset(
    {
        "role_id",
        "aggregate_evidence_source_bundle_id",
        "doc_id",
        "file_hash",
        "scopes",
    }
)
_SCOPE_KEYS = frozenset({"scope_id", "scope_alias", "heading_path", "units"})
_UNIT_KEYS = frozenset({"unit_id", "unit_alias", "sentences"})
_SENTENCE_KEYS = frozenset({"sentence_id", "sentence_alias", "text"})


def _require_exact_keys(
    value: Mapping[str, Any],
    *,
    expected: frozenset[str],
    path: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{path} keys mismatch; missing={missing!r}, unknown={unknown!r}"
        )


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_non_empty_list(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    return value


def _validate_alias(
    value: Any,
    *,
    field: str,
    expected_number: int,
    seen: set[str],
) -> str:
    alias = _require_non_empty_str(value, field=field)
    if _ALIAS_PATTERNS[field].fullmatch(alias) is None:
        raise ValueError(
            f"{field} must match "
            f"{comparison_alias_format_description(prefix=_ALIAS_PREFIXES[field])}"
        )
    if alias in seen:
        raise ValueError(f"duplicate {field} {alias!r}")
    expected = format_comparison_alias(
        prefix=_ALIAS_PREFIXES[field],
        index=expected_number,
    )
    if alias != expected:
        raise ValueError(f"{field} must be {expected!r}, got {alias!r}")
    seen.add(alias)
    return alias


def validate_aggregate_comparison_evidence(payload: Mapping[str, Any]) -> None:
    """Validate one formal aggregate_comparison_evidence envelope."""

    if not isinstance(payload, Mapping):
        raise TypeError("aggregate_comparison_evidence must be an object")
    _require_exact_keys(payload, expected=_ROOT_KEYS, path="root")

    if payload.get("artifact_type") != AGGREGATE_COMPARISON_EVIDENCE_ARTIFACT_TYPE:
        raise ValueError(
            f"artifact_type must be {AGGREGATE_COMPARISON_EVIDENCE_ARTIFACT_TYPE!r}"
        )
    if payload.get("schema_version") != AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION!r}"
        )

    participants = _require_non_empty_list(
        payload.get("participants"),
        field="participants",
    )
    seen_roles: set[str] = set()
    seen_scope_aliases: set[str] = set()
    seen_unit_aliases: set[str] = set()
    seen_sentence_aliases: set[str] = set()
    next_scope_alias = 1
    next_unit_alias = 1
    next_sentence_alias = 1

    for participant_index, participant in enumerate(participants):
        participant_path = f"participants[{participant_index}]"
        if not isinstance(participant, Mapping):
            raise TypeError(f"{participant_path} must be an object")
        _require_exact_keys(
            participant,
            expected=_PARTICIPANT_KEYS,
            path=participant_path,
        )
        role_id = _require_non_empty_str(
            participant.get("role_id"),
            field=f"{participant_path}.role_id",
        )
        if role_id in seen_roles:
            raise ValueError(f"duplicate participant role_id={role_id!r}")
        seen_roles.add(role_id)
        for field in (
            "aggregate_evidence_source_bundle_id",
            "doc_id",
            "file_hash",
        ):
            _require_non_empty_str(
                participant.get(field),
                field=f"{participant_path}.{field}",
            )

        scopes = _require_non_empty_list(
            participant.get("scopes"),
            field=f"{participant_path}.scopes",
        )
        seen_scope_ids: set[str] = set()
        for scope_index, scope in enumerate(scopes):
            scope_path = f"{participant_path}.scopes[{scope_index}]"
            if not isinstance(scope, Mapping):
                raise TypeError(f"{scope_path} must be an object")
            _require_exact_keys(scope, expected=_SCOPE_KEYS, path=scope_path)
            scope_id = _require_non_empty_str(
                scope.get("scope_id"),
                field=f"{scope_path}.scope_id",
            )
            if scope_id in seen_scope_ids:
                raise ValueError(
                    f"duplicate scope_id {scope_id!r} in participant {role_id!r}"
                )
            seen_scope_ids.add(scope_id)
            _validate_alias(
                scope.get("scope_alias"),
                field="scope_alias",
                expected_number=next_scope_alias,
                seen=seen_scope_aliases,
            )
            next_scope_alias += 1

            heading_path = scope.get("heading_path")
            if not isinstance(heading_path, list) or not all(
                isinstance(item, str) for item in heading_path
            ):
                raise ValueError(f"{scope_path}.heading_path must be a string list")
            units = _require_non_empty_list(
                scope.get("units"),
                field=f"{scope_path}.units",
            )
            seen_unit_ids: set[str] = set()
            for unit_index, unit in enumerate(units):
                unit_path = f"{scope_path}.units[{unit_index}]"
                if not isinstance(unit, Mapping):
                    raise TypeError(f"{unit_path} must be an object")
                _require_exact_keys(unit, expected=_UNIT_KEYS, path=unit_path)
                unit_id = _require_non_empty_str(
                    unit.get("unit_id"),
                    field=f"{unit_path}.unit_id",
                )
                if unit_id in seen_unit_ids:
                    raise ValueError(
                        f"duplicate unit_id {unit_id!r} in scope {scope_id!r}"
                    )
                seen_unit_ids.add(unit_id)
                _validate_alias(
                    unit.get("unit_alias"),
                    field="unit_alias",
                    expected_number=next_unit_alias,
                    seen=seen_unit_aliases,
                )
                next_unit_alias += 1

                sentences = _require_non_empty_list(
                    unit.get("sentences"),
                    field=f"{unit_path}.sentences",
                )
                seen_sentence_ids: set[str] = set()
                for sentence_index, sentence in enumerate(sentences):
                    sentence_path = f"{unit_path}.sentences[{sentence_index}]"
                    if not isinstance(sentence, Mapping):
                        raise TypeError(f"{sentence_path} must be an object")
                    _require_exact_keys(
                        sentence,
                        expected=_SENTENCE_KEYS,
                        path=sentence_path,
                    )
                    sentence_id = _require_non_empty_str(
                        sentence.get("sentence_id"),
                        field=f"{sentence_path}.sentence_id",
                    )
                    if sentence_id in seen_sentence_ids:
                        raise ValueError(
                            f"duplicate sentence_id {sentence_id!r} in unit {unit_id!r}"
                        )
                    seen_sentence_ids.add(sentence_id)
                    _validate_alias(
                        sentence.get("sentence_alias"),
                        field="sentence_alias",
                        expected_number=next_sentence_alias,
                        seen=seen_sentence_aliases,
                    )
                    next_sentence_alias += 1
                    _require_non_empty_str(
                        sentence.get("text"),
                        field=f"{sentence_path}.text",
                    )


def build_aggregate_comparison_evidence(
    *,
    participants: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate an envelope from already aliased participants."""

    envelope: dict[str, Any] = {
        "artifact_type": AGGREGATE_COMPARISON_EVIDENCE_ARTIFACT_TYPE,
        "schema_version": AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION,
        "participants": [dict(participant) for participant in participants],
    }
    validate_aggregate_comparison_evidence(envelope)
    return envelope


__all__ = [
    "AGGREGATE_COMPARISON_EVIDENCE_ARTIFACT_TYPE",
    "AGGREGATE_COMPARISON_EVIDENCE_FILENAME",
    "AGGREGATE_COMPARISON_EVIDENCE_SCHEMA_VERSION",
    "build_aggregate_comparison_evidence",
    "validate_aggregate_comparison_evidence",
]
