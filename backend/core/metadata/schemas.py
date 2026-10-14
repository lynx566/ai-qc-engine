from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Confidence = Literal["high", "medium", "low", "none"]
ContextStrategy = Literal["first_n_content_blocks", "metadata_sources_v0_1"]
DocTypeSource = Literal["file_name", "document_context_blocks"]
MetadataSourceType = Literal[
    "file_name",
    "display_name",
    "title_block",
    "heading",
    "early_block",
]


@dataclass(frozen=True)
class MetadataContextConfig:
    strategy: ContextStrategy = "metadata_sources_v0_1"
    default_block_count: int = 20
    doc_type_source_priority: tuple[str, ...] = (
        "file_name",
        "display_name",
        "title_block",
        "heading",
        "early_block",
    )


@dataclass(frozen=True)
class DocumentContextBlock:
    block_id: str
    kind: str
    text: str
    order: int | None = None


@dataclass(frozen=True)
class MetadataRule:
    field_name: str
    pattern: str
    confidence: Confidence = "high"
    flags: int = 0
    source_types: tuple[str, ...] | None = None
    multi: bool = False
    """If True, collect all regex matches (findall) instead of stopping at the first."""


@dataclass(frozen=True)
class DocTypeRule:
    doc_type: str
    pattern: str
    confidence: Confidence = "high"
    flags: int = 0
    source: DocTypeSource = "document_context_blocks"


@dataclass(frozen=True)
class DocTypeFieldPolicy:
    enabled_fields: list[str]
    required_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MetadataProfile:
    name: str
    context: MetadataContextConfig
    doc_type_rules: list[DocTypeRule]
    field_rules: list[MetadataRule]
    default_doc_type: str | None = None
    doc_type_field_policies: dict[str, DocTypeFieldPolicy] = field(default_factory=dict)


@dataclass(frozen=True)
class MetadataSource:
    source_id: str
    source_type: str
    text: str
    block_id: str | None = None
    kind: str | None = None
    order: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetadataEvidence:
    source_type: str
    source_id: str
    source_text: str
    block_id: str | None = None
    matched_rule: str | None = None
    priority_rank: int | None = None


@dataclass
class MetadataField:
    value: str | None = None
    confidence: Confidence = "none"
    source_block_ids: list[str] = field(default_factory=list)
    source_texts: list[str] = field(default_factory=list)
    evidence: list[MetadataEvidence] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    """All matched values when the rule uses multi=True; otherwise empty."""


@dataclass
class MetadataResult:
    doc_id: str
    profile: str
    context_strategy: str
    context_block_count: int
    doc_type: MetadataField = field(default_factory=MetadataField)
    fields: dict[str, MetadataField] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
