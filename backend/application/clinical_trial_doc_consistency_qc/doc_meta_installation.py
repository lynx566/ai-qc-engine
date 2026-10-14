"""Doc Meta application installation for clinical-trial Document Consistency QC."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.metadata.schemas import MetadataProfile
from plugins.clinical_trial_doc.doc_meta import (
    CLINICAL_TRIAL_DOC_META_PROFILE,
    build_clinical_trial_doc_meta_summary,
)


@dataclass(frozen=True, slots=True)
class InstalledDocMetaDependencies:
    profile: MetadataProfile
    summary_builder: Callable[[dict[str, Any]], dict[str, Any]]


def resolve_installed_doc_meta_dependencies() -> InstalledDocMetaDependencies:
    """Return the currently installed Doc Meta profile and summary builder."""
    return InstalledDocMetaDependencies(
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
        summary_builder=build_clinical_trial_doc_meta_summary,
    )


__all__ = [
    "CLINICAL_TRIAL_DOC_META_PROFILE",
    "InstalledDocMetaDependencies",
    "build_clinical_trial_doc_meta_summary",
    "resolve_installed_doc_meta_dependencies",
]
