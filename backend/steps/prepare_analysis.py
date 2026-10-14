"""Neutral canonical Prepare Analysis execution step."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from artifacts.prepare_analysis import (
    ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW,
    ANALYSIS_BUNDLE_SCHEMA_VERSION_IDENTITY,
    BLOCK_GROUPS,
    build_analysis_bundle_artifact,
    requires_canonical_sentence_normalized_text,
    resolve_prepare_sentence_normalized_text,
    validate_prepare_analysis_input,
    validate_prepare_analysis_result,
)
from core.document.structure.analysis_heading_projection import (
    project_analysis_heading_paths,
)
from operations.prepare_analysis.contracts import (
    AnalysisBundleResult,
    ResolvedPrepareAnalysisPlan,
)
from privacy.config import PRIVACY_TRANSFORM_SLOTS, PrivacyConfig
from privacy.document_transform import build_analysis_bundle_dict, to_dict
from privacy.schemas import MaskResult
from privacy.transform import apply_privacy_transform


def _block_normalized_text(block: Mapping[str, Any]) -> str:
    value = (
        block["normalized_text"]
        if "normalized_text" in block
        else block.get("text", "")
    )
    return str(value or "")


def _identity_privacy_metadata(
    *,
    requested_detector_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Bundle-level privacy fields for privacy-off identity representation."""

    configured_after_extract = list(requested_detector_ids)
    privacy_enabled = bool(configured_after_extract)
    transforms: dict[str, Any] = {}
    for slot in PRIVACY_TRANSFORM_SLOTS:
        if slot == "after_extract":
            transforms[slot] = {
                "detectors": configured_after_extract,
                "applied": False,
                "detectors_used": [],
            }
        else:
            transforms[slot] = {
                "detectors": [],
                "applied": False,
            }
    return {
        "privacy_enabled": privacy_enabled,
        "privacy_transforms": transforms,
    }


