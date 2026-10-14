"""
Unified privacy_transform entry for pipeline transform slots.

Scheduling reads ``config.transforms[slot].detectors`` only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from privacy.config import PrivacyConfig, PrivacyTransformSlot
from privacy.detectors.base import SensitiveEntityDetector
from privacy.detectors.composite import CompositeDetector
from privacy.detectors.factory import build_stage_detectors
from privacy.detectors.registry_detector import RegistryEntry
from privacy.document_transform import (
    _mask_bundle_noop,
    build_analysis_artifact_pair,
    collect_mask_hits,
    iter_bundle_blocks,
    resolve_date_shift,
    run,
    sanitize_document_identity_for_mask,
)
from privacy.mapping_store import MappingStore, export_mapping_artifact
from privacy.profile import PrivacyProfile, default_privacy_profile
from privacy.schemas import MaskResult

_MULTI_TRANSFORM_SLOTS: frozenset[PrivacyTransformSlot] = frozenset({"after_filter"})


@dataclass
class PrivacyTransformResult:
    """Output of :func:`apply_privacy_transform`."""

    doc_id: str
    analysis_bundle: dict[str, Any]
    mask_result: MaskResult
    privacy_transform_slot: PrivacyTransformSlot
    detectors_used: list[str]
    slot_applied: bool
    config: PrivacyConfig
    block_audit_surfaces: list[dict[str, Any]] = field(default_factory=list)


def apply_privacy_transform(
    bundle_or_analysis_bundle: dict[str, Any],
    slot: PrivacyTransformSlot,
    config: PrivacyConfig,
    *,
    mapping_store: MappingStore | None = None,
    profile: PrivacyProfile | None = None,
    language: str | None = None,
    detector: SensitiveEntityDetector | None = None,
    analysis_bundle_id: str | None = None,
    date_shift_offset_days: int | None = None,
    clinical_program_id: str | None = None,
    result_extensions: Mapping[str, Any] | None = None,
    registry_entries: Iterable[RegistryEntry] | None = None,
    resolved_detector_ids: Iterable[str] | None = None,
) -> PrivacyTransformResult:
    """
    Run privacy detectors for ``slot`` and return an analysis_bundle.

    Transform paths
    ---------------
    - **True noop**: ``detector_names`` is empty AND effective date_shift offset is 0
      → identity transform; ``analysis_text = normalized_text``, ``slot_applied=False``.
    - **Dates-only**: ``detector_names`` is empty BUT date_shift offset > 0
      (triggered by explicit ``--date-shift`` flag via runner)
      → only date shifts are applied; no entity masking.
    - **Full transform**: ``detector_names`` is non-empty
      → entity masking + date_shift (date_shift off only when offset == 0).

    ``mapping_store`` must be shared across transform slots so token allocation
    stays consistent when multi-transform composition is implemented.

    ``date_shift_offset_days`` is passed through to :func:`~privacy.document_transform.run`
    so block-level and identity-field date shifts use the same resolved offset
    (e.g. a clinical program override instead of the profile default).
    """
    detector_names = config.transform_detectors(slot)

    if slot in _MULTI_TRANSFORM_SLOTS and detector_names:
        raise NotImplementedError(
            "after_filter privacy transform requires span_map composition"
        )

    bundle = bundle_or_analysis_bundle
    doc_id = str(bundle.get("doc_id") or "")

    # Determine if a dates-only transform is requested.
    #
    # Only a positive EXPLICIT date_shift_offset_days argument (from the runner
    # via PrivacyRunConfig) triggers the dates-only path.  A None value means
    # "caller does not specify; use profile default if detectors are active".
    # This preserves backward compatibility: callers that pass profile+no-detectors
    # but omit date_shift_offset_days still get a true noop.
    _explicit_date_shift = (
        date_shift_offset_days is not None and date_shift_offset_days > 0
    )

    if not detector_names and not _explicit_date_shift:
        # True noop: no entity detectors, no explicit date_shift.
        noop = _mask_bundle_noop(
            bundle,
            privacy_config=config,
            executed_slot=slot,
            analysis_bundle_id=analysis_bundle_id,
            clinical_program_id=clinical_program_id,
            result_extensions=result_extensions,
        )
        return PrivacyTransformResult(
            doc_id=noop.doc_id,
            analysis_bundle=noop.analysis_bundle,
            mask_result=noop.mask_result,
            privacy_transform_slot=slot,
            detectors_used=[],
            slot_applied=False,
            config=config,
            block_audit_surfaces=[],
        )

    # From here: either detectors are active, or dates-only transform (offset > 0).
    if detector_names:
        profile = profile or default_privacy_profile()
        effective_offset_days = (
            date_shift_offset_days
            if date_shift_offset_days is not None
            else profile.date_shift_offset_days
        )
    else:
        effective_offset_days = date_shift_offset_days

    store = mapping_store or MappingStore(
        token_prefixes=dict(profile.token_prefixes) if profile is not None else {}
    )
    if profile is not None and not store.token_prefixes and profile.token_prefixes:
        store.token_prefixes.update(profile.token_prefixes)

    shifter, _shift_meta = resolve_date_shift(offset_days=effective_offset_days)

    if detector is not None:
        det = detector
        active_kinds = list(resolved_detector_ids or ())
    elif detector_names:
        built_detectors, active_kinds = build_stage_detectors(
            detector_names,
            profile=profile,
            language=language,
            registry_entries=registry_entries,
        )
        det = CompositeDetector(detectors=built_detectors)
    else:
        det = CompositeDetector(detectors=[])
        active_kinds = []

    flat_blocks = iter_bundle_blocks(bundle)
    mask_result = run(
        doc_id=doc_id,
        blocks=flat_blocks,
        mapping_store=store,
        detector=det,
        profile=profile,
        language=language,
        apply_replacement=True,
        date_shift_offset_days=effective_offset_days,
    )
    resolved_used = active_kinds or list(detector_names)
    mask_result = replace(
        mask_result,
        detectors=resolved_used,
        privacy_mode="transform",
    )

    (
        masked_file_name,
        masked_display_name,
        document_meta,
        identity_hits,
    ) = sanitize_document_identity_for_mask(
        file_name=bundle.get("file_name"),
        display_name=bundle.get("display_name"),
        document_meta=bundle.get("document_meta") or {},
        detector=det,
        profile=profile,
        mapping_store=store,
        date_shifter=shifter,
    )
    mask_result = replace(
        mask_result,
        mapping=export_mapping_artifact(
            doc_id=doc_id,
            mapping_store=store,
            mask_hits=collect_mask_hits(mask_result, identity_hits),
        ),
    )

    mask_by_id = {mb.block_id: mb for mb in mask_result.masked_blocks}
    analysis_bundle, block_audit_surfaces = build_analysis_artifact_pair(
        bundle,
        mask_by_id,
        file_name=masked_file_name,
        display_name=masked_display_name,
        document_meta=document_meta,
        privacy_config=config,
        executed_slot=slot,
        detectors_used=resolved_used,
        slot_applied=True,
        apply_replacement=True,
        analysis_bundle_id=analysis_bundle_id,
        slim_public=True,
        clinical_program_id=clinical_program_id,
        result_extensions=result_extensions,
        sentence_mask_detector=det,
        sentence_mask_profile=profile,
        sentence_mask_store=store,
        sentence_mask_shifter=shifter,
    )

    return PrivacyTransformResult(
        doc_id=doc_id,
        analysis_bundle=analysis_bundle,
        mask_result=mask_result,
        privacy_transform_slot=slot,
        detectors_used=resolved_used,
        slot_applied=True,
        config=config,
        block_audit_surfaces=block_audit_surfaces,
    )
