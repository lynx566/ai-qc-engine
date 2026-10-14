from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from artifacts.prepare_analysis import (
    ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW,
    ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED,
    ANALYSIS_BUNDLE_SCHEMA_VERSION_IDENTITY,
    ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC,
    requires_canonical_sentence_normalized_text,
    resolve_prepare_sentence_normalized_text,
)

from privacy.date_shift import DateShiftConfig, DateShifter
from privacy.detectors.base import SensitiveEntityDetector
from privacy.detectors.composite import CompositeDetector
from privacy.detectors.factory import build_mask_detectors
from privacy.mapping_store import MappingStore, export_mapping_artifact
from privacy.masker import mask_block, mask_text
from privacy.merger import merge_candidates
from privacy.policy import filter_candidates_by_profile
from privacy.profile import PrivacyProfile, default_privacy_profile
from privacy.schemas import MaskedBlock, MaskHit, MaskResult


BUNDLE_BLOCK_GROUPS: tuple[str, ...] = (
    "front_matter_blocks",
    "content_blocks",
    "table_blocks",
    "format_blocks",
)

_PUBLIC_BLOCK_META_KEYS: frozenset[str] = frozenset(
    {
        "heading_level",
        "heading_number",
        "row_count",
        "column_count",
        "non_empty_row_count",
        "style_name",
    }
)

_META_AUDIT_KEYS: tuple[str, ...] = (
    "raw_text_before_normalize",
    "raw_rows",
    "table_ref_candidates",
    "raw_text_changed_by_normalize",
    "has_internal_newlines",
)


def _split_file_name_for_mask(file_name: str) -> tuple[str, str]:
    """Return (stem, suffix) preserving compound suffixes such as ``.tar.gz``."""
    path = Path(file_name)
    suffix = "".join(path.suffixes)
    if suffix and path.name.endswith(suffix):
        stem = path.name[: len(path.name) - len(suffix)]
    else:
        stem = path.name
        suffix = ""
    return stem, suffix


def mask_identity_text(
    raw_text: str,
    *,
    detector: SensitiveEntityDetector,
    profile: PrivacyProfile | None,
    mapping_store: MappingStore,
    date_shifter: DateShifter | None = None,
) -> tuple[str, list[MaskHit]]:
    """
    Mask a short identity string (filename stem or display name) using the same
    detector → profile filter → merger → mapping_store → replace path as blocks.
    """
    text = str(raw_text)
    if not text.strip():
        return text, []

    candidates = detector.detect(text)
    if profile is not None:
        candidates = filter_candidates_by_profile(
            candidates,
            entity_types_to_mask=profile.entity_types_to_mask,
            entity_types_to_keep=profile.entity_types_to_keep,
        )
    merged_entities = merge_candidates(candidates)
    masked_text, hits = mask_text(
        raw_text=text,
        entities=merged_entities,
        mapping_store=mapping_store,
        date_shifter=date_shifter,
    )
    return masked_text, hits


def _mask_sentence_normalized_text(
    normalized_text: str,
    *,
    detector: SensitiveEntityDetector,
    profile: PrivacyProfile | None,
    mapping_store: MappingStore,
    date_shifter: DateShifter | None = None,
) -> str:
    """Sentence-owned privacy transform using shared semantic mapping state."""

    if not normalized_text:
        return normalized_text

    candidates = detector.detect(normalized_text)
    if profile is not None:
        candidates = filter_candidates_by_profile(
            candidates,
            entity_types_to_mask=profile.entity_types_to_mask,
            entity_types_to_keep=profile.entity_types_to_keep,
        )
    merged_entities = merge_candidates(candidates)
    masked_text, _hits = mask_text(
        normalized_text,
        merged_entities,
        mapping_store,
        date_shifter=date_shifter,
    )
    return masked_text


