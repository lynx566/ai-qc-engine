from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.document.language import infer_language_from_source_path
from runtime.run_layout import EXTRACT_RUN_DIR_LAYOUT
from runtime.run_summaries import build_extract_run_summary_dict


class _Bundle:
    doc_id = "ib_001"
    file_name = "ib_001.docx"
    source_type = "docx"
    document_meta = {
        "parser_type": "docx_handlers",
        "parser_version": "0.1.3",
        "bundle_schema_version": "0.1.2",
        "language": "zh",
    }


def test_infer_language_from_source_path_zh() -> None:
    path = Path("samples/docx/zh/extract/ib_extract_heading_001.docx")
    assert infer_language_from_source_path(path) == "zh"


def test_infer_language_from_source_path_en() -> None:
    path = Path("samples/docx/en/extract/ib_001.docx")
    assert infer_language_from_source_path(path) == "en"


def test_infer_language_from_source_path_unknown_parent() -> None:
    path = Path("samples/docx/ib_001.docx")
    assert infer_language_from_source_path(path) is None


def test_extract_run_summary_includes_language() -> None:
    source_docx = Path("samples/docx/zh/extract/ib_extract_heading_001.docx")
    summary = build_extract_run_summary_dict(
        run_id="extract_20260521_120000",
        bundle=_Bundle(),
        export_slices=False,
        source_docx=source_docx,
        git_root=BACKEND_ROOT,
    )
    assert summary["language"] == "zh"
    assert summary["run_dir_layout"] == EXTRACT_RUN_DIR_LAYOUT
