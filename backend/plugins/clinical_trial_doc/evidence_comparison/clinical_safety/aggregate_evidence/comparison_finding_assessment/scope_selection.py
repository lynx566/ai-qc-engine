"""Heading-profile scope selection for Comparison Finding Assessment."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core.normalization.matching import match_text

from .config import HeadingSelectionProfile


def _heading_path_text(scope: Mapping[str, Any]) -> str:
    heading_path = scope.get("heading_path")
    if not isinstance(heading_path, list) or not all(
        isinstance(item, str) for item in heading_path
    ):
        raise ValueError("scope heading_path must be a string list")
    return " / ".join(heading_path)


def _scope_matches_heading_profile(
    *,
    heading_text: str,
    profile: HeadingSelectionProfile,
) -> bool:
    included, _ = match_text(
        heading_text=heading_text,
        heading_terms=profile.include_terms,
        match_mode=profile.match_mode,
    )
    if not included:
        return False
    if not profile.exclude_terms:
        return True
    excluded, _ = match_text(
        heading_text=heading_text,
        heading_terms=profile.exclude_terms,
        match_mode=profile.match_mode,
    )
    return not excluded


def select_scope_aliases_by_heading_profile(
    *,
    scopes: Sequence[Mapping[str, Any]],
    profile: HeadingSelectionProfile,
) -> tuple[str, ...]:
    """Return scope aliases selected by heading profile in artifact scope order."""

    selected: list[str] = []
    for index, scope in enumerate(scopes):
        if not isinstance(scope, Mapping):
            raise TypeError(f"scopes[{index}] must be a mapping")
        scope_alias = scope.get("scope_alias")
        if not isinstance(scope_alias, str) or not scope_alias.strip():
            raise ValueError(f"scopes[{index}].scope_alias must be a non-empty string")
        heading_text = _heading_path_text(scope)
        if _scope_matches_heading_profile(
            heading_text=heading_text,
            profile=profile,
        ):
            selected.append(scope_alias.strip())
    return tuple(selected)


__all__ = ["select_scope_aliases_by_heading_profile"]
