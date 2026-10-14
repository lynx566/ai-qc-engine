"""Product-final findings artifact contract for Evidence Comparison."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    SENTENCE_ALIAS_PATTERN,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    FINDING_ID_PATTERN,
)

FINAL_FINDINGS_FILENAME = "final_findings.json"
FINAL_FINDINGS_ARTIFACT_TYPE = "final_findings"
FINAL_FINDINGS_SCHEMA_VERSION = "0.1.0"

# This serialized order belongs to the artifact contract. It must not be derived
# from the declaration order of a plugin enum.
FINAL_FINDINGS_COMPARISON_MODE_ORDER = (
    "scope_local",
    "focus_comparison",
    "ib_to_dsur",
    "dsur_to_ib",
)

_ALLOWED_LABELS = frozenset({"fail", "need_review"})
_ALLOWED_FINALIZATION_STATUSES = frozenset(
    {"completed", "completed_with_fallback"}
)
_ROOT_KEYS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "finalization_status",
        "fallback_comparison_modes",
        "findings",
    }
)
_FINDING_KEYS = frozenset(
    {
        "finding_id",
        "label",
        "conclusion",
        "source_sentence_aliases",
        "comparison_mode_id",
        "source_finding_ids",
    }
)


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


def _validate_fallback_comparison_modes(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise TypeError("fallback_comparison_modes must be an array")

    canonical_indexes = {
        mode: index
        for index, mode in enumerate(FINAL_FINDINGS_COMPARISON_MODE_ORDER)
    }
    validated: list[str] = []
    previous_index = -1
    for index, raw_mode in enumerate(value):
        mode = _require_non_empty_str(
            raw_mode,
            field=f"fallback_comparison_modes[{index}]",
        )
        canonical_index = canonical_indexes.get(mode)
        if canonical_index is None:
            raise ValueError(
                "fallback_comparison_modes must contain only supported "
                "comparison mode ids"
            )
        if canonical_index <= previous_index:
            raise ValueError(
                "fallback_comparison_modes must be a unique ordered "
                "subsequence of the artifact canonical comparison-mode order"
            )
        validated.append(mode)
        previous_index = canonical_index
    return validated


def _validate_string_array(
    value: Any,
    *,
    path: str,
    pattern: Any,
    format_name: str,
    require_unique: bool,
) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path} must be a non-empty array")
    validated = [
        _require_non_empty_str(item, field=f"{path}[{index}]")
        for index, item in enumerate(value)
    ]
    for index, item in enumerate(validated):
        if pattern.fullmatch(item) is None:
            raise ValueError(f"{path}[{index}] must match {format_name} format")
    if require_unique and len(set(validated)) != len(validated):
        raise ValueError(f"{path} values must be internally unique")
    return validated


def validate_final_findings(payload: Mapping[str, Any]) -> None:
    """Validate one product-final findings artifact."""

    if not isinstance(payload, Mapping):
        raise TypeError("final_findings must be an object")
    _require_exact_keys(payload, expected=_ROOT_KEYS, path="root")

    if payload.get("artifact_type") != FINAL_FINDINGS_ARTIFACT_TYPE:
        raise ValueError(
            f"artifact_type must be {FINAL_FINDINGS_ARTIFACT_TYPE!r}"
        )
    if payload.get("schema_version") != FINAL_FINDINGS_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {FINAL_FINDINGS_SCHEMA_VERSION!r}"
        )

    finalization_status = _require_non_empty_str(
        payload.get("finalization_status"),
        field="finalization_status",
    )
    if finalization_status not in _ALLOWED_FINALIZATION_STATUSES:
        raise ValueError("finalization_status must be a supported status")
    fallback_modes = _validate_fallback_comparison_modes(
        payload.get("fallback_comparison_modes")
    )
    expected_status = (
        "completed_with_fallback" if fallback_modes else "completed"
    )
    if finalization_status != expected_status:
        raise ValueError(
            "finalization_status must be 'completed' exactly when "
            "fallback_comparison_modes is empty, otherwise "
            "'completed_with_fallback'"
        )

    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise TypeError("findings must be an array")

    comparison_modes = frozenset(FINAL_FINDINGS_COMPARISON_MODE_ORDER)
    seen_finding_ids: set[str] = set()
    claimed_source_finding_ids: set[str] = set()
    for index, finding in enumerate(findings):
        path = f"findings[{index}]"
        if not isinstance(finding, Mapping):
            raise TypeError(f"{path} must be an object")
        _require_exact_keys(finding, expected=_FINDING_KEYS, path=path)

        finding_id = _require_non_empty_str(
            finding.get("finding_id"), field=f"{path}.finding_id"
        )
        if FINDING_ID_PATTERN.fullmatch(finding_id) is None:
            raise ValueError(f"{path}.finding_id must match Lddd format")
        if finding_id in seen_finding_ids:
            raise ValueError(f"duplicate finding_id across artifact: {finding_id!r}")
        seen_finding_ids.add(finding_id)

        label = _require_non_empty_str(
            finding.get("label"), field=f"{path}.label"
        )
        if label not in _ALLOWED_LABELS:
            raise ValueError(f"{path}.label must be fail or need_review")
        _require_non_empty_str(
            finding.get("conclusion"), field=f"{path}.conclusion"
        )
        _validate_string_array(
            finding.get("source_sentence_aliases"),
            path=f"{path}.source_sentence_aliases",
            pattern=SENTENCE_ALIAS_PATTERN,
            format_name="Tdddd",
            require_unique=False,
        )

        comparison_mode_id = _require_non_empty_str(
            finding.get("comparison_mode_id"),
            field=f"{path}.comparison_mode_id",
        )
        if comparison_mode_id not in comparison_modes:
            raise ValueError(
                f"{path}.comparison_mode_id must be a supported comparison mode id"
            )

        source_finding_ids = _validate_string_array(
            finding.get("source_finding_ids"),
            path=f"{path}.source_finding_ids",
            pattern=FINDING_ID_PATTERN,
            format_name="Lddd",
            require_unique=True,
        )
        reused_source_ids = claimed_source_finding_ids.intersection(
            source_finding_ids
        )
        if reused_source_ids:
            raise ValueError(
                "source_finding_id must not be reused across final findings: "
                f"{sorted(reused_source_ids)!r}"
            )
        claimed_source_finding_ids.update(source_finding_ids)


def build_final_findings(
    *,
    finalization_status: str,
    fallback_comparison_modes: Sequence[str],
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate one product-final findings artifact."""

    payload: dict[str, Any] = {
        "artifact_type": FINAL_FINDINGS_ARTIFACT_TYPE,
        "schema_version": FINAL_FINDINGS_SCHEMA_VERSION,
        "finalization_status": finalization_status,
        "fallback_comparison_modes": list(fallback_comparison_modes),
        "findings": [dict(finding) for finding in findings],
    }
    validate_final_findings(payload)
    return payload


__all__ = [
    "FINAL_FINDINGS_ARTIFACT_TYPE",
    "FINAL_FINDINGS_COMPARISON_MODE_ORDER",
    "FINAL_FINDINGS_FILENAME",
    "FINAL_FINDINGS_SCHEMA_VERSION",
    "build_final_findings",
    "validate_final_findings",
]
