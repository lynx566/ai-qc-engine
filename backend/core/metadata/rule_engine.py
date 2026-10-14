from __future__ import annotations

import re

from .metadata_sources import (
    DEFAULT_FIELD_SOURCE_TYPES,
    build_metadata_sources,
    context_block_source_types,
    sources_by_type,
)
from .schemas import (
    Confidence,
    DocTypeRule,
    DocumentContextBlock,
    MetadataEvidence,
    MetadataField,
    MetadataProfile,
    MetadataResult,
    MetadataRule,
    MetadataSource,
)


def doc_type_rule_id(rule: DocTypeRule) -> str:
    pattern_key = rule.pattern.replace("\n", "")[:48]
    return f"doc_type:{rule.doc_type}:{pattern_key}"


def field_rule_id(rule: MetadataRule) -> str:
    pattern_key = rule.pattern.replace("\n", "")[:48]
    return f"field:{rule.field_name}:{pattern_key}"


def _doc_type_rule_applies_to_source_type(rule: DocTypeRule, source_type: str) -> bool:
    """
    DocTypeRule.source semantics:

    - ``file_name``: only ``file_name`` and ``display_name`` metadata sources.
    - ``document_context_blocks`` (default): unrestricted — all metadata source types.
    """
    if rule.source == "file_name":
        return source_type in ("file_name", "display_name")
    if rule.source == "document_context_blocks":
        return source_type in ("file_name", "display_name") or source_type in context_block_source_types()
    return False


def _doc_type_rules_for_metadata_source_type(
    profile: MetadataProfile,
    source_type: str,
) -> list[DocTypeRule]:
    return [
        rule
        for rule in profile.doc_type_rules
        if _doc_type_rule_applies_to_source_type(rule, source_type)
    ]


def _field_rule_source_types(rule: MetadataRule) -> tuple[str, ...]:
    if rule.source_types is not None:
        return rule.source_types
    return DEFAULT_FIELD_SOURCE_TYPES


def _make_field_from_source(
    *,
    value: str,
    source: MetadataSource,
    confidence: Confidence,
    matched_rule: str,
    priority_rank: int | None = None,
) -> MetadataField:
    block_id = source.block_id
    source_text = source.text
    evidence = MetadataEvidence(
        source_type=source.source_type,
        source_id=source.source_id,
        source_text=source_text,
        block_id=block_id,
        matched_rule=matched_rule,
        priority_rank=priority_rank,
    )
    return MetadataField(
        value=value.strip(),
        confidence=confidence,
        source_block_ids=[block_id] if block_id else [],
        source_texts=[source_text],
        evidence=[evidence],
    )


def _make_multi_field_from_source(
    *,
    values: list[str],
    source: MetadataSource,
    confidence: Confidence,
    matched_rule: str,
) -> MetadataField:
    """Build a MetadataField from all findall matches on a single source."""
    block_id = source.block_id
    source_text = source.text
    evidence = MetadataEvidence(
        source_type=source.source_type,
        source_id=source.source_id,
        source_text=source_text,
        block_id=block_id,
        matched_rule=matched_rule,
    )
    stripped = [v.strip() for v in values if v.strip()]
    return MetadataField(
        value=stripped[0] if stripped else None,
        values=stripped,
        confidence=confidence,
        source_block_ids=[block_id] if block_id else [],
        source_texts=[source_text],
        evidence=[evidence],
    )


def _try_doc_type_on_source(
    source: MetadataSource,
    rules: list[DocTypeRule],
    *,
    priority_rank: int,
) -> MetadataField | None:
    for rule in rules:
        if re.search(rule.pattern, source.text, flags=rule.flags):
            return _make_field_from_source(
                value=rule.doc_type,
                source=source,
                confidence=rule.confidence,
                matched_rule=doc_type_rule_id(rule),
                priority_rank=priority_rank,
            )
    return None


def detect_doc_type_from_sources(
    sources: list[MetadataSource],
    profile: MetadataProfile,
    *,
    priority_override: tuple[str, ...] | None = None,
) -> tuple[MetadataField, list[str]]:
    priority = list(priority_override or profile.context.doc_type_source_priority)
    warnings: list[str] = []

    file_channel: MetadataField | None = None
    context_channel: MetadataField | None = None
    winner: MetadataField | None = None

    for rank, source_type in enumerate(priority, start=1):
        rules = _doc_type_rules_for_metadata_source_type(profile, source_type)
        if not rules:
            continue

        for source in sources_by_type(sources, source_type):
            hit = _try_doc_type_on_source(source, rules, priority_rank=rank)
            if hit is None:
                continue

            if source_type in ("file_name", "display_name"):
                if file_channel is None:
                    file_channel = hit
            elif source_type in context_block_source_types():
                if context_channel is None:
                    context_channel = hit

            if winner is None:
                winner = hit
            break

    if (
        file_channel
        and context_channel
        and file_channel.value
        and context_channel.value
        and file_channel.value != context_channel.value
    ):
        warnings.append("doc_type_conflict")

    if winner is not None:
        return winner, warnings

    if profile.default_doc_type:
        return MetadataField(value=profile.default_doc_type, confidence="low"), warnings

    return MetadataField(), warnings


