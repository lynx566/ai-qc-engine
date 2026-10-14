"""Neutral in-memory contracts for Filter-output projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from llm.invocation import LLMInvocationRecord


def _require_non_empty_str(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")


def _require_mapping(value: Any, *, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")


RAW_SOURCE_REPRESENTATION_KIND = "raw_source"
ASSEMBLED_SEMANTIC_REPRESENTATION_KIND = "assembled_semantic"
ALLOWED_PROJECTED_SOURCE_REPRESENTATION_KINDS = frozenset(
    {
        RAW_SOURCE_REPRESENTATION_KIND,
        ASSEMBLED_SEMANTIC_REPRESENTATION_KIND,
    }
)


@dataclass(frozen=True, slots=True)
class ResolvedFilterOutputProjectionJob:
    """Already-resolved projection job consumed mechanically by the Step."""

    filter_job_id: str
    strategy_id: str
    strategy_config: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.filter_job_id, field_name="filter_job_id")
        _require_non_empty_str(self.strategy_id, field_name="strategy_id")
        _require_mapping(self.strategy_config, field_name="strategy_config")


@dataclass(frozen=True, slots=True)
class CanonicalSourceRef:
    """Canonical source reference for projection provenance (strategy-neutral shape)."""

    refs: Mapping[str, str]

    def __post_init__(self) -> None:
        _require_mapping(self.refs, field_name="refs")
        block_id = self.refs.get("block_id")
        if not isinstance(block_id, str) or not block_id.strip():
            raise ValueError("canonical source ref must include non-empty block_id")


@dataclass(frozen=True, slots=True)
class ProjectionSourceSentence:
    """Canonical Prepare sentence payload at the Projection source boundary."""

    sentence_id: str
    text: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.sentence_id, field_name="sentence_id")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")


@dataclass(frozen=True, slots=True)
class ProjectedSentence:
    """Canonical sentence persisted on a ProjectedSource (schema 0.3.0+)."""

    sentence_id: str
    text: str
    source_block_id: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.sentence_id, field_name="sentence_id")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        _require_non_empty_str(self.source_block_id, field_name="source_block_id")


@dataclass(frozen=True, slots=True)
class ProjectionSourceBlock:
    """Canonical Prepare block payload at the Projection source boundary."""

    block_id: str
    kind: str
    heading_path: tuple[str, ...]
    source_group: str
    zone_id: str
    text: str
    sentences: tuple[ProjectionSourceSentence, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.block_id, field_name="block_id")
        _require_non_empty_str(self.kind, field_name="kind")
        _require_non_empty_str(self.source_group, field_name="source_group")
        _require_non_empty_str(self.zone_id, field_name="zone_id")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        if not isinstance(self.heading_path, tuple):
            raise TypeError("heading_path must be a tuple")
        for index, segment in enumerate(self.heading_path):
            if not isinstance(segment, str):
                raise TypeError(f"heading_path[{index}] must be a string")
        if not isinstance(self.sentences, tuple):
            raise TypeError("sentences must be a tuple")
        for index, sentence in enumerate(self.sentences):
            if not isinstance(sentence, ProjectionSourceSentence):
                raise TypeError(
                    f"sentences[{index}] must be a ProjectionSourceSentence"
                )


@dataclass(frozen=True, slots=True)
class FilterOutputProjectionInput:
    """Pure in-memory Filter semantic output consumed by projection."""

    filter_job_id: str
    doc_id: str
    file_hash: str
    zone_key: str
    zone_match_bundle: Mapping[str, Any]
    projection_sources: tuple[ProjectionSourceBlock, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.filter_job_id, field_name="filter_job_id")
        _require_non_empty_str(self.doc_id, field_name="doc_id")
        _require_non_empty_str(self.zone_key, field_name="zone_key")
        _require_mapping(self.zone_match_bundle, field_name="zone_match_bundle")
        if not isinstance(self.projection_sources, tuple):
            raise TypeError("projection_sources must be a tuple")
        for index, source in enumerate(self.projection_sources):
            if not isinstance(source, ProjectionSourceBlock):
                raise TypeError(
                    f"projection_sources[{index}] must be a ProjectionSourceBlock"
                )


@dataclass(frozen=True, slots=True)
class ProjectedSource:
    """Semantic projected source produced by a projection strategy."""

    semantic_module_id: str
    source_refs: tuple[CanonicalSourceRef, ...]
    representation_kind: str
    sentences: tuple[ProjectedSentence, ...]
    lineage: Mapping[str, str] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.semantic_module_id, field_name="semantic_module_id")
        _require_non_empty_str(
            self.representation_kind,
            field_name="representation_kind",
        )
        if self.representation_kind not in ALLOWED_PROJECTED_SOURCE_REPRESENTATION_KINDS:
            raise ValueError(
                "representation_kind must be one of: "
                + ", ".join(sorted(ALLOWED_PROJECTED_SOURCE_REPRESENTATION_KINDS))
            )
        if not isinstance(self.source_refs, tuple):
            raise TypeError("source_refs must be a tuple")
        for index, ref in enumerate(self.source_refs):
            if not isinstance(ref, CanonicalSourceRef):
                raise TypeError(
                    f"source_refs[{index}] must be a CanonicalSourceRef"
                )
        if not isinstance(self.sentences, tuple):
            raise TypeError("sentences must be a tuple")
        for index, sentence in enumerate(self.sentences):
            if not isinstance(sentence, ProjectedSentence):
                raise TypeError(
                    f"sentences[{index}] must be a ProjectedSentence"
                )
        _require_mapping(self.lineage, field_name="lineage")
        _require_mapping(self.payload, field_name="payload")


@dataclass(frozen=True, slots=True)
class SemanticProjectionOutcome:
    """Semantic classification or projection outcome for one canonical source."""

    semantic_module_id: str
    source_refs: tuple[CanonicalSourceRef, ...]
    strategy_result: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.semantic_module_id, field_name="semantic_module_id")
        if not isinstance(self.source_refs, tuple):
            raise TypeError("source_refs must be a tuple")
        for index, ref in enumerate(self.source_refs):
            if not isinstance(ref, CanonicalSourceRef):
                raise TypeError(
                    f"source_refs[{index}] must be a CanonicalSourceRef"
                )
        _require_mapping(self.strategy_result, field_name="strategy_result")


@dataclass(frozen=True, slots=True)
class FilterOutputProjectionStepResult:
    """Canonical in-memory result returned by the projection Step."""

    filter_job_id: str
    doc_id: str
    file_hash: str
    zone_key: str
    projected_sources: tuple[ProjectedSource, ...] = ()
    semantic_outcomes: tuple[SemanticProjectionOutcome, ...] = ()
    llm_invocations: tuple[LLMInvocationRecord, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_str(self.filter_job_id, field_name="filter_job_id")
        _require_non_empty_str(self.doc_id, field_name="doc_id")
        _require_non_empty_str(self.zone_key, field_name="zone_key")
        if not isinstance(self.projected_sources, tuple):
            raise TypeError("projected_sources must be a tuple")
        if not isinstance(self.semantic_outcomes, tuple):
            raise TypeError("semantic_outcomes must be a tuple")
        if not isinstance(self.llm_invocations, tuple):
            raise TypeError("llm_invocations must be a tuple")
        for index, source in enumerate(self.projected_sources):
            if not isinstance(source, ProjectedSource):
                raise TypeError(
                    f"projected_sources[{index}] must be a ProjectedSource"
                )
        for index, outcome in enumerate(self.semantic_outcomes):
            if not isinstance(outcome, SemanticProjectionOutcome):
                raise TypeError(
                    f"semantic_outcomes[{index}] must be a SemanticProjectionOutcome"
                )


@runtime_checkable
class FilterOutputProjectionFacade(Protocol):
    """Injected projection strategy boundary; Step does not branch on strategy_id."""

    def project(
        self,
        *,
        projection_input: FilterOutputProjectionInput,
        job: ResolvedFilterOutputProjectionJob,
    ) -> FilterOutputProjectionStepResult: ...


__all__ = [
    "ALLOWED_PROJECTED_SOURCE_REPRESENTATION_KINDS",
    "ASSEMBLED_SEMANTIC_REPRESENTATION_KIND",
    "RAW_SOURCE_REPRESENTATION_KIND",
    "CanonicalSourceRef",
    "FilterOutputProjectionFacade",
    "FilterOutputProjectionInput",
    "FilterOutputProjectionStepResult",
    "ProjectedSentence",
    "ProjectedSource",
    "ProjectionSourceBlock",
    "ProjectionSourceSentence",
    "ResolvedFilterOutputProjectionJob",
    "SemanticProjectionOutcome",
]
