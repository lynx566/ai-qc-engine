"""Expected regulatory document-type vocabulary for clinical-trial installation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

ClinicalTrialDocumentType = Literal["IB", "CSR", "DSUR"]

CLINICAL_TRIAL_DOCUMENT_TYPES: frozenset[str] = frozenset({"IB", "CSR", "DSUR"})


def validate_expected_document_type_installation(
    *,
    expected_document_type_bindings: Mapping[tuple[str, str], ClinicalTrialDocumentType],
) -> None:
    """Validate installed clinical document-type values for the binding table."""

    for key, expected_type in expected_document_type_bindings.items():
        if expected_type not in CLINICAL_TRIAL_DOCUMENT_TYPES:
            capability_id, slot_id = key
            raise ValueError(
                "expected_document_type binding has invalid document type "
                f"{expected_type!r} for capability slot "
                f"({capability_id!r}, {slot_id!r})"
            )


__all__ = [
    "CLINICAL_TRIAL_DOCUMENT_TYPES",
    "ClinicalTrialDocumentType",
    "validate_expected_document_type_installation",
]
