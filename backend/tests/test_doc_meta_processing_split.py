"""Doc Meta processing/persistence split: pure processor, stage, and pipeline contracts."""

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.doc_meta_installation import (
    CLINICAL_TRIAL_DOC_META_PROFILE,
    build_clinical_trial_doc_meta_summary,
)
from artifacts.doc_meta import DOC_META_BUNDLE_FILENAME
from steps.doc_meta import DocMetaPayloads, build_doc_meta_payloads
from runtime.doc_meta_stage import run_doc_meta_stage
from runtime.io import load_json
from runtime.run_summaries import build_doc_meta_run_summary

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)

DOC_META_FORBIDDEN_IMPORT_MODULES = (
    "runtime.io",
    "runtime.doc_meta_paths",
    "runtime.doc_meta_ids",
    "plugins.clinical_trial_doc",
)

DOC_META_FORBIDDEN_CALLS = (
    "save_json",
    "load_json",
    "mkdir",
    "write_text",
    "open",
)


def _masked_bundle_for_equiv() -> dict:
    return {
        "doc_id": "ib_summary_test_001",
        "file_hash": LINEAGE_FILE_HASH,
        "file_name": "Protocol_001 StudyDrug_001研究者手册 V1.0 2024.03.15.docx",
        "display_name": "Protocol_001 StudyDrug_001研究者手册 V1.0 2024.03.15",
        "source_type": "docx",
        "stage": "prepare_analysis",
        "analysis_bundle_id": "prepare_analysis_ib_summary_test_001",
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


def test_build_doc_meta_payloads_is_pure_and_idempotent() -> None:
    bundle = _masked_bundle_for_equiv()
    profile = CLINICAL_TRIAL_DOC_META_PROFILE
    build_summary = build_clinical_trial_doc_meta_summary
    bundle_id = "doc_meta_equiv_test"

    first = build_doc_meta_payloads(
        analysis_bundle=bundle,
        profile=profile,
        build_summary=build_summary,
        doc_meta_bundle_id=bundle_id,
    )
    second = build_doc_meta_payloads(
        analysis_bundle=bundle,
        profile=profile,
        build_summary=build_summary,
        doc_meta_bundle_id=bundle_id,
    )

    assert first == second
    assert isinstance(first, DocMetaPayloads)
    assert first.doc_meta_bundle["doc_meta_bundle_id"] == bundle_id
    assert first.doc_meta_bundle["file_hash"] == LINEAGE_FILE_HASH
    assert first.doc_meta_bundle["doc_id"] == bundle["doc_id"]
    assert first.doc_meta_bundle["summary"]["study_drug"] == "StudyDrug_001"
    assert first.document_context_preview["strategy"] == profile.context.strategy


def test_build_doc_meta_payloads_rejects_invalid_analysis_bundle_stage() -> None:
    bundle = _masked_bundle_for_equiv()
    bundle["stage"] = "extract"

    with pytest.raises(ValueError, match="doc_meta requires analysis_bundle"):
        build_doc_meta_payloads(
            analysis_bundle=bundle,
            profile=CLINICAL_TRIAL_DOC_META_PROFILE,
            build_summary=build_clinical_trial_doc_meta_summary,
            doc_meta_bundle_id="doc_meta_invalid_stage",
        )


def test_pipeline_and_stage_doc_meta_bundle_payloads_match(tmp_path: Path) -> None:
    bundle = _masked_bundle_for_equiv()
    profile = CLINICAL_TRIAL_DOC_META_PROFILE
    build_summary = build_clinical_trial_doc_meta_summary
    bundle_path = tmp_path / "analysis_bundle.json"
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    out_dir = tmp_path / "runs" / "doc_meta" / "20260608_102618" / bundle["doc_id"]

    explicit_id = "doc_meta_equiv_test"
    pipeline_payloads = build_doc_meta_payloads(
        analysis_bundle=bundle,
        profile=profile,
        build_summary=build_summary,
        doc_meta_bundle_id=explicit_id,
    )
    stage_result = run_doc_meta_stage(
        analysis_bundle_path=bundle_path,
        analysis_bundle=bundle,
        output_dir=out_dir,
        profile=profile,
        build_summary=build_summary,
        run_id=explicit_id,
    )

    disk_doc_meta_bundle = load_json(Path(stage_result["doc_meta_bundle_path"]))
    disk_preview = load_json(Path(stage_result["document_context_preview_path"]))

    assert pipeline_payloads.doc_meta_bundle == disk_doc_meta_bundle
    assert pipeline_payloads.document_context_preview == disk_preview


def test_run_doc_meta_stage_disk_matches_pure_processor(tmp_path: Path) -> None:
    bundle = _masked_bundle_for_equiv()
    profile = CLINICAL_TRIAL_DOC_META_PROFILE
    build_summary = build_clinical_trial_doc_meta_summary
    bundle_path = tmp_path / "analysis_bundle.json"
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    out_dir = tmp_path / "doc_meta_out"
    run_id = "doc_meta_20260608_102618"

    expected = build_doc_meta_payloads(
        analysis_bundle=bundle,
        profile=profile,
        build_summary=build_summary,
        doc_meta_bundle_id=run_id,
    )
    result = run_doc_meta_stage(
        analysis_bundle_path=bundle_path,
        analysis_bundle=bundle,
        output_dir=out_dir,
        profile=profile,
        build_summary=build_summary,
        run_id=run_id,
    )

    assert load_json(Path(result["doc_meta_bundle_path"])) == expected.doc_meta_bundle
    assert (
        load_json(Path(result["document_context_preview_path"]))
        == expected.document_context_preview
    )
    assert result["doc_meta_bundle"] == expected.doc_meta_bundle
    assert result["run_summary_path"]
    assert result["artifacts"]["doc_meta_bundle"] == DOC_META_BUNDLE_FILENAME


def _doc_meta_module_ast() -> ast.Module:
    source_path = BACKEND_ROOT / "steps" / "doc_meta.py"
    return ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))


