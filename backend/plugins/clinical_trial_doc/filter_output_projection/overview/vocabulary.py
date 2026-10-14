"""Stable Overview semantic decomposition vocabulary."""

from __future__ import annotations

CLINICAL_SAFETY_MODULE = "clinical_safety"
EFFICACY_MODULE = "efficacy"
PHARMACOKINETICS_MODULE = "pharmacokinetics"
NONCLINICAL_MODULE = "nonclinical"
DRUG_INFORMATION_MODULE = "drug_information"
SHARED_CONTEXT_MODULE = "shared_context"
OTHER_MODULE = "other"

BUSINESS_CONTENT_MODULES: frozenset[str] = frozenset(
    {
        CLINICAL_SAFETY_MODULE,
        EFFICACY_MODULE,
        PHARMACOKINETICS_MODULE,
        NONCLINICAL_MODULE,
        DRUG_INFORMATION_MODULE,
    }
)

ALL_CONTENT_MODULES: frozenset[str] = BUSINESS_CONTENT_MODULES | frozenset(
    {SHARED_CONTEXT_MODULE, OTHER_MODULE}
)

EXCLUSIVE_CONTENT_MODULES: frozenset[str] = frozenset(
    {SHARED_CONTEXT_MODULE, OTHER_MODULE}
)

ASSESSMENTS_FIELD = "sentence_assessments"


def normalize_content_modules(modules: list[str]) -> tuple[str, ...]:
    """Validate and normalize one assessment's content_modules list."""

    if not modules:
        raise ValueError("content_modules must be a non-empty list")
    normalized = [str(module).strip() for module in modules]
    if not all(normalized):
        raise ValueError("content_modules must contain non-empty strings")
    if len(set(normalized)) != len(normalized):
        raise ValueError("content_modules must not contain duplicate values")
    unknown = [module for module in normalized if module not in ALL_CONTENT_MODULES]
    if unknown:
        raise ValueError(f"unknown content_modules: {', '.join(unknown)}")
    return tuple(normalized)


__all__ = [
    "ALL_CONTENT_MODULES",
    "ASSESSMENTS_FIELD",
    "BUSINESS_CONTENT_MODULES",
    "CLINICAL_SAFETY_MODULE",
    "DRUG_INFORMATION_MODULE",
    "EFFICACY_MODULE",
    "EXCLUSIVE_CONTENT_MODULES",
    "NONCLINICAL_MODULE",
    "OTHER_MODULE",
    "PHARMACOKINETICS_MODULE",
    "SHARED_CONTEXT_MODULE",
    "normalize_content_modules",
]
