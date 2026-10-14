"""Versioned job-final findings artifact contract for Evidence Comparison."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_aliases import (
    SENTENCE_ALIAS_PATTERN,
)

FINDINGS_FILENAME = "findings.json"
FINDINGS_ARTIFACT_TYPE = "findings"
FINDINGS_SCHEMA_VERSION = "0.2.0"
FINDING_ID_PATTERN = re.compile(r"^L\d{3}$")

_ALLOWED_COMPARISON_MODE_IDS = frozenset(
    {
        "scope_local",
        "focus_comparison",
        "ib_to_dsur",
        "dsur_to_ib",
    }
)
_ALLOWED_GROUP_ROLES = frozenset(
    {
        "scope",
        "focus_scope",
        "comparison_scopes",
        "ib_scope",
        "dsur_scopes",
        "ib_scopes",
    }
)
_ALLOWED_LABELS = frozenset({"fail", "need_review"})

_JOB_ENTRY_KEYS = frozenset(
    {
        "frozen_job_index",
        "comparison_mode_id",
        "comparison_groups",
        "findings",
    }
)
_GROUP_KEYS = frozenset({"group_role", "scope_aliases"})
_FINDING_KEYS = frozenset(
    {
        "finding_id",
        "conclusion",
        "label",
        "source_sentence_aliases",
    }
)
_ROOT_KEYS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "jobs",
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


def _validate_comparison_groups(
    comparison_groups: Any,
    *,
    path: str,
) -> list[dict[str, Any]]:
    if not isinstance(comparison_groups, list) or not comparison_groups:
        raise ValueError(f"{path} must be a non-empty array")

    validated_groups: list[dict[str, Any]] = []
    for index, group in enumerate(comparison_groups):
        group_path = f"{path}[{index}]"
        if not isinstance(group, Mapping):
            raise TypeError(f"{group_path} must be an object")
        _require_exact_keys(group, expected=_GROUP_KEYS, path=group_path)
        group_role = _require_non_empty_str(
            group.get("group_role"),
            field=f"{group_path}.group_role",
        )
        if group_role not in _ALLOWED_GROUP_ROLES:
            raise ValueError(f"{group_path}.group_role must be a supported group role")
        scope_aliases_raw = group.get("scope_aliases")
        if not isinstance(scope_aliases_raw, list) or not scope_aliases_raw:
            raise ValueError(f"{group_path}.scope_aliases must be a non-empty array")
        scope_aliases = [
            _require_non_empty_str(
                alias,
                field=f"{group_path}.scope_aliases[{alias_index}]",
            )
            for alias_index, alias in enumerate(scope_aliases_raw)
        ]
        validated_groups.append(
            {
                "group_role": group_role,
                "scope_aliases": scope_aliases,
            }
        )
    return validated_groups


def _validate_findings(
    findings: Any,
    *,
    path: str,
    allowed_labels: frozenset[str],
) -> list[dict[str, Any]]:
    if not isinstance(findings, list):
        raise TypeError(f"{path} must be an array")

    validated_findings: list[dict[str, Any]] = []
    seen_finding_ids: set[str] = set()
    for index, finding in enumerate(findings):
        finding_path = f"{path}[{index}]"
        if not isinstance(finding, Mapping):
            raise TypeError(f"{finding_path} must be an object")
        _require_exact_keys(finding, expected=_FINDING_KEYS, path=finding_path)
        finding_id = _require_non_empty_str(
            finding.get("finding_id"),
            field=f"{finding_path}.finding_id",
        )
        if FINDING_ID_PATTERN.fullmatch(finding_id) is None:
            raise ValueError(f"{finding_path}.finding_id must match Lddd format")
        if finding_id in seen_finding_ids:
            raise ValueError(f"duplicate finding_id within job: {finding_id!r}")
        seen_finding_ids.add(finding_id)
        conclusion = _require_non_empty_str(
            finding.get("conclusion"),
            field=f"{finding_path}.conclusion",
        )
        label = _require_non_empty_str(
            finding.get("label"),
            field=f"{finding_path}.label",
        )
        if label not in allowed_labels:
            allowed_label_text = " or ".join(sorted(allowed_labels))
            raise ValueError(
                f"{finding_path}.label must be {allowed_label_text}"
            )
        source_sentence_aliases = finding.get("source_sentence_aliases")
        if not isinstance(source_sentence_aliases, list) or not source_sentence_aliases:
            raise ValueError(
                f"{finding_path}.source_sentence_aliases must be a non-empty array"
            )
        validated_aliases = [
            _require_non_empty_str(
                alias,
                field=f"{finding_path}.source_sentence_aliases[{alias_index}]",
            )
            for alias_index, alias in enumerate(source_sentence_aliases)
        ]
        for alias_index, alias in enumerate(validated_aliases):
            if not SENTENCE_ALIAS_PATTERN.fullmatch(alias):
                raise ValueError(
                    f"{finding_path}.source_sentence_aliases[{alias_index}] "
                    "must match Tdddd format"
                )
        validated_findings.append(
            {
                "finding_id": finding_id,
                "conclusion": conclusion,
                "label": label,
                "source_sentence_aliases": validated_aliases,
            }
        )
    return validated_findings


def validate_findings(payload: Mapping[str, Any]) -> None:
    """Validate one formal findings envelope."""

    if not isinstance(payload, Mapping):
        raise TypeError("findings must be an object")
    _require_exact_keys(payload, expected=_ROOT_KEYS, path="root")

    if payload.get("artifact_type") != FINDINGS_ARTIFACT_TYPE:
        raise ValueError(f"artifact_type must be {FINDINGS_ARTIFACT_TYPE!r}")
    if payload.get("schema_version") != FINDINGS_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {FINDINGS_SCHEMA_VERSION!r}")

    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("jobs must be a non-empty array")

    seen_finding_ids: set[str] = set()
    for job_index, job in enumerate(jobs):
        job_path = f"jobs[{job_index}]"
        if not isinstance(job, Mapping):
            raise TypeError(f"{job_path} must be an object")
        _require_exact_keys(job, expected=_JOB_ENTRY_KEYS, path=job_path)
        frozen_job_index = job.get("frozen_job_index")
        if not isinstance(frozen_job_index, int) or frozen_job_index < 1:
            raise ValueError(f"{job_path}.frozen_job_index must be a positive integer")
        comparison_mode_id = _require_non_empty_str(
            job.get("comparison_mode_id"),
            field=f"{job_path}.comparison_mode_id",
        )
        if comparison_mode_id not in _ALLOWED_COMPARISON_MODE_IDS:
            raise ValueError(
                f"{job_path}.comparison_mode_id must be a supported comparison mode id"
            )
        _validate_comparison_groups(
            job.get("comparison_groups"),
            path=f"{job_path}.comparison_groups",
        )
        job_findings = _validate_findings(
            job.get("findings"),
            path=f"{job_path}.findings",
            allowed_labels=_ALLOWED_LABELS,
        )
        for finding in job_findings:
            finding_id = finding["finding_id"]
            if finding_id in seen_finding_ids:
                raise ValueError(
                    f"duplicate finding_id across artifact: {finding_id!r}"
                )
            seen_finding_ids.add(finding_id)


def build_findings(
    *,
    jobs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate a findings envelope."""

    envelope: dict[str, Any] = {
        "artifact_type": FINDINGS_ARTIFACT_TYPE,
        "schema_version": FINDINGS_SCHEMA_VERSION,
        "jobs": [dict(job) for job in jobs],
    }
    validate_findings(envelope)
    return envelope


__all__ = [
    "FINDINGS_ARTIFACT_TYPE",
    "FINDINGS_FILENAME",
    "FINDINGS_SCHEMA_VERSION",
    "FINDING_ID_PATTERN",
    "build_findings",
    "validate_findings",
]
