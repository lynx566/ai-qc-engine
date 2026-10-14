"""Runtime registry facade for assessment profiles and LLM mode choices."""

from __future__ import annotations

from llm.model_registry import (
    DEFAULT_LLM_PROFILE,
    LLM_PROFILE_CHOICES,
    resolve_llm_profile,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.registry import (
    ASSESSMENT_PROFILE_CHOICES,
    DEFAULT_ASSESSMENT_PROFILE_NAME,
    deprecated_assessment_profile_alias_kind,
    is_deprecated_assessment_profile_alias,
    normalize_assessment_profile_name,
    resolve_clinical_trial_doc_assessment_profile,
)

ASSESSMENT_LLM_CHOICES: tuple[str, ...] = ("mock", "api")

DEFAULT_ASSESSMENT_LLM_PROFILE = DEFAULT_LLM_PROFILE
DEFAULT_ASSESSMENT_PROFILE = DEFAULT_ASSESSMENT_PROFILE_NAME

# Dev default: API assess runs write debug/ unless --no-llm-debug-artifacts.
DEFAULT_WRITE_LLM_DEBUG_ARTIFACTS = True

_CANONICAL_AGGREGATE_HEADING_SCOPE_ASSESSMENT_PROFILE = (
    "clinical_safety_aggregate_heading_scope_assessment_zh"
)


def warn_deprecated_assessment_profile_alias(name: str | None) -> None:
    """Emit a CLI-visible warning when a legacy alias is normalized."""
    import sys

    if not is_deprecated_assessment_profile_alias(name):
        return
    token = str(name).strip()
    normalized = normalize_assessment_profile_name(token)
    alias_kind = deprecated_assessment_profile_alias_kind(token)
    if alias_kind == "retired_per_unit":
        print(
            f"warning: deprecated assessment profile alias {token!r}; "
            "retired per-unit profile name mapped to the canonical "
            "aggregate heading-scope assessment profile; "
            f"use {_CANONICAL_AGGREGATE_HEADING_SCOPE_ASSESSMENT_PROFILE!r} instead",
            file=sys.stderr,
        )
        return
    if alias_kind == "deprecated_ambiguous":
        print(
            f"warning: deprecated assessment profile alias {token!r}; "
            "deprecated ambiguous profile name mapped to "
            f"{_CANONICAL_AGGREGATE_HEADING_SCOPE_ASSESSMENT_PROFILE!r}; "
            f"use {normalized!r} instead",
            file=sys.stderr,
        )
        return
    print(
        f"warning: deprecated assessment profile alias {token!r}; "
        f"use {normalized!r} instead",
        file=sys.stderr,
    )


def resolve_assessment_profile(name: str) -> str:
    warn_deprecated_assessment_profile_alias(name)
    normalized = normalize_assessment_profile_name(name)
    resolve_clinical_trial_doc_assessment_profile(normalized)
    return normalized


__all__ = [
    "ASSESSMENT_PROFILE_CHOICES",
    "DEFAULT_ASSESSMENT_PROFILE",
    "DEFAULT_ASSESSMENT_LLM_PROFILE",
    "DEFAULT_WRITE_LLM_DEBUG_ARTIFACTS",
    "LLM_PROFILE_CHOICES",
    "ASSESSMENT_LLM_CHOICES",
    "deprecated_assessment_profile_alias_kind",
    "is_deprecated_assessment_profile_alias",
    "normalize_assessment_profile_name",
    "resolve_assessment_profile",
    "resolve_clinical_trial_doc_assessment_profile",
    "resolve_llm_profile",
    "warn_deprecated_assessment_profile_alias",
]
