"""Thin task catalog transport service for Document Consistency QC."""

from __future__ import annotations

from task.clinical_trial_doc_qc.catalog import (
    build_product_task_catalog,
    product_task_catalog_to_mapping,
)


def load_task_catalog() -> list[dict[str, object]]:
    """Return installed Product Task catalog entries for HTTP serialization."""

    entries = build_product_task_catalog()
    return product_task_catalog_to_mapping(entries)


__all__ = [
    "load_task_catalog",
]
