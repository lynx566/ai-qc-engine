from __future__ import annotations

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.profile import (
    CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE,
    CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME,
    ClinicalTrialDocAssessmentProfile,
)

_CLINICAL_SAFETY_AGGREGATE_FINDING_ZH_TAG_PROFILE_NAME = "clinical_safety_aggregate_finding_zh"

ASSESSMENT_PROFILE_REGISTRY: dict[str, ClinicalTrialDocAssessmentProfile] = {
    CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME: (
        CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE
    ),
}

ASSESSMENT_PROFILE_CHOICES: tuple[str, ...] = tuple(
    sorted(ASSESSMENT_PROFILE_REGISTRY.keys())
)

_LEGACY_TAG_PROFILE_TO_ASSESSMENT_PROFILE: dict[str, str] = {
    _CLINICAL_SAFETY_AGGREGATE_FINDING_ZH_TAG_PROFILE_NAME: (
        CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME
    ),
    "clinical_safety_scope_annotation_zh": (
        CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME
    ),
}

DEFAULT_ASSESSMENT_PROFILE_NAME = (
    CLINICAL_SAFETY_AGGREGATE_HEADING_SCOPE_ASSESSMENT_ZH_PROFILE_NAME
)


def is_deprecated_assessment_profile_alias(name: str | None) -> bool:
    if not name:
        return False
    return str(name).strip() in _LEGACY_TAG_PROFILE_TO_ASSESSMENT_PROFILE


def deprecated_assessment_profile_alias_kind(name: str | None) -> str | None:
    if not name:
        return None
    token = str(name).strip()
    if token == _CLINICAL_SAFETY_AGGREGATE_FINDING_ZH_TAG_PROFILE_NAME:
        return "retired_per_unit"
    if token == "clinical_safety_scope_annotation_zh":
        return "deprecated_ambiguous"
    return None


def resolve_clinical_trial_doc_assessment_profile(name: str) -> ClinicalTrialDocAssessmentProfile:
    profile = ASSESSMENT_PROFILE_REGISTRY.get(name)
    if profile is None:
        raise ValueError(
            f"unknown assessment profile {name!r}; "
            f"choices: {', '.join(ASSESSMENT_PROFILE_CHOICES)}"
        )
    return profile


def normalize_assessment_profile_name(name: str | None) -> str:
    if not name:
        return DEFAULT_ASSESSMENT_PROFILE_NAME
    token = str(name).strip()
    mapped = _LEGACY_TAG_PROFILE_TO_ASSESSMENT_PROFILE.get(token)
    if mapped is not None:
        return mapped
    resolve_clinical_trial_doc_assessment_profile(token)
    return token