def sanitize_document_identity_for_mask(
    *,
    file_name: object,
    display_name: object,
    document_meta: dict[str, Any] | None,
    detector: SensitiveEntityDetector,
    profile: PrivacyProfile | None,
    mapping_store: MappingStore,
    date_shifter: DateShifter | None = None,
) -> tuple[str | None, str | None, dict[str, Any], list[MaskHit]]:
    """
    Mask bundle-level identity fields and clear upload paths from document_meta.

    Uses the same document-level ``mapping_store`` as block masking so tokens stay
    consistent (e.g. VT8802 → StudyDrug_001 in body and filename).
    """
    meta = deepcopy(document_meta or {})
    if "source_path" in meta:
        meta["source_path"] = None

    identity_hits: list[MaskHit] = []
    masked_display: str | None = None
    if display_name is not None:
        raw_display = str(display_name).strip()
        if raw_display:
            masked_display, hits = mask_identity_text(
                raw_display,
                detector=detector,
                profile=profile,
                mapping_store=mapping_store,
                date_shifter=date_shifter,
            )
            identity_hits.extend(hits)

    masked_file_name: str | None = None
    if file_name is not None:
        raw_file = str(file_name).strip()
        if raw_file:
            stem, suffix = _split_file_name_for_mask(raw_file)
            masked_stem, hits = mask_identity_text(
                stem,
                detector=detector,
                profile=profile,
                mapping_store=mapping_store,
                date_shifter=date_shifter,
            )
            identity_hits.extend(hits)
            masked_file_name = f"{masked_stem}{suffix}"

    return masked_file_name, masked_display, meta, identity_hits


def collect_mask_hits(
    mask_result: MaskResult,
    identity_hits: list[MaskHit] | None = None,
) -> list[MaskHit]:
    """All applied replacements (blocks + optional identity fields)."""
    hits: list[MaskHit] = []
    for block in mask_result.masked_blocks:
        hits.extend(block.mask_hits)
    if identity_hits:
        hits.extend(identity_hits)
    return hits


@dataclass
class MaskBundleResult:
    """Document-level privacy transform output."""

    doc_id: str
    analysis_bundle: dict[str, Any]
    mask_result: MaskResult
    block_audit_surfaces: list[dict[str, Any]] = field(default_factory=list)
    heading_projection: Any | None = None


def document_date_shifter(*, offset_days: int) -> DateShifter:
    return DateShifter(DateShiftConfig(offset_days=offset_days))


def date_shift_summary(*, offset_days: int) -> dict[str, object]:
    enabled = offset_days != 0
    return {"enabled": enabled, "offset_days": offset_days}


def resolve_date_shift(
    *, offset_days: int
) -> tuple[DateShifter | None, dict[str, object]]:
    meta = date_shift_summary(offset_days=offset_days)
    if not meta["enabled"]:
        return None, meta
    return document_date_shifter(offset_days=offset_days), meta


def _get_block_id(block: Any) -> str:
    if isinstance(block, dict):
        return str(block.get("block_id") or block.get("id") or "")
    return str(getattr(block, "block_id", getattr(block, "id", "")))


def _get_block_normalized_text(block: Any) -> str:
    if isinstance(block, dict):
        if "normalized_text" in block:
            value = block["normalized_text"]
        elif "text" in block:  # Legacy Extract artifact compatibility only.
            value = block["text"]
        else:
            value = block.get("content", "")
        return str(value or "")

    if hasattr(block, "normalized_text"):
        value = block.normalized_text
    elif hasattr(block, "text"):  # Legacy Extract-like object compatibility only.
        value = block.text
    else:
        value = getattr(block, "content", "")
    return str(value or "")


