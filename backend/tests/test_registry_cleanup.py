from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from privacy.document_transform import run
from steps.prepare_analysis import prepare_analysis_bundle
from plugins.clinical_trial_doc.privacy.profile import CLINICAL_TRIAL_DOC_PRIVACY_PROFILE
REGISTRY_ENTITY_TYPES = frozenset(
    {
        "STUDY_DRUG",
        "GENERIC_NAME",
        "TARGET",
        "PROTOCOL_ID",
        "PHASE",
        "INDICATION",
        "BACKGROUND_DRUG",
        "DOSE_LEVEL",
        "SPONSOR",
        "SITE",
        "INVESTIGATOR",
        "RECORD_ID",
    }
)

def test_profile_masks_registry_entity_types() -> None:
    masked = CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.entity_types_to_mask
    keep = CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.entity_types_to_keep
    assert REGISTRY_ENTITY_TYPES <= masked
    assert masked.isdisjoint(keep)
    for kept in (
        "AE",
        "ADR",
        "SAE",
        "SAR",
        "SUSAR",
        "DOSE",
        "COUNT",
        "PERCENT",
        "DATE",
        "VISIT",
        "TREATMENT_GROUP",
    ):
        assert kept in keep


def test_vt8802_mapping_sources_registry_only() -> None:
    result = run(
        doc_id="doc",
        blocks=[{"block_id": "B1", "text": "药物 VT-8802 总体耐受性良好。"}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    hit = next(
        h
        for h in result.masked_blocks[0].mask_hits
        if h.original_text == "VT-8802" and h.entity_type == "STUDY_DRUG"
    )
    assert hit.source == "registry"

    row = next(
        r
        for r in result.mapping["mappings"]
        if r.get("canonical_id") == "study_drug_001"
    )
    assert row["sources"] == ["registry"]


def test_px2471_not_in_mapping_as_study_drug() -> None:
    text = (
        "6.2 PX-2471\n"
        "既往PX-2471联合含铂化疗用于晚期非小细胞肺癌患者的研究显示。"
    )
    result = run(
        doc_id="doc_px",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    study_hits = [
        h
        for h in result.masked_blocks[0].mask_hits
        if h.entity_type == "STUDY_DRUG" and h.original_text == "PX-2471"
    ]
    assert study_hits == []

    for row in result.mapping["mappings"]:
        if row["entity_type"] == "STUDY_DRUG":
            assert "PX-2471" not in row.get("original_texts", [])


def test_study_drug_aliases_aggregate_in_mapping_v02() -> None:
    text = "VT-8802 VT8802 Emetuzumab"
    result = run(
        doc_id="doc_agg",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    assert result.mapping["schema_version"] == "0.2.0"
    study_row = next(
        r
        for r in result.mapping["mappings"]
        if r.get("canonical_id") == "study_drug_001"
    )
    assert study_row["token"] == "StudyDrug_001"
    assert set(study_row["original_texts"]) >= {"VT-8802", "VT8802"}

    generic_row = next(
        r
        for r in result.mapping["mappings"]
        if r.get("canonical_id") == "study_drug_001:generic_name"
    )
    assert generic_row["token"] == "GenericName_001"
    assert "Emetuzumab" in generic_row["original_texts"]

    tokens = {r["token"] for r in result.mapping["mappings"]}
    assert "StudyDrug_002" not in tokens
    assert "GenericName_002" not in tokens
