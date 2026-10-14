from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from runtime.run_summaries import build_prepare_analysis_run_summary

RAW_FILE_NAME = "OOJ-VT8802-01 秘密项目 IB.docx"
RAW_SOURCE_DOCX = r"D:\client\XX制药\秘密项目\IB.docx"
FIXED_DOC_ID = "doc_00000000-0000-4000-8000-000000000001"


def test_mask_run_summary_omits_raw_paths(tmp_path: Path) -> None:
    upstream_dir = tmp_path / "extract" / FIXED_DOC_ID
    upstream_dir.mkdir(parents=True)
    (upstream_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "run_id": "extract_20260520_204047",
                "stage": "extract",
                "inputs": {"source_docx": RAW_SOURCE_DOCX},
            }
        ),
        encoding="utf-8",
    )
    input_bundle = upstream_dir / "bundle.json"
    input_bundle.write_text("{}", encoding="utf-8")

    out_dir = tmp_path / "mask" / FIXED_DOC_ID
    out_dir.mkdir(parents=True)

    summary = build_prepare_analysis_run_summary(
        run_id="mask_20260520_220010",
        bundle_dict={
            "doc_id": FIXED_DOC_ID,
            "file_name": RAW_FILE_NAME,
            "file_hash": "sha256:abc123",
            "source_type": "docx",
            "document_meta": {"bundle_schema_version": "0.1.3"},
        },
        language="zh",
        input_bundle=input_bundle,
        output_bundle_path=None,
        analysis_bundle_path=out_dir / "analysis_bundle.json",
        privacy_audit_path=out_dir / "privacy_audit.json",
        mapping_path=out_dir / "mapping.json",
        privacy_transform_applied=True,
        privacy_detectors_configured=["registry"],
        privacy_detectors_used=["registry"],
        analysis_block_count=1,
        paths_base=tmp_path,
    )

    assert "file_name" not in summary
    assert summary["file_hash"] == "sha256:abc123"
    assert "source_docx" not in summary["inputs"]
    assert summary["inputs"]["input_bundle"] == f"extract/{FIXED_DOC_ID}/bundle.json"
    assert RAW_SOURCE_DOCX not in json.dumps(summary, ensure_ascii=False)
    assert RAW_FILE_NAME not in json.dumps(summary, ensure_ascii=False)