_FIELD_SOURCE_PRIORITY: tuple[str, ...] = (
    "file_name",
    "display_name",
    "title_block",
    "heading",
    "early_block",
)


def _sources_in_field_priority_order(
    sources: list[MetadataSource],
    *,
    enabled_source_types: set[str],
) -> list[MetadataSource]:
    ordered: list[MetadataSource] = []
    for source_type in _FIELD_SOURCE_PRIORITY:
        if source_type not in enabled_source_types:
            continue
        ordered.extend(s for s in sources if s.source_type == source_type)
    return ordered


def _extract_field_from_sources(
    sources: list[MetadataSource],
    profile: MetadataProfile,
    *,
    field_name: str,
    enabled_source_types: set[str],
) -> MetadataField:
    for source in _sources_in_field_priority_order(
        sources,
        enabled_source_types=enabled_source_types,
    ):
        for rule in profile.field_rules:
            if rule.field_name != field_name:
                continue
            allowed = set(_field_rule_source_types(rule))
            if source.source_type not in allowed:
                continue

            if rule.multi:
                all_matches = re.findall(rule.pattern, source.text, flags=rule.flags)
                # findall returns strings when there is exactly one group
                values = [m if isinstance(m, str) else (m[0] if m else "") for m in all_matches]
                values = [v for v in values if v.strip()]
                if not values:
                    continue
                return _make_multi_field_from_source(
                    values=values,
                    source=source,
                    confidence=rule.confidence,
                    matched_rule=field_rule_id(rule),
                )

            match = re.search(rule.pattern, source.text, flags=rule.flags)
            if not match:
                continue

            value = match.groupdict().get("value")
            if not value:
                continue

            return _make_field_from_source(
                value=value,
                source=source,
                confidence=rule.confidence,
                matched_rule=field_rule_id(rule),
            )

    return MetadataField()


def extract_metadata(
    *,
    doc_id: str,
    metadata_sources: list[MetadataSource],
    profile: MetadataProfile,
    context_block_count: int,
) -> MetadataResult:
    result = MetadataResult(
        doc_id=doc_id,
        profile=profile.name,
        context_strategy=profile.context.strategy,
        context_block_count=context_block_count,
    )

    result.doc_type, doc_type_warnings = detect_doc_type_from_sources(
        metadata_sources,
        profile,
    )
    result.warnings.extend(doc_type_warnings)
    doc_type = result.doc_type.value

    enabled_fields = set(_enabled_fields_for_doc_type(doc_type, profile))

    for field_name in enabled_fields:
        result.fields[field_name] = MetadataField()

    for field_name in enabled_fields:
        allowed_types = set()
        for rule in profile.field_rules:
            if rule.field_name != field_name:
                continue
            allowed_types.update(_field_rule_source_types(rule))

        hit = _extract_field_from_sources(
            metadata_sources,
            profile,
            field_name=field_name,
            enabled_source_types=allowed_types,
        )
        if hit.value:
            result.fields[field_name] = hit

    if not result.doc_type.value:
        result.warnings.append("required field not found: doc_type")

    for field_name in _required_fields_for_doc_type(doc_type, profile):
        field = result.fields.get(field_name)
        if not field or not field.value:
            result.warnings.append(f"required field not found: {field_name}")

    return result


def extract_metadata_from_analysis_bundle(
    *,
    doc_id: str,
    analysis_bundle: dict,
    profile: MetadataProfile,
    context_block_count: int | None = None,
) -> tuple[MetadataResult, list[MetadataSource]]:
    effective_count = (
        context_block_count
        if context_block_count is not None
        else profile.context.default_block_count
    )
    sources = build_metadata_sources(
        analysis_bundle,
        context_block_count=effective_count,
    )
    result = extract_metadata(
        doc_id=doc_id,
        metadata_sources=sources,
        profile=profile,
        context_block_count=effective_count,
    )
    return result, sources


# ---- legacy helpers (tests / gradual migration) ----


def _make_field(
    value: str,
    block: DocumentContextBlock,
    confidence: Confidence,
) -> MetadataField:
    source = MetadataSource(
        source_id=f"legacy:{block.block_id}",
        source_type="early_block",
        text=block.text,
        block_id=block.block_id,
        kind=block.kind,
        order=block.order,
    )
    return _make_field_from_source(
        value=value,
        source=source,
        confidence=confidence,
        matched_rule="legacy:context_block",
    )


