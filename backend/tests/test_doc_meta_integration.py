from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.clinical_program_fixtures import canonical_clinical_program_fields
from core.metadata.rule_engine import detect_doc_type_from_file_name
from steps.doc_meta import build_doc_meta_payloads
from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from privacy.config import PrivacyConfig
from privacy.schemas import SensitiveEntityCandidate
from artifacts.doc_meta import (
    DOC_META_BUNDLE_FILENAME,
    DOCUMENT_CONTEXT_PREVIEW_FILENAME,
)
from application.clinical_trial_doc_consistency_qc.doc_meta_installation import (
    build_clinical_trial_doc_meta_summary,
)
from plugins.clinical_trial_doc.doc_meta.profile_zh import (
    CLINICAL_TRIAL_DOC_META_PROFILE,
)
from runtime.doc_meta_stage import run_doc_meta_stage
from scripts.stage_runners import doc_meta_runner

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _doc_meta_stage_kwargs() -> dict:
    return {
        "profile": CLINICAL_TRIAL_DOC_META_PROFILE,
        "build_summary": build_clinical_trial_doc_meta_summary,
    }


def _doc_meta_payload_kwargs() -> dict:
    return {
        "profile": CLINICAL_TRIAL_DOC_META_PROFILE,
        "build_summary": build_clinical_trial_doc_meta_summary,
    }


class _StaticMaskDetector:
    def __init__(self, candidates: list[SensitiveEntityCandidate]) -> None:
        self._candidates = candidates

    def detect(self, text: str) -> list[SensitiveEntityCandidate]:
        return [
            c
            for c in self._candidates
            if text[c.start : c.end] == c.original_text
        ]


def _mask_candidate(
    text: str,
    term: str,
    entity_type: str,
) -> SensitiveEntityCandidate:
    start = text.index(term)
    return SensitiveEntityCandidate(
        original_text=term,
        entity_type=entity_type,  # type: ignore[arg-type]
        start=start,
        end=start + len(term),
        source="mock",
        confidence=1.0,
    )


