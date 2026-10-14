from __future__ import annotations

from core.document.doc_identity import DocumentProcessingIdentity
from core.document.document_schema import DocumentBundle
from core.document.extract.strategies import resolve_extract_strategy


def run(
    source_bytes: bytes,
    *,
    identity: DocumentProcessingIdentity,
    extract_config_id: str,
) -> DocumentBundle:
    """Canonical in-memory Extract Step.

    Receives immutable source bytes plus a pre-established processing identity
    and a selected Extract configuration reference. Physical file access and
    persistence are owned by Runtime; this Step resolves the Extract
    implementation and returns a DocumentBundle.
    """
    if not isinstance(source_bytes, (bytes, bytearray)):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(identity, DocumentProcessingIdentity):
        raise TypeError("identity must be a DocumentProcessingIdentity")
    if not isinstance(extract_config_id, str) or not extract_config_id.strip():
        raise TypeError("extract_config_id must be a non-empty str")

    extractor = resolve_extract_strategy(extract_config_id)
    bundle = extractor(source_bytes, identity=identity)
    if not isinstance(bundle, DocumentBundle):
        raise TypeError("extract strategy must return a DocumentBundle")
    return bundle
