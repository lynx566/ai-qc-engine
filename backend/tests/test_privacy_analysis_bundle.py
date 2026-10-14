from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from plugins.clinical_trial_doc.privacy.profile import (
    CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
)
from plugins.clinical_trial_doc.privacy.registry.export import (
    export_clinical_registry_entries,
)
from privacy.config import PrivacyConfig
from privacy.document_transform import run
from privacy.mapping_store import MappingStore
from privacy.schemas import SensitiveEntityCandidate
from tests.clinical_program_fixtures import canonical_clinical_program_fields


class _StaticDetector:
    def __init__(self, candidates: list[SensitiveEntityCandidate]) -> None:
        self._candidates = candidates

    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        return [
            c
            for c in self._candidates
            if text[c.start : c.end] == c.original_text
        ]


def _candidate(
    text: str,
    term: str,
    entity_type: str,
    *,
    canonical_id: str | None = None,
    predefined_token: str | None = None,
) -> SensitiveEntityCandidate:
    start = text.index(term)
    return SensitiveEntityCandidate(
        original_text=term,
        entity_type=entity_type,  # type: ignore[arg-type]
        start=start,
        end=start + len(term),
        source="mock",
        confidence=1.0,
        canonical_id=canonical_id,
        predefined_token=predefined_token,
    )


def _single_block_bundle(*, text: str, block_id: str = "C0001") -> dict:
    return {
        "doc_id": "doc_analysis_bundle",
        "file_name": "sample.docx",
        "display_name": "sample",
        "source_type": "docx",
        "document_meta": {"language": "zh", "bundle_schema_version": "0.2.1"},
        "content_blocks": [
            {
                "block_id": block_id,
                "kind": "paragraph",
                "normalized_text": text,
                "loc": "BODY:P1",
                "sentences": [
                    {
                        "sentence_id": f"{block_id}:S001",
                        "normalized_text": text,
                    }
                ],
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def _registry_regex_config() -> PrivacyConfig:
    return PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": ["registry", "regex"]},
                "after_filter": {"detectors": []},
            }
        }
    )


def _block(bundle: dict) -> dict:
    return bundle["content_blocks"][0]


def test_empty_detectors_identity_sentence_transform() -> None:
    text = "VT-8802治疗23例患者"
    result = prepare_analysis_bundle(
        _single_block_bundle(text=text),
        language="zh",
        **canonical_clinical_program_fields(),
    )
    block = _block(result.analysis_bundle)

    assert result.analysis_bundle["privacy_enabled"] is False
    assert block["normalized_text"] == text
    assert block["analysis_text"] == text
    assert "span_map" not in block

    sentence = block["sentences"][0]
    assert sentence["normalized_text"] == text
    assert sentence["analysis_text"] == text
    assert "span_map" not in sentence


def _audit_block(result) -> dict:
    assert result.block_audit_surfaces
    return result.block_audit_surfaces[0]


def test_replacement_phrase_masks_sentence_analysis_text() -> None:
    normalized = "VT-8802治疗23例患者"
    detector = _StaticDetector(
        [
            _candidate(
                normalized,
                "VT-8802",
                "STUDY_DRUG",
                canonical_id="study_drug.vt8802",
                predefined_token="StudyDrug_001",
            )
        ]
    )
    result = prepare_analysis_bundle(
        _single_block_bundle(text=normalized),
        detector=detector,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
        privacy_config=_registry_regex_config(),
        **canonical_clinical_program_fields(),
    )
    block = _block(result.analysis_bundle)
    audit_block = _audit_block(result)
    analysis = block["analysis_text"]

    assert analysis == "StudyDrug_001治疗23例患者"
    assert "normalized_text" not in block
    assert "span_map" not in audit_block
    sentence = block["sentences"][0]
    assert sentence["analysis_text"] == analysis
    assert "normalized_text" not in sentence


def test_multiple_replacements_mask_sentence_analysis_text() -> None:
    raw = "VT-8802治疗试验参与者001"
    detector = _StaticDetector(
        [
            _candidate(raw, "VT-8802", "STUDY_DRUG", predefined_token="StudyDrug_001"),
            _candidate(raw, "试验参与者001", "SUBJECT", predefined_token="Subject_001"),
        ]
    )
    result = prepare_analysis_bundle(
        _single_block_bundle(text=raw),
        detector=detector,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
        privacy_config=_registry_regex_config(),
        **canonical_clinical_program_fields(),
    )
    block = _block(result.analysis_bundle)
    audit_block = _audit_block(result)
    analysis = block["analysis_text"]

    assert "VT-8802" not in analysis
    assert "试验参与者001" not in analysis
    assert "StudyDrug_001" in analysis
    assert "Subject_001" in analysis
    assert "normalized_text" not in block
    assert "span_map" not in audit_block
    assert block["sentences"][0]["analysis_text"] == analysis


def test_registry_mask_tokens_remain_stable() -> None:
    text = "药物 VT-8802 由申办方某某生物医药有限公司支持。"
    result = run(
        doc_id="doc",
        blocks=[{"block_id": "B1", "text": text, "normalized_text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
        apply_replacement=True,
        registry_entries=export_clinical_registry_entries(),
    )
    block = result.masked_blocks[0]

    assert result.privacy_mode == "transform"
    assert block.mask_hits
    assert "VT-8802" not in block.masked_text
    assert "某某生物医药有限公司" not in block.masked_text

    tokens = {hit.token for hit in block.mask_hits}
    assert "StudyDrug_001" in tokens or any("StudyDrug" in t for t in tokens)

    store = MappingStore()
    for hit in block.mask_hits:
        store.get_or_create_token(
            entity_type=hit.entity_type,
            original_text=hit.original_text,
            canonical_id=hit.canonical_id,
        )
    token_again = store.get_or_create_token(
        entity_type=block.mask_hits[0].entity_type,
        original_text=block.mask_hits[0].original_text,
        canonical_id=block.mask_hits[0].canonical_id,
    )
    assert token_again == block.mask_hits[0].token


def test_analysis_bundle_required_fields_present() -> None:
    text = "VT-8802治疗23例患者"
    result = prepare_analysis_bundle(
        _single_block_bundle(text=text),
        language="zh",
        **canonical_clinical_program_fields(),
    )
    block = _block(result.analysis_bundle)

    for key in ("normalized_text", "analysis_text"):
        assert key in block
    assert "span_map" not in block
    assert "text" not in block
    assert "masked_text" not in block
    assert result.analysis_bundle["privacy_transforms"]["after_extract"]["applied"] is False
    assert "privacy_enabled" in result.analysis_bundle
    assert "privacy_preset" not in result.analysis_bundle
    assert "privacy_mode" not in result.analysis_bundle
    assert "analysis_bundle_id" not in result.analysis_bundle

    sentence = block["sentences"][0]
    assert "text" not in sentence
    assert sentence["normalized_text"] == text
    assert sentence["analysis_text"] == text
    assert "span_map" not in sentence


def test_analysis_bundle_id_stamped_when_provided() -> None:
    run_id = "prepare_analysis_20260606_222646"
    result = prepare_analysis_bundle(
        _single_block_bundle(text="研究者手册"),
        language="zh",
        analysis_bundle_id=run_id,
        **canonical_clinical_program_fields(),
    )
    bundle = result.analysis_bundle
    assert bundle["analysis_bundle_id"] == run_id
    assert next(iter(bundle)) == "analysis_bundle_id"
    assert bundle["doc_id"] == "doc_analysis_bundle"
    assert bundle["stage"] == "prepare_analysis"
