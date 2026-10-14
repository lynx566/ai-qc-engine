from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AliasEntityRecord:
    canonical_id: str
    token: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ScopedAliasEntityRecord:
    """Alias entity scoped under a parent canonical entity."""

    canonical_id: str
    token: str
    aliases: tuple[str, ...]
    parent_canonical_id: str
