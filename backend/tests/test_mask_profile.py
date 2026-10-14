from __future__ import annotations

import json
import sys
from dataclasses import replace
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
from privacy.config import PrivacyConfig
from privacy.detectors.factory import (
    _build_composite_detector,
    build_mask_detectors,
)
from privacy.document_transform import (
    run,
    sanitize_document_identity_for_mask,
    to_dict,
)
from privacy.mapping_store import MappingStore
from privacy.profile import PrivacyProfile
from privacy.schemas import SensitiveEntityCandidate
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


def test_default_profile_filters_non_mask_entity_types() -> None:
    text = "共报告不良反应12例。"
    detector = _StaticDetector(
        [
            _candidate(text, "不良反应", "ADR"),
            _candidate(text, "12例", "COUNT"),
        ]
    )
    result = run(
        doc_id="doc",
        blocks=[{"block_id": "B1", "text": text}],
        detector=detector,
        language="zh",
    )
    assert result.masked_blocks[0].mask_hits == []
    assert result.masked_blocks[0].masked_text == text


def test_default_profile_masks_allowed_types() -> None:
    text = "试验参与者张三入组。"
    detector = _StaticDetector([_candidate(text, "张三", "SUBJECT")])
    result = run(
        doc_id="doc",
        blocks=[{"block_id": "B1", "text": text}],
        detector=detector,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    assert len(result.masked_blocks[0].mask_hits) == 1
    assert result.masked_blocks[0].mask_hits[0].entity_type == "SUBJECT"
    assert "张三" not in result.masked_blocks[0].masked_text


def test_date_shift_recorded_as_replacement_mask_hit() -> None:
    bundle = {
        "doc_id": "doc",
        "file_name": "doc.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "B1",
                "kind": "paragraph",
                "text": "入组日期2026年4月20日。",
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    detector = _StaticDetector(
        [_candidate("入组日期2026年4月20日。", "2026年4月20日", "DATE")]
    )
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        detector=detector,
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    block = result.mask_result.masked_blocks[0]
    assert len(block.mask_hits) == 1
    hit = block.mask_hits[0]
    assert hit.entity_type == "DATE"
    assert hit.source == "date_shift"
    assert hit.original_text == "2026年4月20日"
    assert hit.token == "2026年5月7日"
    assert "2026年5月7日" in block.masked_text
    assert "2026年4月20日" not in block.masked_text


def test_default_profile_masks_registry_study_drug() -> None:
    text = "药物 VT8802 由申办方某某生物医药有限公司支持。"
    result = run(
        doc_id="doc",
        blocks=[{"block_id": "B1", "text": text}],
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    block = result.masked_blocks[0]
    masked_types = {h.entity_type for h in block.mask_hits}
    assert "STUDY_DRUG" in masked_types
    assert "SPONSOR" in masked_types
    assert "某某生物医药有限公司" not in block.masked_text


def test_build_composite_detector_uses_registry_and_regex_only() -> None:
    profile = PrivacyProfile(
        entity_types_to_mask=frozenset({"SUBJECT"}),
        entity_types_to_keep=frozenset(),
    )
    _detectors, kinds = build_mask_detectors(profile=profile, language="zh")
    assert "dictionary" not in kinds


def test_date_shift_disabled_when_offset_zero() -> None:
    bundle = {
        "doc_id": "doc",
        "file_name": "doc.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "B1",
                "kind": "paragraph",
                "text": "入组日期2026年4月20日。",
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    profile = replace(
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        date_shift_offset_days=0,
    )
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        profile=profile,
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    block = result.mask_result.masked_blocks[0]
    assert "2026年4月20日" in block.masked_text
    assert result.mask_result.date_shift == {"enabled": False, "offset_days": 0}


def test_build_mask_detectors_omits_regex_when_no_rules_for_language() -> None:
    profile = replace(
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        regex_rules={},
    )
    _detectors, kinds = build_mask_detectors(profile=profile, language="zh")
    assert "regex" not in kinds
    assert "registry" in kinds
    assert "dictionary" not in kinds


def test_profile_date_shift_offset_days() -> None:
    bundle = {
        "doc_id": "doc",
        "file_name": "doc.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "B1",
                "kind": "paragraph",
                "text": "入组日期2026年4月20日。",
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    profile = replace(
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        date_shift_offset_days=3,
    )
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        profile=profile,
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    block = result.mask_result.masked_blocks[0]
    assert "2026年4月23日" in block.masked_text
    assert result.mask_result.date_shift == {"enabled": True, "offset_days": 3}


def test_mask_result_includes_detector_kinds_for_registry_regex_config() -> None:
    bundle = {
        "doc_id": "doc",
        "file_name": "doc.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [{"block_id": "B1", "kind": "paragraph", "text": "测试"}],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    assert result.mask_result.detectors == ["registry", "regex"]


def test_build_mask_detectors_excludes_uie_by_default() -> None:
    _detectors, kinds = build_mask_detectors(
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
    )
    assert kinds == ["registry", "regex"]
    assert "uie" not in kinds
    assert "local_model" not in kinds


def test_build_mask_detectors_enable_uie_includes_uie(monkeypatch) -> None:
    class _FakeUIEDetector:
        def __init__(self, schema, denylist=None):
            self.schema = schema
            self.denylist = denylist

        def detect(self, text: str):
            return []

    import privacy.detectors.uie_detector as uie_mod

    monkeypatch.setattr(uie_mod, "UIEDetector", _FakeUIEDetector)

    _detectors, kinds = build_mask_detectors(
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
        enable_uie=True,
    )
    assert kinds == ["registry", "regex", "uie"]
    assert isinstance(_detectors[-1], _FakeUIEDetector)


def test_mask_bundle_default_identity_does_not_import_uie(monkeypatch) -> None:
    imported: list[str] = []
    import builtins

    real_import = builtins.__import__

    def tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "privacy.detectors.uie_detector":
            imported.append(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", tracking_import)

    bundle = {
        "doc_id": "doc",
        "file_name": "doc.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [{"block_id": "B1", "kind": "paragraph", "text": "测试"}],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE, **canonical_clinical_program_fields())
    assert imported == []
    assert result.mask_result is None
    assert result.analysis_bundle["privacy_enabled"] is False


def test_mask_bundle_after_extract_uie_records_uie_in_detectors(monkeypatch) -> None:
    class _FakeUIEDetector:
        def __init__(self, schema, denylist=None):
            pass

        def detect(self, text: str):
            return []

    from plugins.clinical_trial_doc.prepare_analysis import resolver as resolver_module

    monkeypatch.setattr(resolver_module, "_uie_runtime_available", lambda: True)
    monkeypatch.setattr(resolver_module, "UIEDetector", _FakeUIEDetector)

    bundle = {
        "doc_id": "doc",
        "file_name": "doc.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [{"block_id": "B1", "kind": "paragraph", "text": "测试"}],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    config = PrivacyConfig.from_dict(
        {
            "transforms": {
                "after_extract": {"detectors": ["registry", "regex", "uie"]},
                "after_filter": {"detectors": []},
            }
        }
    )
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        privacy_config=config, **canonical_clinical_program_fields())
    assert result.mask_result.detectors == ["registry", "regex", "uie"]
    mask_output = to_dict(result.mask_result)
    assert mask_output["detectors"] == ["registry", "regex", "uie"]


RAW_IB_FILE_NAME = "OOJ-VT8802-01 艾美妥珠单抗研究者手册.docx"
RAW_IB_DISPLAY = "OOJ-VT8802-01 艾美妥珠单抗研究者手册"
RAW_SOURCE_PATH = r"D:\client\uploads\OOJ-VT8802-01 艾美妥珠单抗研究者手册.docx"


def _ib_identity_detector() -> _StaticDetector:
    candidates: list[SensitiveEntityCandidate] = []
    for text in (
        RAW_IB_DISPLAY,
        RAW_IB_FILE_NAME.removesuffix(".docx"),
        "VT8802",
        "试验药物：VT8802",
    ):
        if "VT8802" in text:
            candidates.append(_candidate(text, "VT8802", "STUDY_DRUG"))
        if "OOJ-VT8802-01" in text:
            start = text.index("OOJ-VT8802-01")
            candidates.append(
                SensitiveEntityCandidate(
                    original_text="OOJ-VT8802-01",
                    entity_type="RECORD_ID",  # type: ignore[arg-type]
                    start=start,
                    end=start + len("OOJ-VT8802-01"),
                    source="mock",
                    confidence=1.0,
                )
            )
        if "艾美妥珠单抗" in text:
            candidates.append(_candidate(text, "艾美妥珠单抗", "STUDY_DRUG"))
    return _StaticDetector(candidates)


def test_masked_bundle_identity_fields_sanitized() -> None:
    bundle = {
        "doc_id": "doc_test_identity",
        "file_name": RAW_IB_FILE_NAME,
        "display_name": RAW_IB_DISPLAY,
        "source_type": "docx",
        "document_meta": {
            "source_path": RAW_SOURCE_PATH,
            "parser_version": "0.1.0",
            "language": "zh",
        },
        "content_blocks": [
            {"block_id": "B1", "kind": "paragraph", "text": "试验药物：VT8802"},
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        detector=_ib_identity_detector(),
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    masked = result.analysis_bundle

    assert masked["file_name"] != RAW_IB_FILE_NAME
    assert masked["display_name"] != RAW_IB_DISPLAY
    assert "OOJ" not in masked["file_name"]
    assert "VT8802" not in masked["file_name"]
    assert "艾美妥珠单抗" not in masked["file_name"]
    assert "StudyDrug_" in masked["file_name"]
    assert masked["file_name"].endswith(".docx")
    assert "OOJ" not in masked["display_name"]
    assert "VT8802" not in masked["display_name"]
    assert "艾美妥珠单抗" not in masked["display_name"]
    assert "StudyDrug_" in masked["display_name"]
    assert masked["document_meta"]["source_path"] is None
    assert masked["document_meta"]["parser_version"] == "0.1.0"


def test_masked_bundle_filename_and_body_share_study_drug_token() -> None:
    bundle = {
        "doc_id": "doc_mapping_consistency",
        "file_name": "VT8802_研究者手册.docx",
        "display_name": "VT8802_研究者手册",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {"block_id": "B1", "kind": "paragraph", "text": "试验药物：VT8802"},
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    detector = _StaticDetector(
        [
            _candidate("试验药物：VT8802", "VT8802", "STUDY_DRUG"),
            _candidate("VT8802_研究者手册", "VT8802", "STUDY_DRUG"),
            _candidate("VT8802_研究者手册.docx".removesuffix(".docx"), "VT8802", "STUDY_DRUG"),
        ]
    )
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        detector=detector,
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    body_token = result.analysis_bundle["content_blocks"][0]["analysis_text"]
    file_token = result.analysis_bundle["file_name"]
    display_token = result.analysis_bundle["display_name"]

    assert "StudyDrug_001" in body_token
    assert "StudyDrug_001" in file_token
    assert "StudyDrug_001" in display_token
    assert body_token.count("StudyDrug_001") >= 1
    assert file_token.count("StudyDrug_001") == display_token.count("StudyDrug_001")


def test_masked_bundle_no_source_path_leak() -> None:
    bundle = {
        "doc_id": "doc_no_path",
        "file_name": RAW_IB_FILE_NAME,
        "display_name": RAW_IB_DISPLAY,
        "source_type": "docx",
        "document_meta": {"source_path": RAW_SOURCE_PATH},
        "content_blocks": [{"block_id": "B1", "kind": "paragraph", "text": "x"}],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        detector=_StaticDetector([]),
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    serialized = json.dumps(result.analysis_bundle, ensure_ascii=False)

    assert RAW_SOURCE_PATH not in serialized
    assert r"D:\client" not in serialized
    assert "client/uploads" not in serialized.lower()
    assert result.analysis_bundle["document_meta"]["source_path"] is None


def test_mask_bundle_masks_heading_and_list_item_blocks() -> None:
    raw_heading = "VT8802 2 临床安全性"
    bundle = {
        "doc_id": "doc",
        "file_name": "VT8802_研究者手册_V2.0.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "H1",
                "kind": "heading",
                "text": raw_heading,
                "meta": {
                    "heading_level": 1,
                    "heading_text_stripped": "临床安全性",
                },
            },
            {
                "block_id": "L1",
                "kind": "list_item",
                "text": "试验药物：VT8802",
            },
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    detector = _StaticDetector(
        [
            _candidate(raw_heading, "VT8802", "STUDY_DRUG"),
            _candidate("试验药物：VT8802", "VT8802", "STUDY_DRUG"),
        ]
    )
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        detector=detector,
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    heading = result.analysis_bundle["content_blocks"][0]
    list_item = result.analysis_bundle["content_blocks"][1]

    assert "text" not in heading
    assert "VT8802" not in heading["analysis_text"]
    assert "StudyDrug_001" in heading["analysis_text"]
    assert "heading_text_stripped" not in heading.get("meta", {})
    assert heading["meta"]["heading_level"] == 1
    assert "heading_number" not in heading.get("meta", {})
    assert "text" not in list_item
    assert "VT8802" not in list_item["analysis_text"]
    assert "StudyDrug_001" in list_item["analysis_text"]


def _collect_block_keys(bundle: dict) -> set[str]:
    keys: set[str] = set()
    for group in (
        "content_blocks",
        "front_matter_blocks",
        "table_blocks",
        "format_blocks",
    ):
        for block in bundle.get(group) or []:
            if isinstance(block, dict):
                keys.update(block.keys())
    return keys


def test_masked_bundle_privacy_boundary_excludes_raw_text() -> None:
    raw_heading = "6.1 VT-8802（艾美妥珠单抗）"
    bundle = {
        "doc_id": "doc_privacy",
        "file_name": "VT8802_研究者手册.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "C0008",
                "kind": "heading",
                "text": raw_heading,
                "meta": {
                    "heading_level": 2,
                    "heading_text_stripped": "VT-8802（艾美妥珠单抗）",
                    "style_name": "Heading 2",
                },
            },
            {
                "block_id": "P1",
                "kind": "paragraph",
                "text": "试验药物：VT8802",
            },
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    detector = _StaticDetector(
        [
            _candidate(raw_heading, "VT-8802", "STUDY_DRUG"),
            _candidate(raw_heading, "艾美妥珠单抗", "STUDY_DRUG"),
            _candidate("试验药物：VT8802", "VT8802", "STUDY_DRUG"),
        ]
    )
    result = prepare_analysis_bundle(
        bundle,
        language="zh",
        detector=detector,
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    masked_bundle = result.analysis_bundle
    mask_output = to_dict(result.mask_result)

    assert "text" not in _collect_block_keys(masked_bundle)
    for group in (
        "content_blocks",
        "front_matter_blocks",
        "table_blocks",
        "format_blocks",
    ):
        for block in masked_bundle.get(group) or []:
            meta = block.get("meta") or {}
            assert "heading_text_stripped" not in meta

    heading = masked_bundle["content_blocks"][0]
    assert "VT-8802" not in heading["analysis_text"]
    assert "艾美妥珠单抗" not in heading["analysis_text"]
    assert "StudyDrug_" in heading["analysis_text"]
    assert heading["meta"]["heading_level"] == 2
    assert "heading_number" not in heading.get("meta", {})
    assert heading["meta"]["style_name"] == "Heading 2"

    block_output = mask_output["masked_blocks"][0]
    assert block_output["original_text"] == raw_heading
    assert block_output["mask_hits"]


def test_sanitize_document_identity_clears_source_path() -> None:
    profile = replace(
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        entity_types_to_mask=frozenset({"STUDY_DRUG"}),
    )
    detector = _StaticDetector([])
    _file, _display, meta, _hits = sanitize_document_identity_for_mask(
        file_name="ib.docx",
        display_name="ib",
        document_meta={
            "source_path": str(
                BACKEND_ROOT / "samples/docx/zh/tag_integration/ib.docx"
            ),
            "parser_version": "0.1.0",
        },
        detector=detector,
        profile=profile,
        mapping_store=MappingStore(),
    )
    assert meta["source_path"] is None
    assert meta["parser_version"] == "0.1.0"


def test_extract_bundle_identity_unchanged_after_mask() -> None:
    extract_bundle = {
        "doc_id": "doc_extract_raw",
        "file_name": RAW_IB_FILE_NAME,
        "display_name": RAW_IB_DISPLAY,
        "source_type": "docx",
        "document_meta": {"source_path": RAW_SOURCE_PATH},
        "content_blocks": [
            {"block_id": "B1", "kind": "paragraph", "text": "试验药物：VT8802"},
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    raw_snapshot = json.dumps(extract_bundle, ensure_ascii=False)
    result = prepare_analysis_bundle(
        extract_bundle,
        language="zh",
        detector=_ib_identity_detector(),
        privacy_config=_registry_regex_config(), **canonical_clinical_program_fields())
    assert json.dumps(extract_bundle, ensure_ascii=False) == raw_snapshot
    assert extract_bundle["file_name"] == RAW_IB_FILE_NAME
    assert extract_bundle["document_meta"]["source_path"] == RAW_SOURCE_PATH
    assert result.analysis_bundle["file_name"] != RAW_IB_FILE_NAME


def test_mask_module_imports_without_paddlenlp() -> None:
    import privacy.detectors.factory as factory_module

    assert factory_module._build_composite_detector is not None


def test_build_composite_detector_uses_profile_regex_rules() -> None:
    from privacy.detectors.regex_detector import RegexDetector

    profile = replace(
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        regex_rules={"zh": CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.regex_rules["zh"]},
    )
    detector = _build_composite_detector(language="zh", profile=profile)
    inner = detector._detectors[1]  # type: ignore[attr-defined]
    assert isinstance(inner, RegexDetector)


def test_unsupported_language_still_builds_detector() -> None:
    detector = _build_composite_detector(
        language="en",
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
    )
    assert detector.detect("hello") == []
