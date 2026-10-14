from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.privacy_mapping import MAPPING_ARTIFACT_SCHEMA_VERSION
from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from steps.prepare_analysis import to_dict
from privacy.config import PrivacyConfig
from privacy.mapping_store import MappingStore, export_mapping_artifact
from privacy.schemas import MaskHit, SensitiveEntityCandidate
from tests.clinical_program_fixtures import canonical_clinical_program_fields


def _registry_regex_config() -> PrivacyConfig:
    return PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": ["registry", "regex"]},
                "after_filter": {"detectors": []},
            }
        }
    )


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
    source: str = "mock",
) -> SensitiveEntityCandidate:
    start = text.index(term)
    return SensitiveEntityCandidate(
        original_text=term,
        entity_type=entity_type,  # type: ignore[arg-type]
        start=start,
        end=start + len(term),
        source=source,
        confidence=1.0,
    )


def _entry_with_text(artifact: dict, original_text: str) -> dict:
    for row in artifact["mappings"]:
        if original_text in row["original_texts"]:
            return row
    raise AssertionError(f"no mapping row containing {original_text!r}")


def _entry_by_canonical(artifact: dict, canonical_id: str) -> dict:
    for row in artifact["mappings"]:
        if row.get("canonical_id") == canonical_id:
            return row
    raise AssertionError(f"no mapping for canonical_id={canonical_id!r}")


def test_export_mapping_artifact_schema_version() -> None:
    artifact = export_mapping_artifact(
        doc_id="doc_schema",
        mapping_store=MappingStore(),
        mask_hits=[],
    )
    assert artifact["schema_version"] == "0.2.0"
    assert artifact["schema_version"] == MAPPING_ARTIFACT_SCHEMA_VERSION


def test_export_mapping_artifact_unknown_source_when_hit_source_empty() -> None:
    store = MappingStore()
    token = store.get_or_create_token("SPONSOR", "Acme")
    row = _entry_with_text(
        export_mapping_artifact(
            doc_id="doc_unknown",
            mapping_store=store,
            mask_hits=[
                MaskHit(
                    original_text="Acme",
                    token=token,
                    entity_type="SPONSOR",
                    original_start=0,
                    original_end=4,
                    source="",
                ),
            ],
        ),
        "Acme",
    )
    assert row["sources"] == ["unknown"]


def test_export_mapping_artifact_non_canonical_uses_original_texts() -> None:
    store = MappingStore()
    token = store.get_or_create_token("STUDY_DRUG", "VT-8802")
    hits = [
        MaskHit(
            original_text="VT-8802",
            token=token,
            entity_type="STUDY_DRUG",
            original_start=0,
            original_end=7,
            source="regex",
        ),
        MaskHit(
            original_text="VT-8802",
            token=token,
            entity_type="STUDY_DRUG",
            original_start=10,
            original_end=17,
            source="regex",
        ),
        MaskHit(
            original_text="VT-8802",
            token=token,
            entity_type="STUDY_DRUG",
            original_start=20,
            original_end=27,
            source="regex",
        ),
    ]
    artifact = export_mapping_artifact(
        doc_id="doc_meta",
        mapping_store=store,
        mask_hits=hits,
    )
    row = _entry_with_text(artifact, "VT-8802")

    assert artifact["doc_id"] == "doc_meta"
    assert row["entity_type"] == "STUDY_DRUG"
    assert row["token"] == "StudyDrug_001"
    assert row["original_texts"] == ["VT-8802"]
    assert "original_text" not in row
    assert "canonical_id" not in row
    assert row["sources"] == ["regex"]
    assert row["occurrence_count"] == 3


def test_export_mapping_artifact_merges_sources() -> None:
    store = MappingStore()
    token = store.get_or_create_token("STUDY_DRUG", "VT8802")
    hits = [
        MaskHit(
            original_text="VT8802",
            token=token,
            entity_type="STUDY_DRUG",
            original_start=0,
            original_end=6,
            source="regex",
        ),
        MaskHit(
            original_text="VT8802",
            token=token,
            entity_type="STUDY_DRUG",
            original_start=0,
            original_end=6,
            source="registry",
        ),
    ]
    row = _entry_with_text(
        export_mapping_artifact(
            doc_id="doc_sources",
            mapping_store=store,
            mask_hits=hits,
        ),
        "VT8802",
    )
    assert row["original_texts"] == ["VT8802"]
    assert row["sources"] == ["registry", "regex"]
    assert row["occurrence_count"] == 2