def iter_bundle_blocks(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """All blocks from the four bundle groups in stable order."""
    blocks: list[dict[str, Any]] = []
    for group in BUNDLE_BLOCK_GROUPS:
        for block in bundle.get(group) or []:
            if isinstance(block, dict):
                blocks.append(block)
    return blocks


def _empty_mapping_artifact(*, doc_id: str) -> dict[str, Any]:
    return export_mapping_artifact(
        doc_id=doc_id,
        mapping_store=MappingStore(),
        mask_hits=[],
    )


def _run_noop(
    *,
    doc_id: str,
    blocks: list[Any],
) -> MaskResult:
    """Passthrough mask: preserve text, emit analysis_bundle-compatible blocks."""
    masked_blocks: list[MaskedBlock] = []
    for block in blocks:
        block_id = _get_block_id(block)
        raw_text = _get_block_normalized_text(block)
        masked_blocks.append(
            MaskedBlock(
                block_id=block_id,
                original_text=raw_text,
                masked_text=raw_text,
                mask_hits=[],
            )
        )
    return MaskResult(
        doc_id=doc_id,
        masked_blocks=masked_blocks,
        mapping=_empty_mapping_artifact(doc_id=doc_id),
        date_shift={"enabled": False, "offset_days": 0},
        detectors=[],
        privacy_mode="none",
    )


def _mask_bundle_noop(
    bundle: dict[str, Any],
    *,
    privacy_config: Any | None = None,
    executed_slot: str = "after_extract",
    analysis_bundle_id: str | None = None,
    clinical_program_id: str | None = None,
    result_extensions: Mapping[str, Any] | None = None,
) -> MaskBundleResult:
    from privacy.config import PrivacyConfig

    config = privacy_config or PrivacyConfig()
    doc_id = str(bundle.get("doc_id") or "")
    flat_blocks = iter_bundle_blocks(bundle)
    mask_result = _run_noop(doc_id=doc_id, blocks=flat_blocks)
    mask_by_id = {mb.block_id: mb for mb in mask_result.masked_blocks}
    analysis_bundle, _audit_surfaces = build_analysis_artifact_pair(
        bundle,
        mask_by_id,
        privacy_config=config,
        executed_slot=executed_slot,  # type: ignore[arg-type]
        detectors_used=[],
        slot_applied=False,
        apply_replacement=False,
        analysis_bundle_id=analysis_bundle_id,
        slim_public=False,
        clinical_program_id=clinical_program_id,
        result_extensions=result_extensions,
    )
    return MaskBundleResult(
        doc_id=doc_id,
        analysis_bundle=analysis_bundle,
        mask_result=mask_result,
        block_audit_surfaces=[],
    )


def run(
    *,
    doc_id: str,
    blocks: list[Any],
    mapping_store: MappingStore | None = None,
    detector: SensitiveEntityDetector | None = None,
    profile: PrivacyProfile | None = None,
    language: str | None = None,
    apply_replacement: bool = True,
    date_shift_offset_days: int | None = None,
    registry_entries: Any = None,
) -> MaskResult:
    """
    Mask a flat list of blocks with one document-level :class:`MappingStore`.
    Prefer :func:`prepare_analysis_bundle` for full extract output.
    """
    if not apply_replacement:
        return _run_noop(doc_id=doc_id, blocks=blocks)

    store = mapping_store or MappingStore(
        token_prefixes=dict(profile.token_prefixes) if profile is not None else {}
    )
    effective_offset_days = date_shift_offset_days
    if effective_offset_days is None:
        if profile is None:
            profile = default_privacy_profile()
        if not store.token_prefixes and profile.token_prefixes:
            store.token_prefixes.update(profile.token_prefixes)
        effective_offset_days = profile.date_shift_offset_days
    shifter, shift_meta = resolve_date_shift(offset_days=effective_offset_days)
    if detector is not None:
        det = detector
        detector_kinds: list[str] = []
    else:
        if profile is None:
            profile = default_privacy_profile()
        built_detectors, detector_kinds = build_mask_detectors(
            profile=profile,
            language=language,
            registry_entries=registry_entries,
        )
        det = CompositeDetector(detectors=built_detectors)
    if profile is not None and not store.token_prefixes and profile.token_prefixes:
        store.token_prefixes.update(profile.token_prefixes)
    masked_blocks: list[MaskedBlock] = []

    mask_types = profile.entity_types_to_mask if profile is not None else frozenset()
    keep_types = profile.entity_types_to_keep if profile is not None else frozenset()

    for block in blocks:
        block_id = _get_block_id(block)
        raw_text = _get_block_normalized_text(block)

        candidates = det.detect(raw_text)
        candidates = filter_candidates_by_profile(
            candidates,
            entity_types_to_mask=mask_types,
            entity_types_to_keep=keep_types,
        )
        merged_entities = merge_candidates(candidates)

        masked = mask_block(
            block_id=block_id,
            raw_text=raw_text,
            entities=merged_entities,
            mapping_store=store,
            date_shifter=shifter,
        )

        masked_blocks.append(masked)

    all_hits = [hit for block in masked_blocks for hit in block.mask_hits]
    return MaskResult(
        doc_id=doc_id,
        masked_blocks=masked_blocks,
        mapping=export_mapping_artifact(
            doc_id=doc_id,
            mapping_store=store,
            mask_hits=all_hits,
        ),
        date_shift=shift_meta,
        detectors=detector_kinds,
        privacy_mode="transform" if apply_replacement else "none",
    )


def _enrich_sentences_with_analysis(
    sentences: list[Any],
    *,
    apply_replacement: bool,
    canonical_sentence_payload_required: bool,
    block_path: str,
    detector: SensitiveEntityDetector | None = None,
    profile: PrivacyProfile | None = None,
    mapping_store: MappingStore | None = None,
    date_shifter: DateShifter | None = None,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for index, sentence in enumerate(sentences):
        if not isinstance(sentence, dict):
            continue
        sentence_path = f"{block_path}.sentences[{index}]"
        sent = deepcopy(sentence)
        sentence_id = sent.get("sentence_id")
        sent.pop("raw_text", None)
        sent.pop("text", None)
        sent.pop("start", None)
        sent.pop("end", None)
        sent.pop("span_map", None)
        sent_norm = resolve_prepare_sentence_normalized_text(
            sent,
            sentence_path=sentence_path,
            canonical_sentence_payload_required=canonical_sentence_payload_required,
        )
        if apply_replacement and detector is not None and mapping_store is not None:
            sent_analysis = _mask_sentence_normalized_text(
                sent_norm,
                detector=detector,
                profile=profile,
                mapping_store=mapping_store,
                date_shifter=date_shifter,
            )
        else:
            sent_analysis = sent_norm
        if sentence_id is not None:
            sent["sentence_id"] = sentence_id
        sent["normalized_text"] = sent_norm
        sent["analysis_text"] = sent_analysis
        enriched.append(sent)
    return enriched


def _compute_block_analysis_fields(
    block: dict[str, Any],
    masked: MaskedBlock,
    *,
    apply_replacement: bool,
    canonical_sentence_payload_required: bool,
    block_path: str,
    detector: SensitiveEntityDetector | None = None,
    profile: PrivacyProfile | None = None,
    mapping_store: MappingStore | None = None,
    date_shifter: DateShifter | None = None,
) -> tuple[str, str, list[dict[str, Any]]]:
    normalized_text = masked.original_text
    analysis_text = masked.masked_text

    sentences = block.get("sentences")
    enriched_sentences: list[dict[str, Any]] = []
    if isinstance(sentences, list) and sentences:
        enriched_sentences = _enrich_sentences_with_analysis(
            sentences,
            apply_replacement=apply_replacement,
            canonical_sentence_payload_required=canonical_sentence_payload_required,
            block_path=block_path,
            detector=detector,
            profile=profile,
            mapping_store=mapping_store,
            date_shifter=date_shifter,
        )
    return normalized_text, analysis_text, enriched_sentences


def _meta_audit_from_block_meta(meta: dict[str, Any]) -> dict[str, Any]:
    audit: dict[str, Any] = {}
    for key in _META_AUDIT_KEYS:
        if key in meta:
            audit[key] = deepcopy(meta[key])
    return audit


def _strip_public_block_meta(meta: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(meta[key]) for key in _PUBLIC_BLOCK_META_KEYS if key in meta}


def _slim_sentences_for_public(
    enriched_sentences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    slim: list[dict[str, Any]] = []
    for sentence in enriched_sentences:
        entry: dict[str, Any] = {}
        for key in ("sentence_id", "analysis_text"):
            if key in sentence:
                entry[key] = sentence[key]
        slim.append(entry)
    return slim


def build_block_audit_surface(
    block: dict[str, Any],
    masked: MaskedBlock,
    *,
    apply_replacement: bool,
    canonical_sentence_payload_required: bool = False,
    block_path: str = "bundle.content_blocks[0]",
    detector: SensitiveEntityDetector | None = None,
    profile: PrivacyProfile | None = None,
    mapping_store: MappingStore | None = None,
    date_shifter: DateShifter | None = None,
) -> dict[str, Any]:
    """Raw-side audit entry from extract block + mask intermediate (pre-public slim)."""
    normalized_text, analysis_text, enriched_sentences = _compute_block_analysis_fields(
        block,
        masked,
        apply_replacement=apply_replacement,
        canonical_sentence_payload_required=canonical_sentence_payload_required,
        block_path=block_path,
        detector=detector,
        profile=profile,
        mapping_store=mapping_store,
        date_shifter=date_shifter,
    )
    entry: dict[str, Any] = {
        "block_id": block.get("block_id"),
        "kind": block.get("kind"),
        "normalized_text": normalized_text,
        "analysis_text": analysis_text,
    }
    if enriched_sentences:
        entry["sentences"] = enriched_sentences
    source_ref = block.get("source_ref")
    if source_ref is not None:
        entry["source_ref"] = deepcopy(source_ref)
    heading_path = block.get("heading_path")
    if isinstance(heading_path, list):
        entry["heading_path_extract"] = list(heading_path)
    meta = block.get("meta")
    if isinstance(meta, dict):
        meta_audit = _meta_audit_from_block_meta(meta)
        if meta_audit:
            entry["meta_audit"] = meta_audit
    return entry


def build_public_analysis_block(
    block: dict[str, Any],
    masked: MaskedBlock,
    *,
    apply_replacement: bool,
    slim: bool,
    canonical_sentence_payload_required: bool = False,
    block_path: str = "bundle.content_blocks[0]",
    detector: SensitiveEntityDetector | None = None,
    profile: PrivacyProfile | None = None,
    mapping_store: MappingStore | None = None,
    date_shifter: DateShifter | None = None,
) -> dict[str, Any]:
    _normalized_text, analysis_text, enriched_sentences = _compute_block_analysis_fields(
        block,
        masked,
        apply_replacement=apply_replacement,
        canonical_sentence_payload_required=canonical_sentence_payload_required,
        block_path=block_path,
        detector=detector,
        profile=profile,
        mapping_store=mapping_store,
        date_shifter=date_shifter,
    )
    if not slim:
        return _apply_analysis_fields_to_block(
            block,
            masked,
            apply_replacement=apply_replacement,
            canonical_sentence_payload_required=canonical_sentence_payload_required,
            block_path=block_path,
            detector=detector,
            profile=profile,
            mapping_store=mapping_store,
            date_shifter=date_shifter,
        )

    new_block: dict[str, Any] = {
        "block_id": block.get("block_id"),
        "kind": block.get("kind"),
        "analysis_text": analysis_text,
    }
    for key in ("loc", "order", "doc_order_index", "page_no"):
        if block.get(key) is not None:
            new_block[key] = block[key]
    meta = block.get("meta")
    if isinstance(meta, dict):
        public_meta = _strip_public_block_meta(meta)
        if public_meta:
            new_block["meta"] = public_meta
    if enriched_sentences:
        new_block["sentences"] = _slim_sentences_for_public(enriched_sentences)
    return new_block


def _apply_analysis_fields_to_block(
    block: dict[str, Any],
    masked: MaskedBlock,
    *,
    apply_replacement: bool,
    canonical_sentence_payload_required: bool = False,
    block_path: str = "bundle.content_blocks[0]",
    detector: SensitiveEntityDetector | None = None,
    profile: PrivacyProfile | None = None,
    mapping_store: MappingStore | None = None,
    date_shifter: DateShifter | None = None,
) -> dict[str, Any]:
    normalized_text, analysis_text, enriched_sentences = _compute_block_analysis_fields(
        block,
        masked,
        apply_replacement=apply_replacement,
        canonical_sentence_payload_required=canonical_sentence_payload_required,
        block_path=block_path,
        detector=detector,
        profile=profile,
        mapping_store=mapping_store,
        date_shifter=date_shifter,
    )

    new_block = deepcopy(block)
    new_block.pop("text", None)
    new_block.pop("raw_text", None)
    new_block.pop("span_map", None)
    new_block["normalized_text"] = normalized_text
    new_block["analysis_text"] = analysis_text

    if enriched_sentences:
        new_block["sentences"] = enriched_sentences

    meta = new_block.get("meta")
    if isinstance(meta, dict) and apply_replacement:
        meta.pop("heading_text_stripped", None)
    return new_block


def build_analysis_artifact_pair(
    bundle: dict[str, Any],
    mask_by_id: dict[str, MaskedBlock],
    *,
    file_name: str | None = None,
    display_name: str | None = None,
    document_meta: dict[str, Any] | None = None,
    privacy_config: Any | None = None,
    executed_slot: Any = "after_extract",
    detectors_used: list[str] | None = None,
    slot_applied: bool = True,
    apply_replacement: bool = True,
    analysis_bundle_id: str | None = None,
    slim_public: bool = False,
    clinical_program_id: str | None = None,
    result_extensions: Mapping[str, Any] | None = None,
    sentence_mask_detector: SensitiveEntityDetector | None = None,
    sentence_mask_profile: PrivacyProfile | None = None,
    sentence_mask_store: MappingStore | None = None,
    sentence_mask_shifter: DateShifter | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Build public analysis_bundle and optional per-block audit surfaces.

    When ``slim_public`` is True (privacy transform applied), public blocks omit
    pre-mask fields; audit surfaces carry the raw side for private_audit_bundle.
    """
    from privacy.config import PrivacyConfig

    config = privacy_config or PrivacyConfig()
    resolved_used = list(detectors_used or [])
    out: dict[str, Any] = {
        "doc_id": bundle.get("doc_id"),
        "file_name": file_name if file_name is not None else bundle.get("file_name"),
        "display_name": (
            display_name if display_name is not None else bundle.get("display_name")
        ),
        "file_hash": bundle.get("file_hash"),
        "created_at": bundle.get("created_at"),
        "source_type": bundle.get("source_type"),
        "document_meta": deepcopy(
            document_meta
            if document_meta is not None
            else bundle.get("document_meta") or {}
        ),
        "stage": "prepare_analysis",
        "pipeline": ["extract", "prepare_analysis"],
    }
    if clinical_program_id is not None:
        out["clinical_program_id"] = clinical_program_id
    for key, value in (result_extensions or {}).items():
        if key in out:
            raise ValueError(f"result extension collides with base field: {key}")
        out[key] = deepcopy(value)
    out.update(
        config.bundle_privacy_metadata(
            executed_slot=executed_slot,
            detectors_used=resolved_used,
            slot_applied=slot_applied,
        )
    )
    if slim_public:
        out["analysis_bundle_schema_version"] = ANALYSIS_BUNDLE_SCHEMA_VERSION_PUBLIC
        out["analysis_bundle_contract"] = ANALYSIS_BUNDLE_CONTRACT_PUBLIC_MASKED
    else:
        out["analysis_bundle_schema_version"] = ANALYSIS_BUNDLE_SCHEMA_VERSION_IDENTITY
        out["analysis_bundle_contract"] = ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW

    audit_surfaces: list[dict[str, Any]] = []
    canonical_sentence_payload_required = requires_canonical_sentence_normalized_text(
        bundle
    )
    for group in BUNDLE_BLOCK_GROUPS:
        analysis_group: list[dict[str, Any]] = []
        for index, block in enumerate(bundle.get(group) or []):
            if not isinstance(block, dict):
                continue
            block_id = _get_block_id(block)
            block_path = f"bundle.{group}[{index}]"
            masked = mask_by_id.get(block_id)
            if masked is None:
                raise KeyError(f"no mask result for block_id={block_id!r}")
            if slim_public:
                audit_surfaces.append(
                    build_block_audit_surface(
                        block,
                        masked,
                        apply_replacement=apply_replacement,
                        canonical_sentence_payload_required=(
                            canonical_sentence_payload_required
                        ),
                        block_path=block_path,
                        detector=sentence_mask_detector,
                        profile=sentence_mask_profile,
                        mapping_store=sentence_mask_store,
                        date_shifter=sentence_mask_shifter,
                    )
                )
                analysis_group.append(
                    build_public_analysis_block(
                        block,
                        masked,
                        apply_replacement=apply_replacement,
                        slim=True,
                        canonical_sentence_payload_required=(
                            canonical_sentence_payload_required
                        ),
                        block_path=block_path,
                        detector=sentence_mask_detector,
                        profile=sentence_mask_profile,
                        mapping_store=sentence_mask_store,
                        date_shifter=sentence_mask_shifter,
                    )
                )
            else:
                analysis_group.append(
                    build_public_analysis_block(
                        block,
                        masked,
                        apply_replacement=apply_replacement,
                        slim=False,
                        canonical_sentence_payload_required=(
                            canonical_sentence_payload_required
                        ),
                        block_path=block_path,
                        detector=sentence_mask_detector,
                        profile=sentence_mask_profile,
                        mapping_store=sentence_mask_store,
                        date_shifter=sentence_mask_shifter,
                    )
                )
        out[group] = analysis_group

    if analysis_bundle_id is not None:
        return {"analysis_bundle_id": analysis_bundle_id, **out}, audit_surfaces
    return out, audit_surfaces


def build_analysis_bundle_dict(
    bundle: dict[str, Any],
    mask_by_id: dict[str, MaskedBlock],
    *,
    file_name: str | None = None,
    display_name: str | None = None,
    document_meta: dict[str, Any] | None = None,
    privacy_config: Any | None = None,
    executed_slot: Any = "after_extract",
    detectors_used: list[str] | None = None,
    slot_applied: bool = True,
    apply_replacement: bool = True,
    analysis_bundle_id: str | None = None,
    slim_public: bool | None = None,
    clinical_program_id: str | None = None,
    result_extensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build analysis_bundle for downstream filter/tag (privacy/analysis contract).

    Identity / noop runs retain ``normalized_text`` and ``analysis_text``.
    Privacy-transform runs with ``slim_public=True`` emit masked public blocks only.
    """
    if slim_public is None:
        slim_public = slot_applied and apply_replacement
    public_bundle, _audit_surfaces = build_analysis_artifact_pair(
        bundle,
        mask_by_id,
        file_name=file_name,
        display_name=display_name,
        document_meta=document_meta,
        privacy_config=privacy_config,
        executed_slot=executed_slot,
        detectors_used=detectors_used,
        slot_applied=slot_applied,
        apply_replacement=apply_replacement,
        analysis_bundle_id=analysis_bundle_id,
        slim_public=slim_public,
        clinical_program_id=clinical_program_id,
        result_extensions=result_extensions,
    )
    return public_bundle


def to_dict(result: MaskResult) -> dict[str, Any]:
    return asdict(result)
