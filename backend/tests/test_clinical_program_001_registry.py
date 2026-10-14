from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from privacy.document_transform import run
from plugins.clinical_trial_doc.privacy.profile import CLINICAL_TRIAL_DOC_PRIVACY_PROFILE
from plugins.clinical_trial_doc.privacy.registry.export import export_clinical_registry_entries
from plugins.clinical_trial_doc.privacy.registry.loader import load_clinical_registry
from plugins.clinical_trial_doc.privacy.registry.records.clinical_program_001 import CLINICAL_PROGRAM
from privacy.detectors.registry_detector import RegistryDetector


def _alias_to_token(alias: str) -> str | None:
    detector = RegistryDetector(export_clinical_registry_entries())
    text = f"prefix {alias} suffix"
    start = text.index(alias)
    end = start + len(alias)
    hits = detector.detect(text)
    span_hits = [h for h in hits if h.start == start and h.end == end]
    if not span_hits:
        return None
    return span_hits[0].predefined_token


def test_load_clinical_registry_includes_clinical_program_001() -> None:
    registry = load_clinical_registry()
    assert "clinical_program_001" in registry
    program = registry["clinical_program_001"]
    assert program.canonical_id == CLINICAL_PROGRAM.canonical_id


def test_clinical_program_001_program_level_structure() -> None:
    program = CLINICAL_PROGRAM

    assert len(program.protocols) == 2
    assert {p.token for p in program.protocols} == {"Protocol_001", "Protocol_002"}

    assert len(program.indications) == 2
    assert {i.token for i in program.indications} == {"Indication_001", "Indication_002"}

    assert len(program.background_drugs) == 2
    assert {d.token for d in program.background_drugs} == {
        "BackgroundDrug_001",
        "BackgroundDrug_002",
    }

    assert len(program.dose_levels) == 3
    assert {d.token for d in program.dose_levels} == {
        "DoseLevel_001",
        "DoseLevel_002",
        "DoseLevel_003",
    }

    assert len(program.targets) == 2
    assert {target.token for target in program.targets} == {
        "TargetClass_001",
        "Target_001",
    }


def test_export_clinical_program_001_alias_mappings() -> None:
    cases = {
        "OOJ-VT8802-01": "Protocol_001",
        "OOJ-VT8802-02": "Protocol_002",
        "晚期实体瘤": "Indication_001",
        "非鳞状非小细胞肺癌": "Indication_002",
        "卡铂": "BackgroundDrug_001",
        "培美曲塞": "BackgroundDrug_002",
        "0.3 mg/kg Q3W": "DoseLevel_001",
        "1 mg/kg Q3W": "DoseLevel_002",
        "3 mg/kg Q3W": "DoseLevel_003",
    }
    for alias, expected_token in cases.items():
        assert _alias_to_token(alias) == expected_token, alias


def test_broad_disease_terms_not_exported_as_indication_aliases() -> None:
    entries = export_clinical_registry_entries()
    indication_aliases = {
        alias
        for entry in entries
        if entry.entity_type == "INDICATION"
        for alias in entry.aliases
    }
    for broad in ("NSCLC", "非小细胞肺癌", "non-small cell lung cancer"):
        assert broad not in indication_aliases


def test_background_drugs_exported_as_background_drug_not_regimen() -> None:
    entries = export_clinical_registry_entries()
    entity_types = {entry.entity_type for entry in entries}
    assert "BACKGROUND_DRUG" in entity_types
    assert "REGIMEN" not in entity_types

    by_canonical = {entry.canonical_id: entry for entry in entries}
    assert by_canonical["background_drug_001"].entity_type == "BACKGROUND_DRUG"
    assert by_canonical["background_drug_002"].entity_type == "BACKGROUND_DRUG"


def test_target_pd_l1_aliases_exclude_directional_phrases() -> None:
    entries = export_clinical_registry_entries()
    target = next(e for e in entries if e.canonical_id == "target_001")
    assert target.token == "Target_001"
    assert "PD-L1" in target.aliases
    assert "anti-PD-L1" not in target.aliases
    assert "抗PD-L1" not in target.aliases


def test_target_class_pd_1_pd_l1_aliases_exported() -> None:
    entries = export_clinical_registry_entries()
    target_class = next(e for e in entries if e.canonical_id == "target_class_001")
    assert target_class.token == "TargetClass_001"
    assert "PD-1/PD-L1" in target_class.aliases
    assert "PD-1 / PD-L1" in target_class.aliases
    assert "PD-1 与 PD-L1" in target_class.aliases


def test_mask_pd_l1_standalone_target() -> None:
    result = run(
        doc_id="doc_pd_l1",
        blocks=[{"block_id": "B1", "text": "表达 PD-L1 的肿瘤。"}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    assert result.masked_blocks[0].masked_text == "表达 Target_001 的肿瘤。"
    hit = result.masked_blocks[0].mask_hits[0]
    assert hit.entity_type == "TARGET"
    assert hit.token == "Target_001"


def test_mask_adr_attribution_preserves_counts_and_tokenizes_drugs() -> None:
    text = (
        "8例（40.0%）试验参与者发生16例次与VT8802相关的ADR；"
        "12例（60.0%）试验参与者发生20例次与卡铂相关的ADR；"
        "11例（55.0%）试验参与者发生16例次与培美曲塞相关的ADR。"
    )
    result = run(
        doc_id="doc_adr_attr",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    masked = result.masked_blocks[0].masked_text
    assert "8例（40.0%）" in masked
    assert "12例（60.0%）" in masked
    assert "11例（55.0%）" in masked
    assert "16例次" in masked
    assert "20例次" in masked
    assert "StudyDrug_001" in masked
    assert "BackgroundDrug_001" in masked
    assert "BackgroundDrug_002" in masked
    assert "VT8802" not in masked
    assert "卡铂" not in masked
    assert "培美曲塞" not in masked

    by_text = {(h.entity_type, h.original_text): h for h in result.masked_blocks[0].mask_hits}
    assert by_text[("STUDY_DRUG", "VT8802")].token == "StudyDrug_001"
    assert by_text[("BACKGROUND_DRUG", "卡铂")].token == "BackgroundDrug_001"
    assert by_text[("BACKGROUND_DRUG", "培美曲塞")].token == "BackgroundDrug_002"
