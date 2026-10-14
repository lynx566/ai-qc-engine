"""Clinical-trial-specific doc_meta summary construction."""

from __future__ import annotations

from typing import Any

from core.metadata.date_normalize import (
    normalize_date_range_value,
    normalize_date_value,
)

CLINICAL_TRIAL_DOC_META_SUMMARY_FIELD_NAMES: tuple[str, ...] = (
    "study_drug",
    "sponsor",
    "investigator",
    "version",
    "document_date",
    "cutoff_date",
    "reporting_period",
    # CSR title-page metadata; null for IB/DSUR when not extracted
    "study_title",
    "drug_modality",
    "indication",
    "study_phase",
    "study_start_date",
    "first_subject_dosed_date",
    "dose_escalation_completion_date",
    "study_completion_date",
    "database_lock_date",
    "report_date",
)

CLINICAL_TRIAL_DOC_META_DATE_FIELDS: frozenset[str] = frozenset(
    {
        "document_date",
        "cutoff_date",
        "report_date",
        "study_start_date",
        "first_subject_dosed_date",
        "dose_escalation_completion_date",
        "study_completion_date",
        "database_lock_date",
    }
)

CLINICAL_TRIAL_DOC_META_DATE_RANGE_FIELDS: frozenset[str] = frozenset(
    {
        "reporting_period",
    }
)


def _summary_value_for_field(field: dict[str, Any] | None) -> str | None:
    if field is None:
        return None
    if field.get("confidence") == "none":
        return None
    value = field.get("value")
    return str(value) if value is not None else None


def _summary_protocol_ids(field: dict[str, Any] | None) -> list[str]:
    """Map internal ``fields.protocol_id`` to canonical summary ``protocol_ids`` list."""
    if field is None:
        return []
    if field.get("confidence") == "none":
        return []

    values = field.get("values")
    if isinstance(values, list) and values:
        return [str(value).strip() for value in values if str(value).strip()]

    value = field.get("value")
    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def _normalize_clinical_summary_field_value(
    field_name: str,
    value: str | None,
) -> str | None:
    if field_name in CLINICAL_TRIAL_DOC_META_DATE_RANGE_FIELDS:
        return normalize_date_range_value(value)
    if field_name in CLINICAL_TRIAL_DOC_META_DATE_FIELDS:
        return normalize_date_value(value)
    return value


def build_clinical_trial_doc_meta_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    """Build clinical-trial-specific lightweight metadata summary for LLM input/UI.

    ``summary.protocol_ids`` is always a list. It carries protocol identifiers
    explicitly declared in metadata source regions only; not all protocols cited
    or referenced in the full document body.
    """
    doc_type = bundle.get("doc_type") or {}
    fields = bundle.get("fields") or {}

    summary: dict[str, Any] = {
        "doc_type": doc_type.get("value"),
        "protocol_ids": _summary_protocol_ids(fields.get("protocol_id")),
    }

    for field_name in CLINICAL_TRIAL_DOC_META_SUMMARY_FIELD_NAMES:
        field = fields.get(field_name)
        raw_value = _summary_value_for_field(field)
        summary[field_name] = _normalize_clinical_summary_field_value(
            field_name,
            raw_value,
        )

    return summary
