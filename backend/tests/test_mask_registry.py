from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from privacy.detectors.factory import build_mask_detectors
from privacy.document_transform import run
from plugins.clinical_trial_doc.privacy.profile import CLINICAL_TRIAL_DOC_PRIVACY_PROFILE
from plugins.clinical_trial_doc.privacy.registry.export import export_clinical_registry_entries
from privacy.detectors.registry_detector import RegistryDetector
from privacy.mapping_store import MappingStore
from privacy.merger import merge_candidates
from privacy.schemas import SensitiveEntityCandidate


def test_export_clinical_registry_includes_vt8802_study_drug() -> None:
    entries = export_clinical_registry_entries()
    study_drug_rows = [e for e in entries if e.entity_type == "STUDY_DRUG"]
    assert study_drug_rows
    aliases = {alias for row in study_drug_rows for alias in row.aliases}
    assert "VT-8802" in aliases
    vt_row = next(row for row in study_drug_rows if "VT-8802" in row.aliases)
    assert vt_row.canonical_id == "study_drug_001"
    assert vt_row.token == "StudyDrug_001"


def test_export_clinical_registry_includes_protocol_cci_entities() -> None:
    entries = export_clinical_registry_entries()
    by_type = {e.entity_type: e for e in entries}

    sponsor = by_type["SPONSOR"]
    assert sponsor.canonical_id == "sponsor_001"
    assert sponsor.token == "Sponsor_001"
    assert "某某生物医药有限公司" in sponsor.aliases

    site = by_type["SITE"]
    assert site.canonical_id == "site_001"
    assert site.token == "Site_001"
    assert "研究中心A" in site.aliases

    investigator = by_type["INVESTIGATOR"]
    assert investigator.canonical_id == "investigator_001"
    assert investigator.token == "Investigator_001"
    assert "李四" in investigator.aliases

    subject_id = by_type["RECORD_ID"]
    assert subject_id.canonical_id == "protocol_002:subject_id_001"
    assert subject_id.token == "SubjectId_001"
    assert subject_id.parent_canonical_id == "protocol_002"
    assert "01001" in subject_id.aliases


