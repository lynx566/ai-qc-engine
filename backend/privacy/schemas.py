from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EntityType = Literal[
    "SUBJECT",
    "SITE",
    "STUDY_DRUG",
    "GENERIC_NAME",
    "TARGET",
    "PROTOCOL_ID",
    "PHASE",
    "INDICATION",
    "BACKGROUND_DRUG",
    "DOSE_LEVEL",
    "INVESTIGATOR",
    "SPONSOR",
    "RECORD_ID",
    "STUDY_ID",
    "OTHER_CCI",
    "DATE",
]


@dataclass(slots=True)
class SensitiveEntityCandidate:
    """
    Raw sensitive entity candidate before merge/dedup.
    """

    original_text: str
    entity_type: EntityType
    start: int
    end: int
    source: str
    confidence: float
    canonical_id: str | None = None
    predefined_token: str | None = None
    parent_canonical_id: str | None = None


@dataclass(slots=True)
class MergedEntity:
    """
    Final merged entity consumed by masking engine.
    """

    original_text: str
    entity_type: EntityType
    start: int
    end: int
    sources: list[str] = field(default_factory=list)
    confidence: float = 1.0
    canonical_id: str | None = None
    predefined_token: str | None = None
    parent_canonical_id: str | None = None


@dataclass(slots=True)
class MaskHit:
    """
    One applied masking replacement.

    ``source`` holds the primary (winning) detector label for display.
    ``sources`` holds the full provenance set from all detectors that fired on
    this span; exported to mapping.json as ``row["sources"]``.
    """

    original_text: str
    token: str
    entity_type: EntityType
    original_start: int
    original_end: int
    source: str
    canonical_id: str | None = None
    parent_canonical_id: str | None = None
    sources: tuple[str, ...] = ()
    shift_days: int | None = None


@dataclass(slots=True)
class MaskedBlock:
    """
    One privacy-transformed block (prepare_analysis engine output).
    """

    block_id: str
    original_text: str
    masked_text: str
    mask_hits: list[MaskHit] = field(default_factory=list)


@dataclass(slots=True)
class MaskResult:
    """
    Privacy engine result for one document (audit payload / ``privacy_audit.json``).
    """

    doc_id: str
    masked_blocks: list[MaskedBlock] = field(default_factory=list)
    mapping: dict[str, Any] = field(default_factory=dict)
    date_shift: dict[str, object] = field(default_factory=dict)
    detectors: list[str] = field(default_factory=list)
    privacy_mode: Literal["none", "transform"] = "none"