def _masked_bundle_for_meta() -> dict:
    return {
        "doc_id": "ib_meta_test_001",
        "file_hash": LINEAGE_FILE_HASH,
        "file_name": "ib_meta_test_001.docx",
        "display_name": "ib_meta_test_001",
        "source_type": "docx",
        "stage": "prepare_analysis",
        "content_blocks": [
            {
                "block_id": "t1",
                "kind": "paragraph",
                "text": "研究者手册（Investigator's Brochure）",
            },
            {
                "block_id": "t2",
                "kind": "paragraph",
                "text": "试验药物：StudyDrug_001",
            },
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def _masked_bundle_for_summary() -> dict:
    return {
        "doc_id": "ib_summary_test_001",
        "file_hash": LINEAGE_FILE_HASH,
        "file_name": "Protocol_001 StudyDrug_001研究者手册 V1.0 2024.03.15.docx",
        "display_name": "Protocol_001 StudyDrug_001研究者手册 V1.0 2024.03.15",
        "source_type": "docx",
        "stage": "prepare_analysis",
        "content_blocks": [
            {
                "block_id": "C0003",
                "kind": "paragraph",
                "order": 1,
                "text": "代号：StudyDrug_001",
            },
            {
                "block_id": "C0006",
                "kind": "paragraph",
                "order": 2,
                "text": "申办者：Sponsor_001",
            },
            {
                "block_id": "C0011",
                "kind": "paragraph",
                "order": 3,
                "text": "注：数据截至2023年12月17日。",
            },
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def test_doc_meta_bundle_summary_and_id(tmp_path: Path) -> None:
    mask_path = tmp_path / "analysis_bundle.json"
    mask_path.write_text(
        json.dumps(_masked_bundle_for_summary(), ensure_ascii=False),
        encoding="utf-8",
    )
    out_dir = tmp_path / "runs" / "doc_meta" / "20260608_102618" / "ib_summary_test_001"
    result = run_doc_meta_stage(
        analysis_bundle_path=mask_path,
        output_dir=out_dir,
        run_id="doc_meta_20260608_102618",
        **_doc_meta_stage_kwargs(),
    )

    meta = json.loads(Path(result["doc_meta_bundle_path"]).read_text(encoding="utf-8"))
    summary = json.loads(Path(result["run_summary_path"]).read_text(encoding="utf-8"))

    profile = CLINICAL_TRIAL_DOC_META_PROFILE

    assert meta["doc_meta_bundle_id"] == "doc_meta_20260608_102618"
    assert meta["doc_meta_bundle_id"] == summary["run_id"]
    assert "summary" in meta

    assert meta["summary"]["doc_type"] == meta["doc_type"]["value"] == "IB"
    assert meta["summary"]["study_drug"] == meta["fields"]["study_drug"]["value"] == "StudyDrug_001"
    assert meta["fields"]["cutoff_date"]["value"] == "2023年12月17日"
    assert meta["summary"]["cutoff_date"] == "2023-12-17"
    assert meta["summary"]["investigator"] is None
    assert meta["fields"]["investigator"]["confidence"] == "none"
    assert meta["summary"]["protocol_ids"] == ["Protocol_001"]
    assert meta["summary"]["reporting_period"] is None

    assert meta["profile"] == profile.name
    assert meta["context_strategy"] == profile.context.strategy
    assert meta["context_block_count"] == profile.context.default_block_count

    study_drug_evidence = meta["fields"]["study_drug"]["evidence"][0]
    assert study_drug_evidence["matched_rule"]
    assert "field:study_drug:" in study_drug_evidence["matched_rule"]
    assert meta["doc_type"]["evidence"]
    assert meta["doc_type"]["evidence"][0]["matched_rule"]


def test_doc_meta_stage_writes_doc_meta_bundle_from_analysis_bundle(tmp_path: Path) -> None:
    mask_path = tmp_path / "analysis_bundle.json"
    mask_path.write_text(
        json.dumps(_masked_bundle_for_meta(), ensure_ascii=False),
        encoding="utf-8",
    )
    out_dir = tmp_path / "doc_meta"

    result = run_doc_meta_stage(
        analysis_bundle_path=mask_path,
        output_dir=out_dir,
        **_doc_meta_stage_kwargs(),
    )

    resolved_doc_meta_bundle_path = Path(result["doc_meta_bundle_path"])
    assert resolved_doc_meta_bundle_path.name == DOC_META_BUNDLE_FILENAME
    assert resolved_doc_meta_bundle_path.is_file()
    preview_path = Path(result["document_context_preview_path"])
    assert preview_path.is_file()
    assert preview_path.name == "document_context_preview.json"

    meta = json.loads(resolved_doc_meta_bundle_path.read_text(encoding="utf-8"))
    assert meta["context_strategy"] == "metadata_sources_v0_1"
    assert meta["context_block_count"] == 20
    assert meta["doc_type"]["value"] == "IB"
    assert meta["doc_type"]["source_texts"] == ["ib_meta_test_001.docx"]
    assert meta["doc_type"]["evidence"][0]["source_type"] == "file_name"
    assert meta["fields"]["study_drug"]["value"] == "StudyDrug_001"


def test_doc_meta_prefers_file_name_over_context_blocks(tmp_path: Path) -> None:
    bundle = _masked_bundle_for_meta()
    bundle["file_name"] = "csr_tag_integration_001.docx"
    mask_path = tmp_path / "analysis_bundle.json"
    mask_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

    payloads = build_doc_meta_payloads(
        analysis_bundle=bundle,
        doc_meta_bundle_id="doc_meta_test",
        **_doc_meta_payload_kwargs(),
    )
    meta = payloads.doc_meta_bundle
    assert meta["doc_type"]["value"] == "CSR"
    assert meta["doc_type"]["source_texts"] == ["csr_tag_integration_001.docx"]
    assert "doc_type_conflict" in meta["warnings"]


@pytest.mark.parametrize(
    ("file_name", "expected_doc_type"),
    [
        ("VT8802_研究者手册_V2.0.docx", "IB"),
        ("艾美妥珠单抗_研发期间安全性更新报告_第2版.docx", "DSUR"),
        ("VT8802-01_最终研究报告.docx", "CSR"),
        ("investigator brochure draft.docx", "IB"),
        ("研究者资料_V1.docx", "IB"),
    ],
)
def test_doc_type_from_zh_file_names(file_name: str, expected_doc_type: str) -> None:
    profile = CLINICAL_TRIAL_DOC_META_PROFILE
    field = detect_doc_type_from_file_name(file_name, profile)
    assert field.value == expected_doc_type
    assert field.source_texts == [file_name]


def test_doc_meta_rejects_extract_bundle(tmp_path: Path) -> None:
    bundle = _masked_bundle_for_meta()
    bundle["stage"] = "extract"

    with pytest.raises(ValueError, match="requires analysis_bundle"):
        build_doc_meta_payloads(
            analysis_bundle=bundle,
            doc_meta_bundle_id="doc_meta_test",
            **_doc_meta_payload_kwargs(),
        )


def test_doc_meta_rejects_legacy_mask_stage() -> None:
    bundle = _masked_bundle_for_meta()
    bundle["stage"] = "mask"

    with pytest.raises(ValueError, match="requires analysis_bundle"):
        build_doc_meta_payloads(
            analysis_bundle=bundle,
            doc_meta_bundle_id="doc_meta_test",
            **_doc_meta_payload_kwargs(),
        )


def test_doc_meta_context_uses_masked_heading_text(tmp_path: Path) -> None:
    raw_heading = "VT8802 2 临床安全性"
    extract_bundle = {
        "doc_id": "heading_mask_test",
        "file_hash": LINEAGE_FILE_HASH,
        "file_name": "VT8802_研究者手册_V2.0.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "h1",
                "kind": "heading",
                "order": 1,
                "text": raw_heading,
                "meta": {
                    "heading_level": 1,
                    "heading_text_stripped": "临床安全性",
                },
            },
            {
                "block_id": "p1",
                "kind": "list_item",
                "order": 2,
                "text": "试验药物：VT8802",
            },
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    detector = _StaticMaskDetector(
        [
            _mask_candidate(raw_heading, "VT8802", "STUDY_DRUG"),
            _mask_candidate("试验药物：VT8802", "VT8802", "STUDY_DRUG"),
        ]
    )
    masked_bundle = prepare_analysis_bundle(
        extract_bundle,
        language="zh",
        detector=detector,
        privacy_config=PrivacyConfig.from_dict(
            {
                "transforms": {
                    "after_extract": {"detectors": ["registry", "regex"]},
                    "after_filter": {"detectors": []},
                }
            }
        ), **canonical_clinical_program_fields()).analysis_bundle

    heading_block = masked_bundle["content_blocks"][0]
    list_block = masked_bundle["content_blocks"][1]
    assert "text" not in heading_block
    assert "text" not in list_block
    assert "VT8802" not in heading_block["analysis_text"]
    assert "StudyDrug_001" in heading_block["analysis_text"]
    assert "临床安全性" in heading_block["analysis_text"]
    assert "heading_text_stripped" not in heading_block.get("meta", {})
    assert "VT8802" not in list_block["analysis_text"]
    assert "StudyDrug_001" in list_block["analysis_text"]

    payloads = build_doc_meta_payloads(
        analysis_bundle=masked_bundle,
        doc_meta_bundle_id="doc_meta_test",
        **_doc_meta_payload_kwargs(),
    )
    preview = payloads.document_context_preview
    ctx_heading = next(b for b in preview["blocks"] if b["kind"] == "heading")
    ctx_list = next(b for b in preview["blocks"] if b["kind"] == "list_item")
    assert ctx_heading["text"] == heading_block["analysis_text"]
    assert "VT8802" not in ctx_heading["text"]
    assert "StudyDrug_001" in ctx_heading["text"]
    assert ctx_list["text"] == list_block["analysis_text"]
    assert "VT8802" not in ctx_list["text"]
    assert "StudyDrug_001" in ctx_list["text"]


def test_doc_meta_stage_writes_all_artifacts_on_disk(tmp_path: Path) -> None:
    mask_path = tmp_path / "analysis_bundle.json"
    mask_path.write_text(
        json.dumps(_masked_bundle_for_meta(), ensure_ascii=False),
        encoding="utf-8",
    )

    out_dir = tmp_path / "runs" / "doc_meta" / "20260530_220001" / "ib_meta_test_001"
    result = run_doc_meta_stage(
        analysis_bundle_path=mask_path,
        output_dir=out_dir,
        **_doc_meta_stage_kwargs(),
    )
    out_dir = Path(result["output_dir"])
    resolved_doc_meta_bundle_path = Path(result["doc_meta_bundle_path"])
    preview_path = Path(result["document_context_preview_path"])
    summary_path = Path(result["run_summary_path"])

    assert out_dir.is_dir()
    assert resolved_doc_meta_bundle_path.is_file()
    assert preview_path.is_file()
    assert summary_path.is_file()
    assert resolved_doc_meta_bundle_path.parent == out_dir.resolve()
    assert resolved_doc_meta_bundle_path.name == DOC_META_BUNDLE_FILENAME
    assert preview_path.name == DOCUMENT_CONTEXT_PREVIEW_FILENAME


def test_doc_meta_stage_run_summary_records_analysis_bundle_input(tmp_path: Path) -> None:
    mask_path = tmp_path / "analysis_bundle.json"
    mask_path.write_text(
        json.dumps(_masked_bundle_for_meta(), ensure_ascii=False),
        encoding="utf-8",
    )

    out_dir = tmp_path / "runs" / "doc_meta" / "20260530_220000" / "ib_meta_test_001"
    result = run_doc_meta_stage(
        analysis_bundle_path=mask_path,
        output_dir=out_dir,
        **_doc_meta_stage_kwargs(),
    )

    summary_path = Path(result["run_summary_path"])
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["stage"] == "doc_meta"
    assert summary["pipeline"] == ["extract", "prepare_analysis", "doc_meta"]
    assert summary["inputs"]["analysis_bundle"] == mask_path.resolve().as_posix()
    assert summary["outputs"]["doc_meta_bundle"] == DOC_META_BUNDLE_FILENAME
    assert summary["outputs"]["document_context_preview"] == "document_context_preview.json"

    profile = CLINICAL_TRIAL_DOC_META_PROFILE
    meta_profile = summary["metadata_profile"]
    assert meta_profile["name"] == profile.name
    from runtime.run_summaries import metadata_profile_version

    assert meta_profile["version"] == metadata_profile_version(profile)
    assert meta_profile["context_strategy"] == profile.context.strategy
    assert meta_profile["context_block_count"] == profile.context.default_block_count


def test_doc_meta_does_not_read_extract_bundle(tmp_path: Path) -> None:
    extract_path = tmp_path / "bundle.json"
    extract_path.write_text(json.dumps({"doc_id": "x"}), encoding="utf-8")
    mask_path = tmp_path / "analysis_bundle.json"
    mask_path.write_text(
        json.dumps(_masked_bundle_for_meta(), ensure_ascii=False),
        encoding="utf-8",
    )

    original_open = Path.open

    def guarded_open(self, *args, **kwargs):
        if self.resolve() == extract_path.resolve():
            raise AssertionError("doc_meta must not read extract bundle")
        return original_open(self, *args, **kwargs)

    with patch.object(Path, "open", guarded_open):
        run_doc_meta_stage(
            analysis_bundle_path=mask_path,
            output_dir=tmp_path / "doc_meta",
            **_doc_meta_stage_kwargs(),
        )


def _masked_bundle_multi_protocol() -> dict:
    """IB bundle whose early block references two protocol placeholders."""
    return {
        "doc_id": "ib_multi_protocol_001",
        "file_hash": LINEAGE_FILE_HASH,
        "file_name": "StudyDrug_001研究者手册 V1.0 2024.03.15.docx",
        "display_name": "StudyDrug_001研究者手册 V1.0 2024.03.15",
        "source_type": "docx",
        "stage": "prepare_analysis",
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "order": 1,
                "analysis_text": "研究者手册",
            },
            {
                "block_id": "C0002",
                "kind": "paragraph",
                "order": 2,
                "analysis_text": (
                    "通用名称：GenericName_001 代号：StudyDrug_001 版本号：1.3 "
                    "版本日期：2024.04.01 适用范围：Protocol_001、Protocol_002 "
                    "申办者：Sponsor_001"
                ),
            },
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def test_protocol_id_multi_match_populates_values(tmp_path: Path) -> None:
    """When early_block contains two Protocol_ placeholders, both are captured."""
    payloads = build_doc_meta_payloads(
        analysis_bundle=_masked_bundle_multi_protocol(),
        doc_meta_bundle_id="doc_meta_test",
        **_doc_meta_payload_kwargs(),
    )
    meta = payloads.doc_meta_bundle

    protocol_field = meta["fields"]["protocol_id"]
    assert protocol_field["value"] == "Protocol_001"
    assert protocol_field["values"] == ["Protocol_001", "Protocol_002"]
    assert protocol_field["confidence"] == "high"


def test_protocol_id_multi_match_summary_protocol_ids(tmp_path: Path) -> None:
    """Summary always exposes protocol_ids as a list; multi-match yields all values."""
    payloads = build_doc_meta_payloads(
        analysis_bundle=_masked_bundle_multi_protocol(),
        doc_meta_bundle_id="doc_meta_test",
        **_doc_meta_payload_kwargs(),
    )
    summary = payloads.doc_meta_bundle["summary"]

    assert "protocol_id" not in summary
    assert summary["protocol_ids"] == ["Protocol_001", "Protocol_002"]


def test_protocol_id_single_match_summary_protocol_ids_list(tmp_path: Path) -> None:
    """Summary exposes protocol_ids as a one-element list for a single match."""
    bundle = _masked_bundle_for_summary()
    payloads = build_doc_meta_payloads(
        analysis_bundle=bundle,
        doc_meta_bundle_id="doc_meta_test",
        **_doc_meta_payload_kwargs(),
    )
    summary = payloads.doc_meta_bundle["summary"]

    assert "protocol_id" not in summary
    assert summary["protocol_ids"] == ["Protocol_001"]


def test_protocol_id_no_match_summary_empty_protocol_ids(tmp_path: Path) -> None:
    """Summary exposes protocol_ids as an empty list when no protocol is found."""
    payloads = build_doc_meta_payloads(
        analysis_bundle=_masked_bundle_for_meta(),
        doc_meta_bundle_id="doc_meta_test",
        **_doc_meta_payload_kwargs(),
    )
    summary = payloads.doc_meta_bundle["summary"]

    assert "protocol_id" not in summary
    assert summary["protocol_ids"] == []


def test_doc_meta_runner_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mask_path = tmp_path / "analysis_bundle.json"
    mask_path.write_text(
        json.dumps(_masked_bundle_for_meta(), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(doc_meta_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        doc_meta_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["doc_meta_runner.py", "--analysis-bundle", str(mask_path)],
    )
    doc_meta_runner.main()

    doc_meta_runs = [
        p
        for p in (tmp_path / "runs" / "doc_meta").glob("*/*")
        if (p / DOC_META_BUNDLE_FILENAME).is_file()
    ]
    assert len(doc_meta_runs) == 1
    out_dir = doc_meta_runs[0]
    assert (out_dir / DOC_META_BUNDLE_FILENAME).is_file()
    assert (out_dir / DOCUMENT_CONTEXT_PREVIEW_FILENAME).is_file()
    assert (out_dir / "run_summary.json").is_file()
    summary = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["run_dir_layout"] == "stage/run_id/doc_dir"
