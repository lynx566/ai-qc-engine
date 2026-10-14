"""Route semantic-module installation for clinical-trial Document Consistency QC."""

from __future__ import annotations

from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)

_INSTALLED_ROUTE_SEMANTIC_MODULE_OBJECTS: tuple[str, ...] = (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)

INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE = tuple(
    _INSTALLED_ROUTE_SEMANTIC_MODULE_OBJECTS
)


def validate_route_semantic_module_sequence(
    route_semantic_module_sequence: tuple[str, ...],
) -> None:
    """Reject duplicate or empty semantic module ids in Route installation order."""

    seen: set[str] = set()
    for index, module_id in enumerate(route_semantic_module_sequence):
        if not isinstance(module_id, str) or not module_id.strip():
            raise ValueError(
                f"route_semantic_module_sequence[{index}] must be a non-empty string"
            )
        normalized = module_id.strip()
        if normalized in seen:
            raise ValueError(
                "duplicate installed Route semantic module: "
                f"semantic_module_id={normalized!r}"
            )
        seen.add(normalized)


validate_route_semantic_module_sequence(
    INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE
)

__all__ = [
    "INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE",
    "validate_route_semantic_module_sequence",
]
