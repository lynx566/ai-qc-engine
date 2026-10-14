"""Structural response-contract validation for Finding Verification responses."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    SENTENCE_ALIAS_PATTERN,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDING_ID_PATTERN,
)

from ..response_json_repair import repair_unescaped_quotes_in_string_fields

ComparisonFindingVerificationLabel = Literal["fail", "need_review"]
VerificationResult = Literal["confirmed", "revised", "rejected"]

_VERIFICATION_RESULTS = frozenset({"confirmed", "revised", "rejected"})
_FINDING_LABELS = frozenset({"fail", "need_review"})
_TERMINAL_ENTRY_KEYS = frozenset({"finding_id", "verification_result"})
_REVISED_ENTRY_KEYS = frozenset(
    {
        "finding_id",
        "verification_result",
        "conclusion",
        "label",
        "source_sentence_aliases",
    }
)
_ADDITIONAL_FINDING_KEYS = frozenset(
    {"conclusion", "label", "source_sentence_aliases"},
)


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationConfirmedEntry:
    finding_id: str
    verification_result: Literal["confirmed"]


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationRevisedEntry:
    finding_id: str
    verification_result: Literal["revised"]
    conclusion: str
    label: ComparisonFindingVerificationLabel
    source_sentence_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationRejectedEntry:
    finding_id: str
    verification_result: Literal["rejected"]


ComparisonFindingVerificationEntry = (
    ComparisonFindingVerificationConfirmedEntry
    | ComparisonFindingVerificationRevisedEntry
    | ComparisonFindingVerificationRejectedEntry
)


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationAdditionalFinding:
    conclusion: str
    label: ComparisonFindingVerificationLabel
    source_sentence_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComparisonFindingVerificationValidatedResponse:
    finding_verifications: tuple[ComparisonFindingVerificationEntry, ...]
    additional_findings: tuple[ComparisonFindingVerificationAdditionalFinding, ...]


def _extract_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            opening = lines[0].strip()
            closing = lines[-1].strip()
            if opening in {"```", "```json", "```JSON"} and closing == "```":
                return "\n".join(lines[1:-1]).strip()
    return text


def parse_comparison_finding_verification_response(raw_text: str) -> dict[str, Any]:
    """Parse raw provider text into a JSON object."""

    json_text = _extract_json_text(raw_text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        repaired_json_text = repair_unescaped_quotes_in_string_fields(
            json_text,
            allowed_field_names=frozenset({"conclusion"}),
        )
        try:
            payload = json.loads(repaired_json_text)
        except json.JSONDecodeError:
            raise ValueError(f"response is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("response must be a JSON object")
    return payload


def _validate_sentence_alias(alias: str, *, context: str) -> str:
    if not isinstance(alias, str) or not SENTENCE_ALIAS_PATTERN.fullmatch(alias):
        raise ValueError(f"{context} must match Tdddd format: {alias!r}")
    return alias


def _validate_finding_id(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or FINDING_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{context} must match Lddd format: {value!r}")
    return value


def _validate_finding_label(
    value: Any,
    *,
    context: str,
) -> ComparisonFindingVerificationLabel:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    normalized = value.strip()
    if normalized not in _FINDING_LABELS:
        choices = ", ".join(sorted(_FINDING_LABELS))
        raise ValueError(f"{context} must be one of: {choices}; got {normalized!r}")
    return normalized  # type: ignore[return-value]


def _validate_finding_id_coverage(
    response_finding_ids: Sequence[str],
    input_finding_ids: Sequence[str],
) -> None:
    if Counter(response_finding_ids) != Counter(input_finding_ids):
        raise ValueError(
            "finding_verifications[].finding_id must cover each input finding "
            "exactly once"
        )


def _validate_finding_verification_entry(
    entry: Mapping[str, Any],
    *,
    index: int,
) -> ComparisonFindingVerificationEntry:
    if not isinstance(entry, dict):
        raise ValueError(f"finding_verifications[{index}] must be an object")

    verification_result = entry.get("verification_result")
    if (
        not isinstance(verification_result, str)
        or verification_result not in _VERIFICATION_RESULTS
    ):
        choices = ", ".join(sorted(_VERIFICATION_RESULTS))
        raise ValueError(
            f"finding_verifications[{index}].verification_result must be one of: "
            f"{choices}; got {verification_result!r}"
        )

    finding_id = _validate_finding_id(
        entry.get("finding_id"),
        context=f"finding_verifications[{index}].finding_id",
    )

    if verification_result in {"confirmed", "rejected"}:
        if set(entry) != _TERMINAL_ENTRY_KEYS:
            raise ValueError(
                f"finding_verifications[{index}] with "
                f"verification_result={verification_result!r} "
                "must contain exactly finding_id and verification_result"
            )
        if verification_result == "confirmed":
            return ComparisonFindingVerificationConfirmedEntry(
                finding_id=finding_id,
                verification_result="confirmed",
            )
        return ComparisonFindingVerificationRejectedEntry(
            finding_id=finding_id,
            verification_result="rejected",
        )

    if set(entry) != _REVISED_ENTRY_KEYS:
        raise ValueError(
            f"finding_verifications[{index}] with verification_result='revised' "
            "must contain exactly finding_id, verification_result, conclusion, label, "
            "and source_sentence_aliases"
        )
    conclusion = entry["conclusion"]
    if not isinstance(conclusion, str) or not conclusion.strip():
        raise ValueError(
            f"finding_verifications[{index}].conclusion must be a non-empty string"
        )
    label = _validate_finding_label(
        entry["label"],
        context=f"finding_verifications[{index}].label",
    )
    source_sentence_aliases = entry["source_sentence_aliases"]
    if not isinstance(source_sentence_aliases, list) or not source_sentence_aliases:
        raise ValueError(
            f"finding_verifications[{index}].source_sentence_aliases "
            "must be a non-empty array"
        )
    validated_aliases = tuple(
        _validate_sentence_alias(
            alias,
            context=(
                f"finding_verifications[{index}].source_sentence_aliases[{alias_index}]"
            ),
        )
        for alias_index, alias in enumerate(source_sentence_aliases)
    )
    return ComparisonFindingVerificationRevisedEntry(
        finding_id=finding_id,
        verification_result="revised",
        conclusion=conclusion.strip(),
        label=label,
        source_sentence_aliases=validated_aliases,
    )


def _validate_additional_finding(
    entry: Mapping[str, Any],
    *,
    index: int,
) -> ComparisonFindingVerificationAdditionalFinding:
    if not isinstance(entry, dict):
        raise ValueError(f"additional_findings[{index}] must be an object")
    if set(entry) != _ADDITIONAL_FINDING_KEYS:
        raise ValueError(
            f"additional_findings[{index}] must contain exactly conclusion, label, "
            "and source_sentence_aliases"
        )
    conclusion = entry["conclusion"]
    if not isinstance(conclusion, str) or not conclusion.strip():
        raise ValueError(
            f"additional_findings[{index}].conclusion must be a non-empty string"
        )
    label = _validate_finding_label(
        entry["label"],
        context=f"additional_findings[{index}].label",
    )
    source_sentence_aliases = entry["source_sentence_aliases"]
    if not isinstance(source_sentence_aliases, list) or not source_sentence_aliases:
        raise ValueError(
            f"additional_findings[{index}].source_sentence_aliases "
            "must be a non-empty array"
        )
    validated_aliases = tuple(
        _validate_sentence_alias(
            alias,
            context=(
                f"additional_findings[{index}].source_sentence_aliases[{alias_index}]"
            ),
        )
        for alias_index, alias in enumerate(source_sentence_aliases)
    )
    return ComparisonFindingVerificationAdditionalFinding(
        conclusion=conclusion.strip(),
        label=label,
        source_sentence_aliases=validated_aliases,
    )


def validate_comparison_finding_verification_response_structure(
    payload: Mapping[str, Any],
    *,
    input_finding_ids: Sequence[str],
) -> ComparisonFindingVerificationValidatedResponse:
    """Validate top-level Finding Verification response shape and finding coverage."""

    allowed_keys = {"finding_verifications"}
    if "additional_findings" in payload:
        allowed_keys = {"finding_verifications", "additional_findings"}
    if set(payload) != allowed_keys:
        raise ValueError(
            "response object must contain finding_verifications and optionally "
            "additional_findings only"
        )

    finding_verifications = payload["finding_verifications"]
    if not isinstance(finding_verifications, list):
        raise ValueError("finding_verifications must be an array")

    validated_entries: list[ComparisonFindingVerificationEntry] = []
    response_finding_ids: list[str] = []
    for index, entry in enumerate(finding_verifications):
        validated = _validate_finding_verification_entry(entry, index=index)
        validated_entries.append(validated)
        response_finding_ids.append(validated.finding_id)

    _validate_finding_id_coverage(response_finding_ids, input_finding_ids)

    additional_findings_raw = payload.get("additional_findings", ())
    if additional_findings_raw == ():
        additional_validated: tuple[
            ComparisonFindingVerificationAdditionalFinding, ...
        ] = ()
    else:
        if not isinstance(additional_findings_raw, list):
            raise ValueError("additional_findings must be an array when present")
        additional_validated = tuple(
            _validate_additional_finding(entry, index=index)
            for index, entry in enumerate(additional_findings_raw)
        )

    return ComparisonFindingVerificationValidatedResponse(
        finding_verifications=tuple(validated_entries),
        additional_findings=additional_validated,
    )


def parse_and_validate_comparison_finding_verification_response(
    raw_text: str,
    *,
    input_finding_ids: Sequence[str],
) -> ComparisonFindingVerificationValidatedResponse:
    """Parse raw provider text and validate the Verification response contract."""

    payload = parse_comparison_finding_verification_response(raw_text)
    return validate_comparison_finding_verification_response_structure(
        payload,
        input_finding_ids=input_finding_ids,
    )


def _serialize_finding_verification_entry(
    entry: ComparisonFindingVerificationEntry,
) -> dict[str, Any]:
    if isinstance(
        entry,
        (
            ComparisonFindingVerificationConfirmedEntry,
            ComparisonFindingVerificationRejectedEntry,
        ),
    ):
        return {
            "finding_id": entry.finding_id,
            "verification_result": entry.verification_result,
        }
    return {
        "finding_id": entry.finding_id,
        "verification_result": entry.verification_result,
        "conclusion": entry.conclusion,
        "label": entry.label,
        "source_sentence_aliases": list(entry.source_sentence_aliases),
    }


def serialize_validated_response(
    validated_response: ComparisonFindingVerificationValidatedResponse,
) -> dict[str, Any]:
    """Serialize a validated Verification response for persistence."""

    payload: dict[str, Any] = {
        "finding_verifications": [
            _serialize_finding_verification_entry(entry)
            for entry in validated_response.finding_verifications
        ],
    }
    if validated_response.additional_findings:
        payload["additional_findings"] = [
            {
                "conclusion": finding.conclusion,
                "label": finding.label,
                "source_sentence_aliases": list(finding.source_sentence_aliases),
            }
            for finding in validated_response.additional_findings
        ]
    return payload


__all__ = [
    "ComparisonFindingVerificationAdditionalFinding",
    "ComparisonFindingVerificationConfirmedEntry",
    "ComparisonFindingVerificationEntry",
    "ComparisonFindingVerificationRejectedEntry",
    "ComparisonFindingVerificationRevisedEntry",
    "ComparisonFindingVerificationLabel",
    "ComparisonFindingVerificationValidatedResponse",
    "VerificationResult",
    "parse_and_validate_comparison_finding_verification_response",
    "parse_comparison_finding_verification_response",
    "serialize_validated_response",
    "validate_comparison_finding_verification_response_structure",
]