def test_doc_meta_step_has_no_runtime_persistence_imports() -> None:
    tree = _doc_meta_module_ast()
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    for module_name in DOC_META_FORBIDDEN_IMPORT_MODULES:
        assert module_name not in imported_modules


def test_doc_meta_step_has_no_file_io_calls() -> None:
    tree = _doc_meta_module_ast()
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in DOC_META_FORBIDDEN_CALLS:
            offenders.append(name)
    assert not offenders, f"forbidden IO calls in doc_meta.py: {offenders}"


def test_doc_meta_step_has_no_clinical_plugin_imports() -> None:
    tree = _doc_meta_module_ast()
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    for module_name in DOC_META_FORBIDDEN_IMPORT_MODULES:
        assert not any(
            imported == module_name or imported.startswith(f"{module_name}.")
            for imported in imported_modules
        ), f"forbidden import in doc_meta step: {module_name}"


def test_build_doc_meta_payloads_uses_injected_summary_builder() -> None:
    bundle = _masked_bundle_for_equiv()

    def injected_summary(metadata_base: dict) -> dict:
        return {
            "doc_type": metadata_base.get("doc_type", {}).get("value"),
            "injected_marker": True,
        }

    payloads = build_doc_meta_payloads(
        analysis_bundle=bundle,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
        build_summary=injected_summary,
        doc_meta_bundle_id="doc_meta_injected_summary",
    )

    assert payloads.doc_meta_bundle["summary"]["injected_marker"] is True


def test_run_doc_meta_stage_forwards_supplied_summary_builder(tmp_path: Path) -> None:
    bundle = _masked_bundle_for_equiv()
    bundle_path = tmp_path / "analysis_bundle.json"
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    out_dir = tmp_path / "doc_meta_out"

    def injected_summary(metadata_base: dict) -> dict:
        return {
            "doc_type": metadata_base.get("doc_type", {}).get("value"),
            "injected_marker": True,
        }

    result = run_doc_meta_stage(
        analysis_bundle_path=bundle_path,
        analysis_bundle=bundle,
        output_dir=out_dir,
        profile=CLINICAL_TRIAL_DOC_META_PROFILE,
        build_summary=injected_summary,
        run_id="doc_meta_injected_summary",
    )
    doc_meta_bundle = load_json(Path(result["doc_meta_bundle_path"]))
    assert doc_meta_bundle["summary"]["injected_marker"] is True


def test_run_doc_meta_stage_has_no_run_context_parameter() -> None:
    assert "run_context" not in inspect.signature(run_doc_meta_stage).parameters


def test_build_doc_meta_run_summary_has_no_run_context_parameter() -> None:
    assert "run_context" not in inspect.signature(build_doc_meta_run_summary).parameters


def test_doc_meta_bundle_filename_constant() -> None:
    assert DOC_META_BUNDLE_FILENAME == "doc_meta_bundle.json"
