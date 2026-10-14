"""Regression guards for Prepare direct canonical Sentence.normalized_text consumption."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import pytest

BACKEND_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.prepare_analysis import (
    validate_prepare_analysis_input,
)
from core.document.sentence_index import build_sentences
from operations.prepare_analysis import PrepareAnalysisConfigId
from steps.prepare_analysis import prepare_analysis_bundle
from privacy.config import PrivacyConfig
from privacy.detectors.composite import CompositeDetector
from privacy.mapping_store import MappingStore
from privacy.profile import PrivacyProfile
from privacy.schemas import MaskHit, MaskedBlock, SensitiveEntityCandidate
from privacy.document_transform import _apply_analysis_fields_to_block
from tests.clinical_program_fixtures import (
    CANONICAL_TEST_CLINICAL_PROGRAM_ID,
    prepare_analysis_bundle_for_test,
)

FILE_HASH = "sha256:" + "c" * 64
CANONICAL_SENTENCE = "Canonical sentence payload."


@dataclass(frozen=True)
class _IdentityPlan:
    prepare_analysis_config_id: PrepareAnalysisConfigId
    privacy_enabled: bool = False
    requested_detector_ids: tuple[str, ...] = ()
    effective_detector_ids: tuple[str, ...] = ()
    date_shift_enabled: bool = False
    date_shift_offset_days: int = 0

    @property
    def result_extension_values(self) -> Mapping[str, str]:
        return {}

    @property
    def provenance_descriptor(self) -> Mapping[str, Any]:
        return {}

    @property
    def privacy_provenance_stats(self) -> Mapping[str, str]:
        return {}

    def build_detector(self) -> CompositeDetector:
        raise AssertionError("identity prepare must not invoke build_detector")

    def build_privacy_profile(self) -> PrivacyProfile:
        raise AssertionError("identity prepare must not invoke build_privacy_profile")

    def new_mapping_store(self) -> MappingStore:
        raise AssertionError("identity prepare must not invoke new_mapping_store")

    def validate_result_extension(self, payload: Mapping[str, Any]) -> None:
        del payload


def _identity_plan() -> _IdentityPlan:
    return _IdentityPlan(
        prepare_analysis_config_id=PrepareAnalysisConfigId("pacfg_sentence_handoff"),
    )


def _bundle_v021(
    *,
    block_normalized: str,
    sentences: list[dict[str, Any]],
    schema_version: str = "0.2.1",
) -> dict[str, Any]:
    return {
        "doc_id": "sentence_handoff_doc",
        "file_hash": FILE_HASH,
        "file_name": "handoff.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh", "bundle_schema_version": schema_version},
        "front_matter_blocks": [],
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "raw_text": block_normalized,
                "normalized_text": block_normalized,
                "order": 1,
                "sentences": sentences,
            }
        ],
        "table_blocks": [],
        "format_blocks": [],
    }


def _canonical_sentence(
    *,
    normalized_text: str = CANONICAL_SENTENCE,
    block_normalized: str | None = None,
) -> dict[str, Any]:
    block_text = block_normalized or normalized_text
    built = build_sentences(
        "C0001",
        "paragraph",
        raw_text=block_text,
        normalized_text=block_text,
    )[0]
    return {
        "sentence_id": built.sentence_id,
        "raw_text": built.raw_text,
        "normalized_text": normalized_text,
    }


def test_current_v021_direct_inherits_extract_normalized_text() -> None:
    bundle = _bundle_v021(
        block_normalized=CANONICAL_SENTENCE,
        sentences=[_canonical_sentence()],
    )
    result = prepare_analysis_bundle(bundle, resolved_plan=_identity_plan())
    sentence = result.analysis_bundle["content_blocks"][0]["sentences"][0]
    block = result.analysis_bundle["content_blocks"][0]
    assert sentence["sentence_id"] == "C0001:S001"
    assert sentence["normalized_text"] is CANONICAL_SENTENCE
    assert sentence["analysis_text"] == CANONICAL_SENTENCE
    assert "raw_text" not in sentence
    assert "span_map" not in sentence
    assert "span_map" not in block


def test_mismatched_normalized_text_still_passes_ingress() -> None:
    block_text = "A。B。"
    bundle = _bundle_v021(
        block_normalized=block_text,
        sentences=[
            {
                "sentence_id": "C0001:S001",
                "raw_text": "B。",
                "normalized_text": "B。",
            }
        ],
    )
    result = prepare_analysis_bundle(bundle, resolved_plan=_identity_plan())
    sentence = result.analysis_bundle["content_blocks"][0]["sentences"][0]
    assert sentence["normalized_text"] == "B。"
    assert sentence["analysis_text"] == "B。"


def test_missing_normalized_text_on_v021_fails() -> None:
    block_text = CANONICAL_SENTENCE
    bundle = _bundle_v021(
        block_normalized=block_text,
        sentences=[
            {
                "sentence_id": "C0001:S001",
            }
        ],
    )
    with pytest.raises(ValueError, match="normalized_text is required"):
        validate_prepare_analysis_input(bundle)


def test_legacy_sentence_text_still_supported() -> None:
    legacy_text = "Legacy sentence."
    bundle = {
        "doc_id": "legacy_doc",
        "file_hash": FILE_HASH,
        "source_type": "docx",
        "document_meta": {"language": "zh", "bundle_schema_version": "0.1.9"},
        "front_matter_blocks": [],
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "normalized_text": legacy_text,
                "sentences": [
                    {
                        "sentence_id": "C0001:S001",
                        "text": legacy_text,
                    }
                ],
            }
        ],
        "table_blocks": [],
        "format_blocks": [],
    }
    result = prepare_analysis_bundle(bundle, resolved_plan=_identity_plan())
    sentence = result.analysis_bundle["content_blocks"][0]["sentences"][0]
    assert sentence["normalized_text"] == legacy_text
    assert sentence["analysis_text"] == legacy_text
    assert "text" not in sentence


def test_identity_path_preserves_canonical_payload_object_identity() -> None:
    bundle = _bundle_v021(
        block_normalized=CANONICAL_SENTENCE,
        sentences=[_canonical_sentence()],
    )
    input_sentence = bundle["content_blocks"][0]["sentences"][0]
    result = prepare_analysis_bundle(bundle, resolved_plan=_identity_plan())
    output_sentence = result.analysis_bundle["content_blocks"][0]["sentences"][0]
    assert output_sentence["sentence_id"] == input_sentence["sentence_id"]
    assert output_sentence["normalized_text"] == input_sentence["normalized_text"]


def test_privacy_on_sentence_owned_transform() -> None:
    normalized = "代号：VT-8802"
    canonical = _canonical_sentence(normalized_text=normalized, block_normalized=normalized)
    bundle = _bundle_v021(block_normalized=normalized, sentences=[canonical])

    class _StaticDetector:
        def detect(self, text: str) -> list[SensitiveEntityCandidate]:
            if "VT-8802" not in text:
                return []
            start = text.index("VT-8802")
            return [
                SensitiveEntityCandidate(
                    original_text="VT-8802",
                    entity_type="STUDY_DRUG",
                    start=start,
                    end=start + len("VT-8802"),
                    source="mock",
                    confidence=1.0,
                    predefined_token="StudyDrug_001",
                )
            ]

    result = prepare_analysis_bundle_for_test(
        bundle,
        detector=_StaticDetector(),
        privacy_config=PrivacyConfig.from_dict(
            {
                "transforms": {
                    "after_extract": {"detectors": ["registry", "regex"]},
                    "after_filter": {"detectors": []},
                }
            }
        ),
        clinical_program_id=CANONICAL_TEST_CLINICAL_PROGRAM_ID,
    )
    public_block = result.analysis_bundle["content_blocks"][0]
    public_sentence = public_block["sentences"][0]
    audit_sentence = result.block_audit_surfaces[0]["sentences"][0]

    assert audit_sentence["normalized_text"] == normalized
    assert audit_sentence["analysis_text"] == "代号：StudyDrug_001"
    assert "span_map" not in audit_sentence
    assert public_sentence["analysis_text"] == "代号：StudyDrug_001"
    assert set(public_sentence) <= {"sentence_id", "analysis_text"}
    assert "normalized_text" not in public_sentence
    assert "raw_text" not in public_sentence
    assert "normalized_text" not in public_block


def test_apply_analysis_fields_masks_sentence_directly() -> None:
    normalized = "代号：VT-8802"
    block = {
        "block_id": "C0001",
        "kind": "paragraph",
        "sentences": [
            {
                "sentence_id": "C0001:S001",
                "normalized_text": normalized,
            }
        ],
    }
    masked = MaskedBlock(
        block_id="C0001",
        original_text=normalized,
        masked_text="代号：StudyDrug_001",
        mask_hits=[
            MaskHit(
                original_text="VT-8802",
                token="StudyDrug_001",
                entity_type="STUDY_DRUG",
                original_start=3,
                original_end=10,
                source="registry",
            )
        ],
    )

    class _StaticDetector:
        def detect(self, text: str) -> list[SensitiveEntityCandidate]:
            if "VT-8802" not in text:
                return []
            start = text.index("VT-8802")
            return [
                SensitiveEntityCandidate(
                    original_text="VT-8802",
                    entity_type="STUDY_DRUG",
                    start=start,
                    end=start + len("VT-8802"),
                    source="mock",
                    confidence=1.0,
                    predefined_token="StudyDrug_001",
                )
            ]

    enriched = _apply_analysis_fields_to_block(
        block,
        masked,
        apply_replacement=True,
        canonical_sentence_payload_required=True,
        detector=_StaticDetector(),
        mapping_store=MappingStore(),
    )
    sentence = enriched["sentences"][0]
    assert sentence["sentence_id"] == "C0001:S001"
    assert sentence["normalized_text"] == normalized
    assert sentence["analysis_text"] == "代号：StudyDrug_001"
    assert "span_map" not in sentence


def test_build_sentences_fixture_carries_normalized_text_for_v021() -> None:
    text = "第一句。第二句。"
    sentences = build_sentences(
        "C0001",
        "paragraph",
        raw_text=text,
        normalized_text=text,
    )
    bundle = _bundle_v021(
        block_normalized=text,
        sentences=[asdict(sentence) for sentence in sentences],
    )
    validate_prepare_analysis_input(bundle)
