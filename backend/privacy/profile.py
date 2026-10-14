from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from privacy.detectors.regex_detector import RegexRule

DEFAULT_DATE_SHIFT_OFFSET_DAYS = 17


def default_privacy_profile() -> PrivacyProfile:
    """Return the neutral shared default; domain profiles are injected by plugins."""
    return PrivacyProfile(
        entity_types_to_mask=frozenset(),
        entity_types_to_keep=frozenset(),
        date_shift_offset_days=DEFAULT_DATE_SHIFT_OFFSET_DAYS,
    )


@dataclass(frozen=True)
class PrivacyProfile:
    """Business-level privacy configuration consumed by the mask engine."""

    entity_types_to_mask: frozenset[str]
    entity_types_to_keep: frozenset[str]
    date_shift_offset_days: int = DEFAULT_DATE_SHIFT_OFFSET_DAYS
    regex_rules: dict[str, tuple[RegexRule, ...]] = field(default_factory=dict)
    uie_schema_by_language: dict[str, dict[str, str]] = field(default_factory=dict)
    uie_denylist: frozenset[str] = field(default_factory=frozenset)
    registry_entries: tuple[Any, ...] = ()
    token_prefixes: dict[str, str] = field(default_factory=dict)