def test_export_mapping_artifact_sources_sorted_stably() -> None:
    store = MappingStore()
    token = store.get_or_create_token("SPONSOR", "Acme")
    hits = [
        MaskHit(
            original_text="Acme",
            token=token,
            entity_type="SPONSOR",
            original_start=0,
            original_end=4,
            source="uie",
        ),
        MaskHit(
            original_text="Acme",
            token=token,
            entity_type="SPONSOR",
            original_start=0,
            original_end=4,
            source="registry",
        ),
        MaskHit(
            original_text="Acme",
            token=token,
            entity_type="SPONSOR",
            original_start=0,
            original_end=4,
            source="regex",
        ),
    ]
    row = _entry_with_text(
        export_mapping_artifact(
            doc_id="doc_sort",
            mapping_store=store,
            mask_hits=hits,
        ),
        "Acme",
    )
    assert row["sources"] == ["registry", "regex", "uie"]
    assert row["occurrence_count"] == 3


def test_export_mapping_artifact_includes_parent_canonical_id() -> None:
    store = MappingStore()
    token = store.get_or_create_token(
        "RECORD_ID",
        "SCR-001",
        canonical_id="protocol_001:subject_id_001",
        predefined_token="SubjectId_001",
    )
    artifact = export_mapping_artifact(
        doc_id="doc_parent",
        mapping_store=store,
        mask_hits=[
            MaskHit(
                original_text="SCR-001",
                token=token,
                entity_type="RECORD_ID",
                original_start=0,
                original_end=7,
                source="registry",
                canonical_id="protocol_001:subject_id_001",
                parent_canonical_id="protocol_001",
            ),
        ],
    )
    row = _entry_by_canonical(artifact, "protocol_001:subject_id_001")
    assert row["token"] == "SubjectId_001"
    assert row["parent_canonical_id"] == "protocol_001"
    assert row["sources"] == ["registry"]


def test_export_mapping_artifact_registry_canonical_aggregates_aliases() -> None:
    store = MappingStore()
    token = "StudyDrug_001"
    aliases = ("VT-8802", "VT8802", "艾美妥珠单抗", "Emetuzumab")
    hits: list[MaskHit] = []
    offset = 0
    for alias in aliases:
        for _ in range(2):
            start = offset
            end = start + len(alias)
            hits.append(
                MaskHit(
                    original_text=alias,
                    token=token,
                    entity_type="STUDY_DRUG",
                    original_start=start,
                    original_end=end,
                    source="registry",
                    canonical_id="study_drug_001",
                )
            )
            offset = end + 1

    artifact = export_mapping_artifact(
        doc_id="doc_registry",
        mapping_store=store,
        mask_hits=hits,
    )
    row = _entry_by_canonical(artifact, "study_drug_001")

    assert len(artifact["mappings"]) == 1
    assert row["entity_type"] == "STUDY_DRUG"
    assert row["token"] == "StudyDrug_001"
    assert row["original_texts"] == list(aliases)
    assert row["sources"] == ["registry"]
    assert row["occurrence_count"] == 8
    assert "original_text" not in row


def test_mask_bundle_mapping_includes_identity_occurrences() -> None:
    body_text = "试验药物：VT8802"
    file_stem = "VT8802 IB"
    bundle = {
        "doc_id": "doc_identity_mapping",
        "file_name": f"{file_stem}.docx",
        "display_name": file_stem,
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {"block_id": "B1", "kind": "paragraph", "text": body_text},
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    detector = _StaticDetector(
        [
            _candidate(body_text, "VT8802", "STUDY_DRUG", source="regex"),
            _candidate(file_stem, "VT8802", "STUDY_DRUG", source="registry"),
        ]
    )
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        detector=detector,
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    artifact = result.mask_result.mapping
    row = _entry_with_text(artifact, "VT8802")

    assert artifact["schema_version"] == "0.2.0"
    assert len(artifact["mappings"]) == 1
    assert row["token"] == "StudyDrug_001"
    assert row["original_texts"] == ["VT8802"]
    assert row["sources"] == ["registry", "regex"]
    assert row["occurrence_count"] == 3

    mask_output = to_dict(result.mask_result)
    block_hit = mask_output["masked_blocks"][0]["mask_hits"][0]
    assert block_hit["source"] == "regex"
    assert "source" not in result.analysis_bundle["content_blocks"][0]


def test_mask_output_retains_per_hit_source() -> None:
    text = "VT8802"
    bundle = {
        "doc_id": "doc_hits",
        "file_name": "doc.docx",
        "source_type": "docx",
        "document_meta": {},
        "content_blocks": [{"block_id": "B1", "kind": "paragraph", "text": text}],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    detector = _StaticDetector(
        [_candidate(text, "VT8802", "STUDY_DRUG", source="regex")]
    )
    mask_output = to_dict(
        prepare_analysis_bundle(
            bundle,
            detector=detector,
            privacy_config=_registry_regex_config(), **canonical_clinical_program_fields()).mask_result
    )
    hit = mask_output["masked_blocks"][0]["mask_hits"][0]
    assert hit["source"] == "regex"
    assert hit["original_start"] == 0
    assert "mappings" in mask_output["mapping"]