def _make_field_from_file_name(
    value: str,
    file_name: str,
    confidence: Confidence,
) -> MetadataField:
    source = MetadataSource(
        source_id="legacy:file_name",
        source_type="file_name",
        text=file_name,
    )
    return _make_field_from_source(
        value=value,
        source=source,
        confidence=confidence,
        matched_rule="legacy:file_name",
    )


def _detect_doc_type_in_text(
    text: str,
    rules: list[DocTypeRule],
) -> MetadataField | None:
    for rule in rules:
        if re.search(rule.pattern, text, flags=rule.flags):
            return MetadataField(
                value=rule.doc_type,
                confidence=rule.confidence,
            )
    return None


def detect_doc_type_from_file_name(
    file_name: str,
    profile: MetadataProfile,
) -> MetadataField:
    if not file_name:
        return MetadataField()

    sources = [
        MetadataSource(
            source_id="legacy:file_name",
            source_type="file_name",
            text=file_name,
        )
    ]
    field, _warnings = detect_doc_type_from_sources(sources, profile)
    return field


def detect_doc_type_from_context_blocks(
    context_blocks: list[DocumentContextBlock],
    profile: MetadataProfile,
) -> MetadataField:
    sources: list[MetadataSource] = []
    title_used = False
    for block in context_blocks:
        if block.kind == "heading":
            st = "heading"
        elif not title_used:
            st = "title_block"
            title_used = True
        else:
            st = "early_block"
        sources.append(
            MetadataSource(
                source_id=f"legacy:{st}:{block.block_id}",
                source_type=st,
                text=block.text,
                block_id=block.block_id,
                kind=block.kind,
                order=block.order,
            )
        )

    context_types = context_block_source_types()
    narrowed_priority = tuple(
        p
        for p in profile.context.doc_type_source_priority
        if p in context_types
    )
    field, _ = detect_doc_type_from_sources(
        sources,
        profile,
        priority_override=narrowed_priority,
    )

    if field.value:
        return field

    if profile.default_doc_type:
        return MetadataField(value=profile.default_doc_type, confidence="low")

    return MetadataField()


def detect_doc_type(
    context_blocks: list[DocumentContextBlock],
    profile: MetadataProfile,
    *,
    file_name: str = "",
) -> tuple[MetadataField, list[str]]:
    sources: list[MetadataSource] = []
    if file_name.strip():
        sources.append(
            MetadataSource(
                source_id="legacy:file_name",
                source_type="file_name",
                text=file_name.strip(),
            )
        )
    title_used = False
    for block in context_blocks:
        if block.kind == "heading":
            st = "heading"
        elif not title_used:
            st = "title_block"
            title_used = True
        else:
            st = "early_block"
        sources.append(
            MetadataSource(
                source_id=f"legacy:{st}:{block.block_id}",
                source_type=st,
                text=block.text,
                block_id=block.block_id,
                kind=block.kind,
                order=block.order,
            )
        )
    return detect_doc_type_from_sources(sources, profile)


def _enabled_fields_for_doc_type(
    doc_type: str | None,
    profile: MetadataProfile,
) -> list[str]:
    if doc_type and doc_type in profile.doc_type_field_policies:
        return profile.doc_type_field_policies[doc_type].enabled_fields

    return sorted({rule.field_name for rule in profile.field_rules})


def _required_fields_for_doc_type(
    doc_type: str | None,
    profile: MetadataProfile,
) -> list[str]:
    if doc_type and doc_type in profile.doc_type_field_policies:
        return profile.doc_type_field_policies[doc_type].required_fields

    return []


def extract_metadata_legacy(
    *,
    doc_id: str,
    context_blocks: list[DocumentContextBlock],
    profile: MetadataProfile,
    context_block_count: int,
    file_name: str = "",
) -> MetadataResult:
    """Backward-compatible wrapper over :func:`extract_metadata`."""
    sources: list[MetadataSource] = []
    if file_name.strip():
        sources.append(
            MetadataSource(
                source_id=f"{doc_id}:file_name",
                source_type="file_name",
                text=file_name.strip(),
            )
        )
    title_used = False
    for block in context_blocks[:context_block_count]:
        if block.kind == "heading":
            st = "heading"
        elif not title_used:
            st = "title_block"
            title_used = True
        else:
            st = "early_block"
        sources.append(
            MetadataSource(
                source_id=f"{doc_id}:{st}:{block.block_id}",
                source_type=st,
                text=block.text,
                block_id=block.block_id,
                kind=block.kind,
                order=block.order,
            )
        )
    return extract_metadata(
        doc_id=doc_id,
        metadata_sources=sources,
        profile=profile,
        context_block_count=context_block_count,
    )
