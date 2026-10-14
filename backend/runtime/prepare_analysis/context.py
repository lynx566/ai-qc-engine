"""Prepare-analysis runtime context helpers."""

from __future__ import annotations

from typing import Any

PREPARE_ANALYSIS_LANGUAGE_CHOICES = ("zh",)
PREPARE_ANALYSIS_STAGE_SCOPE = "analysis_preparation"


def infer_language_from_bundle(bundle_dict: dict[str, Any]) -> str | None:
    meta = bundle_dict.get("document_meta") or {}
    language = meta.get("language")
    if language is None:
        return None
    text = str(language).strip()
    return text or None
