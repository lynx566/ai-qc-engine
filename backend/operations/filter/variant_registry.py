"""Neutral Filter job variant indexing and resolution."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any


def build_filter_job_variants(
    configs: Iterable[Any],
) -> MappingProxyType[tuple[str, str], Any]:
    """Derive an immutable (filter_job_id, language) → config index from installed configs."""

    variants: dict[tuple[str, str], Any] = {}
    for config in configs:
        key = (config.filter_job_id, config.language)
        if key in variants:
            existing = variants[key]
            raise ValueError(
                "duplicate installed Filter variant for "
                f"filter_job_id={key[0]!r}, language={key[1]!r}: "
                f"{existing.zone_config_name!r} and {config.zone_config_name!r}"
            )
        variants[key] = config
    return MappingProxyType(variants)


def resolve_filter_job_variant(
    *,
    filter_job_id: str,
    language: str,
    filter_job_variants: Mapping[tuple[str, str], Any],
) -> Any:
    """Resolve one installed localized Filter config for a product job and language."""

    if not isinstance(filter_job_id, str) or not filter_job_id.strip():
        raise ValueError("filter_job_id must be a non-empty string")
    if language is None:
        raise ValueError("language is required for Filter variant resolution")
    if not isinstance(language, str) or not language.strip():
        raise ValueError("language must be a non-empty string")

    key = (filter_job_id, language)
    resolved = filter_job_variants.get(key)
    if resolved is not None:
        return resolved

    known_languages = sorted(
        {
            lang
            for job, lang in filter_job_variants
            if job == filter_job_id
        }
    )
    if not known_languages:
        raise ValueError(f"unknown Filter job: {filter_job_id!r}")
    raise ValueError(
        f"unsupported language variant for Filter job {filter_job_id!r}: "
        f"language={language!r}"
    )


__all__ = [
    "build_filter_job_variants",
    "resolve_filter_job_variant",
]