def _enrich_sentences_identity(
    sentences: list[Any],
    *,
    canonical_sentence_payload_required: bool,
    block_path: str,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for index, sentence in enumerate(sentences):
        if not isinstance(sentence, dict):
            continue
        sentence_path = f"{block_path}.sentences[{index}]"
        sent = deepcopy(sentence)
        sentence_id = sent.get("sentence_id")
        sent_norm = resolve_prepare_sentence_normalized_text(
            sent,
            sentence_path=sentence_path,
            canonical_sentence_payload_required=canonical_sentence_payload_required,
        )
        sent.pop("raw_text", None)
        sent.pop("text", None)
        sent.pop("start", None)
        sent.pop("end", None)
        sent.pop("span_map", None)
        if sentence_id is not None:
            sent["sentence_id"] = sentence_id
        sent["normalized_text"] = sent_norm
        sent["analysis_text"] = sent_norm
        enriched.append(sent)
    return enriched


def _build_identity_analysis_block(
    block: Mapping[str, Any],
    *,
    canonical_sentence_payload_required: bool,
    block_path: str,
) -> dict[str, Any]:
    normalized_text = _block_normalized_text(block)
    analysis_text = normalized_text

    new_block = deepcopy(dict(block))
    new_block.pop("text", None)
    new_block.pop("raw_text", None)
    new_block.pop("span_map", None)
    new_block["normalized_text"] = normalized_text
    new_block["analysis_text"] = analysis_text

    sentences = block.get("sentences")
    if isinstance(sentences, list) and sentences:
        new_block["sentences"] = _enrich_sentences_identity(
            sentences,
            canonical_sentence_payload_required=canonical_sentence_payload_required,
            block_path=block_path,
        )
    return new_block


def _build_identity_analysis_representation(
    bundle: Mapping[str, Any],
    *,
    resolved_plan: ResolvedPrepareAnalysisPlan,
    analysis_bundle_id: str | None = None,
) -> dict[str, Any]:
    """Materialize Prepare-owned identity analysis semantics for privacy-off runs."""

    out: dict[str, Any] = {
        "doc_id": bundle.get("doc_id"),
        "file_name": bundle.get("file_name"),
        "display_name": bundle.get("display_name"),
        "file_hash": bundle.get("file_hash"),
        "created_at": bundle.get("created_at"),
        "source_type": bundle.get("source_type"),
        "document_meta": deepcopy(bundle.get("document_meta") or {}),
        "stage": "prepare_analysis",
        "pipeline": ["extract", "prepare_analysis"],
        "analysis_bundle_schema_version": ANALYSIS_BUNDLE_SCHEMA_VERSION_IDENTITY,
        "analysis_bundle_contract": ANALYSIS_BUNDLE_CONTRACT_LOCAL_RAW,
    }
    for key, value in resolved_plan.result_extension_values.items():
        if key in out:
            raise ValueError(f"result extension collides with base field: {key}")
        out[key] = deepcopy(value)
    out.update(
        _identity_privacy_metadata(
            requested_detector_ids=resolved_plan.requested_detector_ids,
        )
    )

    canonical_sentence_payload_required = requires_canonical_sentence_normalized_text(
        bundle
    )

    for group in BLOCK_GROUPS:
        analysis_group: list[dict[str, Any]] = []
        for index, block in enumerate(bundle.get(group) or []):
            if not isinstance(block, Mapping):
                continue
            analysis_group.append(
                _build_identity_analysis_block(
                    block,
                    canonical_sentence_payload_required=(
                        canonical_sentence_payload_required
                    ),
                    block_path=f"bundle.{group}[{index}]",
                )
            )
        out[group] = analysis_group

    if analysis_bundle_id is not None:
        out = {"analysis_bundle_id": analysis_bundle_id, **out}

    return out


def _identity_analysis_from_plan(
    bundle: dict[str, Any],
    *,
    resolved_plan: ResolvedPrepareAnalysisPlan,
    analysis_bundle_id: str | None,
) -> AnalysisBundleResult:
    """Materialize identity analysis without masked-privacy execution setup."""

    analysis_bundle = _build_identity_analysis_representation(
        bundle,
        resolved_plan=resolved_plan,
        analysis_bundle_id=analysis_bundle_id,
    )
    return AnalysisBundleResult(
        doc_id=str(bundle.get("doc_id") or ""),
        analysis_bundle=analysis_bundle,
        mask_result=None,
        block_audit_surfaces=[],
    )


def prepare_analysis_bundle(
    bundle: dict[str, Any],
    *,
    resolved_plan: ResolvedPrepareAnalysisPlan,
    analysis_bundle_id: str | None = None,
) -> AnalysisBundleResult:
    """Execute one already-resolved Prepare Analysis plan over Extract input."""

    if not isinstance(resolved_plan, ResolvedPrepareAnalysisPlan):
        raise TypeError("resolved_plan must satisfy ResolvedPrepareAnalysisPlan")
    validate_prepare_analysis_input(bundle)
    if not resolved_plan.privacy_enabled:
        step_result = _identity_analysis_from_plan(
            bundle,
            resolved_plan=resolved_plan,
            analysis_bundle_id=analysis_bundle_id,
        )
    else:
        privacy_config = PrivacyConfig.default().with_transform_detectors(
            "after_extract",
            list(resolved_plan.requested_detector_ids),
        )
        transform_result = apply_privacy_transform(
            bundle,
            "after_extract",
            privacy_config,
            mapping_store=resolved_plan.new_mapping_store(),
            profile=resolved_plan.build_privacy_profile(),
            detector=resolved_plan.build_detector(),
            analysis_bundle_id=analysis_bundle_id,
            date_shift_offset_days=resolved_plan.date_shift_offset_days,
            result_extensions=resolved_plan.result_extension_values,
            resolved_detector_ids=resolved_plan.effective_detector_ids,
        )
        step_result = AnalysisBundleResult(
            doc_id=transform_result.doc_id,
            analysis_bundle=transform_result.analysis_bundle,
            mask_result=transform_result.mask_result,
            block_audit_surfaces=list(transform_result.block_audit_surfaces),
            heading_projection=None,
        )
    analysis_bundle = build_analysis_bundle_artifact(step_result.analysis_bundle)
    heading_projection = project_analysis_heading_paths(analysis_bundle)
    formal_result = AnalysisBundleResult(
        doc_id=step_result.doc_id,
        analysis_bundle=analysis_bundle,
        mask_result=step_result.mask_result,
        block_audit_surfaces=list(step_result.block_audit_surfaces),
        heading_projection=heading_projection,
    )
    validate_prepare_analysis_result(formal_result)
    resolved_plan.validate_result_extension(formal_result.analysis_bundle)
    return formal_result


def privacy_audit_to_dict(result: MaskResult) -> dict[str, Any]:
    """Serialize privacy audit payload (written as `privacy_audit.json`)."""

    return to_dict(result)


def analysis_bundle_to_dict(result: AnalysisBundleResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "doc_id": result.doc_id,
        "analysis_bundle": result.analysis_bundle,
    }
    if result.mask_result is not None:
        payload["privacy_audit"] = privacy_audit_to_dict(result.mask_result)
    return payload


__all__ = [
    "AnalysisBundleResult",
    "analysis_bundle_to_dict",
    "build_analysis_bundle_dict",
    "prepare_analysis_bundle",
    "privacy_audit_to_dict",
]
