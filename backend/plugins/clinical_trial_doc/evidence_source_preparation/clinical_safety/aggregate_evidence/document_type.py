"""Aggregate-evidence document-type canonicalization."""

from __future__ import annotations

_DOCUMENT_TYPE_MAP = {"IB": "ib", "CSR": "csr", "DSUR": "dsur"}


def canonicalize_aggregate_evidence_document_type(raw_document_type: str) -> str:
    token = str(raw_document_type or "").strip()
    document_type = _DOCUMENT_TYPE_MAP.get(token)
    if document_type is None:
        raise ValueError(
            f"unsupported aggregate evidence document type {token!r}; "
            f"expected one of {sorted(_DOCUMENT_TYPE_MAP)!r}"
        )
    return document_type


__all__ = ["canonicalize_aggregate_evidence_document_type"]