def test_build_mask_detectors_includes_registry_not_dictionary() -> None:
    _detectors, kinds = build_mask_detectors(
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    assert kinds == ["registry", "regex"]
    assert isinstance(_detectors[0], RegistryDetector)
    assert "dictionary" not in kinds


def test_mask_vt8802_hit_source_registry() -> None:
    result = run(
        doc_id="doc",
        blocks=[{"block_id": "B1", "text": "药物 VT-8802 总体耐受性良好。"}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    hits = [
        h
        for h in result.masked_blocks[0].mask_hits
        if h.original_text == "VT-8802" and h.entity_type == "STUDY_DRUG"
    ]
    assert len(hits) == 1
    assert hits[0].source == "registry"


def test_merge_registry_beats_uie_for_overlapping_vt8802() -> None:
    text = "药物 VT-8802 良好。"
    start = text.index("VT-8802")
    end = start + len("VT-8802")
    registry = SensitiveEntityCandidate(
        original_text="VT-8802",
        entity_type="STUDY_DRUG",
        start=start,
        end=end,
        source="registry",
        confidence=1.0,
        canonical_id="study_drug_001",
        predefined_token="StudyDrug_001",
    )
    uie = SensitiveEntityCandidate(
        original_text="VT-8802",
        entity_type="STUDY_DRUG",
        start=start,
        end=end,
        source="uie",
        confidence=1.0,
    )
    merged = merge_candidates([uie, registry])
    assert len(merged) == 1
    # Both sources preserved; registry wins canonical identity and sort order.
    assert merged[0].sources == ["registry", "uie"]
    assert merged[0].canonical_id == "study_drug_001"
    assert merged[0].predefined_token == "StudyDrug_001"


def test_export_clinical_registry_includes_generic_name_entry() -> None:
    entries = export_clinical_registry_entries()
    generic_rows = [
        e for e in entries if e.canonical_id == "study_drug_001:generic_name"
    ]
    assert len(generic_rows) == 1
    row = generic_rows[0]
    assert row.entity_type == "GENERIC_NAME"
    assert row.token == "GenericName_001"
    assert set(row.aliases) == {"艾美妥珠单抗", "Emetuzumab"}


def test_study_drug_001_generic_name_aliases_exclude_modality_descriptions() -> None:
    from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001.study_drugs import (
        STUDY_DRUG_001,
    )

    modality_phrases = (
        "重组人源化抗PD-L1单克隆抗体",
        "recombinant humanized anti-PD-L1 monoclonal antibody",
        "anti-PD-L1 monoclonal antibody",
    )
    for phrase in modality_phrases:
        assert phrase not in STUDY_DRUG_001.generic_name_aliases
        assert phrase not in STUDY_DRUG_001.aliases


def test_mapping_store_registry_identity_key_shares_predefined_token() -> None:
    store = MappingStore()
    t_vt_dash = store.get_or_create_token(
        "STUDY_DRUG",
        "VT-8802",
        canonical_id="study_drug_001",
        predefined_token="StudyDrug_001",
    )
    t_vt = store.get_or_create_token(
        "STUDY_DRUG",
        "VT8802",
        canonical_id="study_drug_001",
        predefined_token="StudyDrug_001",
    )
    t_cn = store.get_or_create_token(
        "GENERIC_NAME",
        "艾美妥珠单抗",
        canonical_id="study_drug_001:generic_name",
        predefined_token="GenericName_001",
    )
    assert t_vt_dash == t_vt == "StudyDrug_001"
    assert t_cn == "GenericName_001"
    assert store.counters.get("STUDY_DRUG", 0) == 1
    assert ("STUDY_DRUG", "study_drug_001") in store.mapping
    assert ("GENERIC_NAME", "study_drug_001:generic_name") in store.mapping
    assert store.mapping[("GENERIC_NAME", "study_drug_001:generic_name")] == "GenericName_001"


def test_mapping_store_non_registry_uses_original_text_key() -> None:
    store = MappingStore()
    token = store.get_or_create_token("SUBJECT", "张三")
    assert token == "Subject_001"
    assert store.mapping[("SUBJECT", "张三")] == "Subject_001"


def test_mapping_store_predefined_does_not_block_next_auto_token() -> None:
    store = MappingStore()
    store.get_or_create_token(
        "STUDY_DRUG",
        "VT-8802",
        canonical_id="study_drug_001",
        predefined_token="StudyDrug_001",
    )
    other = store.get_or_create_token("STUDY_DRUG", "UnknownDrugX")
    assert other == "StudyDrug_002"


def test_registry_aliases_share_study_drug_and_generic_name_tokens() -> None:
    text = (
        "药物 VT-8802 与 VT8802 及 艾美妥珠单抗、Emetuzumab 均相关。"
    )
    result = run(
        doc_id="doc_aliases",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    study_hits = [
        h
        for h in result.masked_blocks[0].mask_hits
        if h.entity_type == "STUDY_DRUG"
    ]
    generic_hits = [
        h
        for h in result.masked_blocks[0].mask_hits
        if h.entity_type == "GENERIC_NAME"
    ]
    assert len(study_hits) == 2
    assert {h.original_text for h in study_hits} == {"VT-8802", "VT8802"}
    assert all(h.token == "StudyDrug_001" for h in study_hits)

    assert len(generic_hits) == 2
    assert {h.original_text for h in generic_hits} == {"艾美妥珠单抗", "Emetuzumab"}
    assert all(h.token == "GenericName_001" for h in generic_hits)

    artifact = result.mapping
    assert artifact["schema_version"] == "0.2.0"
    study_rows = [
        row for row in artifact["mappings"] if row["entity_type"] == "STUDY_DRUG"
    ]
    generic_rows = [
        row for row in artifact["mappings"] if row["entity_type"] == "GENERIC_NAME"
    ]
    assert len(study_rows) == 1
    study_row = study_rows[0]
    assert study_row["canonical_id"] == "study_drug_001"
    assert study_row["token"] == "StudyDrug_001"
    assert study_row["original_texts"] == ["VT-8802", "VT8802"]
    assert study_row["sources"] == ["registry"]
    assert study_row["occurrence_count"] == 2

    assert len(generic_rows) == 1
    generic_row = generic_rows[0]
    assert generic_row["canonical_id"] == "study_drug_001:generic_name"
    assert generic_row["token"] == "GenericName_001"
    assert set(generic_row["original_texts"]) == {"艾美妥珠单抗", "Emetuzumab"}
    assert generic_row["sources"] == ["registry"]
    assert generic_row["occurrence_count"] == 2

    tokens = {row["token"] for row in artifact["mappings"]}
    assert "StudyDrug_002" not in tokens
    assert "GenericName_002" not in tokens


def test_mask_clinical_program_cci_all_registry_sources() -> None:
    text = (
        "艾美妥珠单抗由某某生物医药有限公司开发。"
        "研究中心A的研究者李四筛选01001。"
    )
    result = run(
        doc_id="doc_cci",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    block = result.masked_blocks[0]
    by_text = {(h.entity_type, h.original_text): h for h in block.mask_hits}

    assert by_text[("GENERIC_NAME", "艾美妥珠单抗")].token == "GenericName_001"
    assert by_text[("SPONSOR", "某某生物医药有限公司")].token == "Sponsor_001"
    assert by_text[("SITE", "研究中心A")].token == "Site_001"
    assert by_text[("INVESTIGATOR", "李四")].token == "Investigator_001"
    subject_id_hit = by_text[("RECORD_ID", "01001")]
    assert subject_id_hit.token == "SubjectId_001"
    assert subject_id_hit.parent_canonical_id == "protocol_002"
    assert all(h.source == "registry" for h in block.mask_hits)

    tokens = {row["token"] for row in result.mapping["mappings"]}
    assert "StudyDrug_002" not in tokens
    assert "Sponsor_002" not in tokens
    assert "Site_002" not in tokens
    assert "Investigator_002" not in tokens
    assert "SubjectId_002" not in tokens
    subject_id_row = next(
        row for row in result.mapping["mappings"] if row["token"] == "SubjectId_001"
    )
    assert set(subject_id_row["sources"]) == {"registry", "regex"}
    for row in result.mapping["mappings"]:
        assert "registry" in row["sources"]
        if row["token"] != "SubjectId_001":
            assert row["sources"] == ["registry"]
    assert result.detectors == ["registry", "regex"]

    subject_row = next(
        r
        for r in result.mapping["mappings"]
        if r.get("canonical_id") == "protocol_002:subject_id_001"
    )
    assert subject_row["token"] == "SubjectId_001"
    assert subject_row["parent_canonical_id"] == "protocol_002"


def test_mask_sponsor_hit_source_registry() -> None:
    result = run(
        doc_id="doc_sponsor",
        blocks=[{"block_id": "B1", "text": "申办方某某生物医药有限公司。"}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    sponsor_hits = [
        h for h in result.masked_blocks[0].mask_hits if h.entity_type == "SPONSOR"
    ]
    assert len(sponsor_hits) == 1
    assert sponsor_hits[0].token == "Sponsor_001"
    assert sponsor_hits[0].original_text == "某某生物医药有限公司"
    assert sponsor_hits[0].source == "registry"

    row = next(
        r
        for r in result.mapping["mappings"]
        if r.get("canonical_id") == "sponsor_001"
    )
    assert row["token"] == "Sponsor_001"
    assert row["sources"] == ["registry"]


def test_export_clinical_registry_includes_pd_l1_target() -> None:
    entries = export_clinical_registry_entries()
    by_type = {e.canonical_id: e for e in entries if e.entity_type == "TARGET"}

    pd_1_pd_l1 = by_type["target_class_001"]
    assert pd_1_pd_l1.token == "TargetClass_001"
    assert "PD-1/PD-L1" in pd_1_pd_l1.aliases
    assert "PD-1和PD-L1" in pd_1_pd_l1.aliases

    pd_l1 = by_type["target_001"]
    assert pd_l1.token == "Target_001"
    assert "PD-L1" in pd_l1.aliases
    assert "anti-PD-L1" not in pd_l1.aliases
    assert "CD274" in pd_l1.aliases
    assert "target_002" not in by_type


def test_mask_standalone_pd_l1_target() -> None:
    result = run(
        doc_id="doc_targets",
        blocks=[
            {"block_id": "B1", "text": "靶点 PD-L1 相关。"},
        ],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    masked = result.masked_blocks[0].masked_text
    assert masked == "靶点 Target_001 相关。"
    by_text = {
        (h.entity_type, h.original_text): h for h in result.masked_blocks[0].mask_hits
    }
    assert by_text[("TARGET", "PD-L1")].token == "Target_001"


def test_mask_pd_l1_in_checkpoint_inhibitor_phrase() -> None:
    text = "PD-1/PD-L1类免疫检查点抑制剂"
    result = run(
        doc_id="doc_checkpoint",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    masked = result.masked_blocks[0].masked_text
    assert masked == "TargetClass_001类免疫检查点抑制剂"
    assert "PD-1/Target_001" not in masked


def test_mask_pd_1_pd_l1_target_class_variants() -> None:
    cases = [
        ("PD-1/PD-L1", "TargetClass_001"),
        ("PD-1 / PD-L1", "TargetClass_001"),
        ("PD-1及PD-L1", "TargetClass_001"),
        ("PD-1和PD-L1", "TargetClass_001"),
        ("PD-1或PD-L1", "TargetClass_001"),
        ("PD-1、PD-L1", "TargetClass_001"),
        ("PD-1 与 PD-L1", "TargetClass_001"),
        ("PD-1/PD-L1类免疫检查点抑制剂", "TargetClass_001类免疫检查点抑制剂"),
    ]

    for raw, expected in cases:
        result = run(
            doc_id=f"doc_target_class_{len(raw)}",
            blocks=[{"block_id": "B1", "text": raw}],
            profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
            language="zh",
        )
        masked = result.masked_blocks[0].masked_text
        assert masked == expected
        assert "PD-1/Target_001" not in masked
        assert result.masked_blocks[0].mask_hits[0].token == "TargetClass_001"


def test_mask_target_class_and_standalone_pd_l1_in_same_sentence() -> None:
    text = "PD-1/PD-L1类免疫检查点抑制剂不同于单独检测PD-L1表达。"
    result = run(
        doc_id="doc_target_class_and_single_target",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    masked = result.masked_blocks[0].masked_text
    assert masked == "TargetClass_001类免疫检查点抑制剂不同于单独检测Target_001表达。"
    assert "PD-1/Target_001" not in masked
    assert [hit.token for hit in result.masked_blocks[0].mask_hits] == [
        "TargetClass_001",
        "Target_001",
    ]


def test_mask_target_class_user_examples() -> None:
    result = run(
        doc_id="doc_target_class_example_1",
        blocks=[
            {
                "block_id": "B1",
                "text": "VT8802的总体安全性特征与PD-1/PD-L1类免疫检查点抑制剂的已知风险谱基本一致。",
            }
        ],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    assert (
        result.masked_blocks[0].masked_text
        == "StudyDrug_001的总体安全性特征与TargetClass_001类免疫检查点抑制剂的已知风险谱基本一致。"
    )

    result = run(
        doc_id="doc_target_class_example_2",
        blocks=[
            {
                "block_id": "B1",
                "text": "VT8802为重组人源化抗PD-L1单克隆抗体，属于PD-1/PD-L1类免疫检查点抑制剂。",
            }
        ],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    assert (
        result.masked_blocks[0].masked_text
        == "StudyDrug_001为重组人源化抗Target_001单克隆抗体，属于TargetClass_001类免疫检查点抑制剂。"
    )


def test_mask_english_anti_pd_l1_monoclonal_antibody_masks_embedded_target() -> None:
    cases = [
        (
            "anti-PD-L1 monoclonal antibody",
            "anti-Target_001 monoclonal antibody",
        ),
        (
            "recombinant humanized anti-PD-L1 monoclonal antibody",
            "recombinant humanized anti-Target_001 monoclonal antibody",
        ),
    ]
    for text, expected in cases:
        result = run(
            doc_id=f"doc_anti_pd_l1_{len(text)}",
            blocks=[{"block_id": "B1", "text": text}],
            profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
            language="en",
        )
        masked = result.masked_blocks[0].masked_text
        assert masked == expected
        assert "GenericName_001" not in masked
        assert "PD-L1" not in masked
        hits = result.masked_blocks[0].mask_hits
        assert len(hits) == 1
        assert hits[0].entity_type == "TARGET"
        assert hits[0].token == "Target_001"


def test_mask_chinese_anti_pd_l1_phrase_masks_embedded_target() -> None:
    text = "重组人源化抗PD-L1单克隆抗体"
    result = run(
        doc_id="doc_chinese_anti_pd_l1",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    masked = result.masked_blocks[0].masked_text
    assert masked == "重组人源化抗Target_001单克隆抗体"
    assert "PD-L1" not in masked
    assert "GenericName_001" not in masked
    hits = result.masked_blocks[0].mask_hits
    assert len(hits) == 1
    assert hits[0].entity_type == "TARGET"
    assert hits[0].token == "Target_001"


def test_mask_title_page_study_drug_generic_name_and_modality() -> None:
    text = (
        "试验药物名称：VT8802（拟定通用名：艾美妥珠单抗）\n"
        "药物类别：重组人源化抗PD-L1单克隆抗体"
    )
    result = run(
        doc_id="doc_title_page",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    masked = result.masked_blocks[0].masked_text
    assert (
        masked
        == "试验药物名称：StudyDrug_001（拟定通用名：GenericName_001）\n"
        "药物类别：重组人源化抗Target_001单克隆抗体"
    )
    assert "GenericName_001" in masked
    assert "药物类别：GenericName_001" not in masked
    by_text = {
        (h.entity_type, h.original_text): h for h in result.masked_blocks[0].mask_hits
    }
    assert by_text[("STUDY_DRUG", "VT8802")].token == "StudyDrug_001"
    assert by_text[("GENERIC_NAME", "艾美妥珠单抗")].token == "GenericName_001"
    assert by_text[("TARGET", "PD-L1")].token == "Target_001"


def test_mask_targets_do_not_alter_safety_count_payload() -> None:
    text = "18例（90.0%）试验参与者发生86例次TEAE"
    result = run(
        doc_id="doc_counts",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    assert result.masked_blocks[0].masked_text == text
    assert result.masked_blocks[0].mask_hits == []
