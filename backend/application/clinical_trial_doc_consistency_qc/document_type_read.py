"""Best-effort document-type advice from a slot's persisted Doc Meta artifact."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path

from application.document_consistency_qc.document_type_result import (
    diagnose_document_type_bundle,
)
from core.metadata.document_type_diagnostic import DocumentTypeDiagnostic
from runtime.io import load_json

from .capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS,
)
from .expected_document_type_installation import CLINICAL_TRIAL_DOCUMENT_TYPES

logger = logging.getLogger(__name__)


def read_slot_document_type_diagnostic(
    *,
    capability_id: str,
    slot_id: str,
    doc_meta_bundle_path: str | None,
) -> DocumentTypeDiagnostic | None:
    """Return no advice when historical metadata is absent or cannot be read.

    Unresolved type values inside a readable bundle remain semantic ``uncertain``.
    This read never regenerates metadata or changes the persisted execution state.
    """
    expected = INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS.get(
        (capability_id, slot_id)
    )
    if expected is None or not doc_meta_bundle_path:
        return None
    try:
        bundle = load_json(Path(doc_meta_bundle_path))
        if not isinstance(bundle, Mapping) or not isinstance(
            bundle.get("doc_type"), Mapping
        ):
            raise ValueError("doc_meta_bundle is missing its document-type metadata")
        if "value" not in bundle["doc_type"] or not isinstance(
            bundle.get("warnings"), list
        ):
            raise ValueError(
                "doc_meta_bundle has an invalid document-type metadata shape"
            )
        value = bundle["doc_type"]["value"]
        if value is not None and not isinstance(value, str):
            raise ValueError("doc_meta_bundle document-type value must be text or null")
        return diagnose_document_type_bundle(
            expected_document_type=expected,
            doc_meta_bundle=bundle,
            supported_document_types=CLINICAL_TRIAL_DOCUMENT_TYPES,
        )
    except (OSError, ValueError, TypeError):
        logger.warning(
            "Document-type advice unavailable for capability=%s slot=%s",
            capability_id,
            slot_id,
            exc_info=True,
        )
        return None
