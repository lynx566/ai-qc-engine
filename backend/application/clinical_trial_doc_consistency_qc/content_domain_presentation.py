"""User-facing presentation labels for installed content domains (route semantic modules)."""

from __future__ import annotations

from types import MappingProxyType

from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)

_CONTENT_DOMAIN_DISPLAY_LABEL_BY_ID: dict[str, str] = {
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID: "临床安全性",
}

INSTALLED_CLINICAL_TRIAL_DOC_CONTENT_DOMAIN_DISPLAY_LABELS: MappingProxyType[str, str] = (
    MappingProxyType(_CONTENT_DOMAIN_DISPLAY_LABEL_BY_ID)
)


def content_domain_display_label(content_domain_id: str) -> str:
    """Resolve the user-facing label for one installed content domain id."""

    normalized = content_domain_id.strip()
    label = INSTALLED_CLINICAL_TRIAL_DOC_CONTENT_DOMAIN_DISPLAY_LABELS.get(normalized)
    if label is None:
        raise ValueError(
            f"unknown installed content domain id for presentation: {content_domain_id!r}"
        )
    return label


__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_CONTENT_DOMAIN_DISPLAY_LABELS",
    "content_domain_display_label",
]
