"""Filter stage runtime unit tests (temp dirs only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
)
from operations.filter.variant_registry import resolve_filter_job_variant
from artifacts.zone_match_bundle import ZONE_MATCH_BUNDLE_DEBUG_FILENAME, ZONE_MATCH_BUNDLE_FILENAME
from core.document.sentence_index import build_sentences
from runtime.filter_stage import FilterStageInvocation, run_filter_stage
from runtime.run_ids import utc_run_stamp
from tests.filter_test_helpers import write_prepare_analysis_filter_input

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _paragraph_block(*, block_id: str, analysis_text: str) -> dict:
    sentences = build_sentences(
        block_id,
        "paragraph",
        raw_text=analysis_text,
        normalized_text=analysis_text,
    )
    return {
        "block_id": block_id,
        "kind": "paragraph",
        "analysis_text": analysis_text,
        "sentences": [
            {
                "sentence_id": sentence.sentence_id,
                "analysis_text": sentence.normalized_text,
            }
            for sentence in sentences
        ],
    }


def _sample_analysis_bundle() -> dict:
    return {
        "doc_id": "ib_001",
        "file_hash": LINEAGE_FILE_HASH,
        "file_name": "ib_001.docx",
        "source_type": "docx",
        "stage": "prepare_analysis",
        "document_meta": {
            "parser_type": "docx_handlers",
            "parser_version": "0.1.3",
            "bundle_schema_version": "0.1.2",
        },
        "content_blocks": [
            {
                "block_id": "h1",
                "kind": "heading",
                "analysis_text": "<<SPONSOR>> 5.2.1 临床安全性",
                "meta": {
                    "heading_level": 3,
                    "heading_text_stripped": "临床安全性",
                },
            },
            _paragraph_block(
                block_id="p1",
                analysis_text="analysis safety paragraph",
            ),
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }


def _sample_ib_dual_zone_bundle() -> dict:
    return {
        "doc_id": "ib_safety_tag_integration_001",
        "file_hash": LINEAGE_FILE_HASH,
        "file_name": "ib_safety_tag_integration_001.docx",
        "source_type": "docx",
        "document_meta": {
            "parser_type": "docx_handlers",
            "parser_version": "0.1.3",
            "bundle_schema_version": "0.1.2",
        },
        "content_blocks": [
            {
                "block_id": "h_summary",
                "kind": "heading",
                "text": "1 摘要",
                "meta": {
                    "heading_level": 1,
                    "heading_text_stripped": "摘要",
                },
            },
            {
                "block_id": "p_summary",
                "kind": "paragraph",
                "text": "masked summary body",
            },
            {
                "block_id": "h_safety",
                "kind": "heading",
                "text": "2 临床安全性",
                "meta": {
                    "heading_level": 1,
                    "heading_text_stripped": "临床安全性",
                },
            },
            {
                "block_id": "h_ae",
                "kind": "heading",
                "text": "2.1 不良事件汇总",
                "meta": {
                    "heading_level": 2,
                    "heading_text_stripped": "不良事件汇总",
                },
            },
            {
                "block_id": "p_safety",
                "kind": "paragraph",
                "text": "masked safety paragraph",
            },
        ],
    }


def _mask_output_for_debug() -> dict:
    return {
        "masked_blocks": [
            {
                "block_id": "p1",
                "original_text": "original safety paragraph",
                "masked_text": "masked safety paragraph",
            }
        ],
        "mapping": {},
    }


def _ib_clinical_safety_profile():
    return resolve_filter_job_variant(
        filter_job_id="ib_clinical_safety",
        language="zh",
        filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
    )


def _invocation(
    tmp_path: Path,
    *,
    custom_output_dir: Path | None = None,
    multi_profile: bool = False,
) -> FilterStageInvocation:
    stamp = utc_run_stamp()
    session_dir = tmp_path / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    return FilterStageInvocation(
        stamp=stamp,
        session_dir=session_dir,
        runs_root=tmp_path / "runs",
        git_root=tmp_path,
        multi_bundle=False,
        multi_profile=multi_profile,
        custom_output_dir=custom_output_dir,
    )


def test_run_filter_stage_persists_public_artifacts(tmp_path: Path) -> None:
    masked_path = write_prepare_analysis_filter_input(
        tmp_path / "ib_001",
        _sample_analysis_bundle(),
    )
    out_dir = tmp_path / "filter_out"
    profile = _ib_clinical_safety_profile()

    result = run_filter_stage(
        bundle_path=masked_path,
        profile=profile,
        zone_key="ib_clinical_safety_zh",
        invocation=_invocation(tmp_path, custom_output_dir=out_dir),
        git_provenance={"git_commit": "abc", "git_dirty": False},
        paths_base=tmp_path,
    )

    assert result.zone_bundle_path == out_dir / ZONE_MATCH_BUNDLE_FILENAME
    assert result.coverage_bundle_path == out_dir / "coverage_bundle.json"
    assert result.run_summary_path == out_dir / "run_summary.json"
    assert result.zone_bundle_debug_path is None

    zone_bundle = json.loads(result.zone_bundle_path.read_text(encoding="utf-8"))
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))

    assert zone_bundle["input_stage"] == "prepare_analysis"
    assert zone_bundle["pipeline"] == ["extract", "prepare_analysis", "filter"]
    assert zone_bundle["resolved_filter_strategy_id"] == "heading_zone"
    assert summary["input_stage"] == "prepare_analysis"
    assert summary["zone_key"] == "ib_clinical_safety_zh"
    assert summary["resolved_filter_strategy_id"] == "heading_zone"
    assert summary["output_privacy_contract"]["zone_match_bundle"][
        "artifact_privacy_level"
    ] == "public_masked_v0.2"
    assert summary["artifacts"]["zone_match_bundle_debug"] is None
    assert (out_dir / "coverage_bundle.json").is_file()


def test_run_filter_stage_requires_block_manifest(tmp_path: Path) -> None:
    mask_dir = tmp_path / "ib_001"
    mask_dir.mkdir()
    bundle_path = mask_dir / "analysis_bundle.json"
    bundle_path.write_text(json.dumps(_sample_analysis_bundle()), encoding="utf-8")
    profile = _ib_clinical_safety_profile()

    with pytest.raises(FileNotFoundError, match="block_manifest.json is required"):
        run_filter_stage(
            bundle_path=bundle_path,
            profile=profile,
            zone_key="ib_clinical_safety_zh",
            invocation=_invocation(tmp_path),
        )


def test_run_filter_stage_dual_zone_profiles(tmp_path: Path) -> None:
    masked_path = write_prepare_analysis_filter_input(
        tmp_path / "ib_safety_tag_integration_001",
        _sample_ib_dual_zone_bundle(),
    )

    overview_profile = resolve_filter_job_variant(
        filter_job_id="ib_overview",
        language="zh",
        filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
    )
    safety_profile = resolve_filter_job_variant(
        filter_job_id="ib_clinical_safety",
        language="zh",
        filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
    )
    out_overview = tmp_path / "overview"
    out_safety = tmp_path / "safety"

    overview_result = run_filter_stage(
        bundle_path=masked_path,
        profile=overview_profile,
        zone_key="ib_overview_zh",
        invocation=_invocation(tmp_path, custom_output_dir=out_overview),
    )
    safety_result = run_filter_stage(
        bundle_path=masked_path,
        profile=safety_profile,
        zone_key="ib_clinical_safety_zh",
        invocation=_invocation(tmp_path, custom_output_dir=out_safety),
    )

    overview_bundle = json.loads(
        overview_result.zone_bundle_path.read_text(encoding="utf-8")
    )
    safety_bundle = json.loads(
        safety_result.zone_bundle_path.read_text(encoding="utf-8")
    )

    assert overview_bundle["zone_config_name"] == "ib_overview_zh"
    assert safety_bundle["zone_config_name"] == "ib_clinical_safety_zh"
    assert "zone_config_names" not in overview_bundle
    assert "zone_config_names" not in safety_bundle


def test_run_filter_stage_debug_writes_original_text(tmp_path: Path) -> None:
    mask_dir = tmp_path / "ib_001"
    masked_path = write_prepare_analysis_filter_input(
        mask_dir,
        _sample_analysis_bundle(),
    )
    (mask_dir / "privacy_audit.json").write_text(
        json.dumps(_mask_output_for_debug()),
        encoding="utf-8",
    )
    out_dir = tmp_path / "filter_out"
    profile = _ib_clinical_safety_profile()

    result = run_filter_stage(
        bundle_path=masked_path,
        profile=profile,
        zone_key="ib_clinical_safety_zh",
        invocation=_invocation(tmp_path, custom_output_dir=out_dir),
        include_debug=True,
        paths_base=tmp_path,
    )

    public = json.loads(result.zone_bundle_path.read_text(encoding="utf-8"))
    debug = json.loads(result.zone_bundle_debug_path.read_text(encoding="utf-8"))
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))

    para_public = public["matched_zones"][0]["blocks"][1]
    para_debug = debug["matched_zones"][0]["blocks"][1]
    assert "original_text" not in para_public
    assert para_debug["original_text"] == "original safety paragraph"
    assert summary["artifacts"]["zone_match_bundle_debug"] == ZONE_MATCH_BUNDLE_DEBUG_FILENAME


def test_run_filter_stage_debug_without_privacy_audit_warns(tmp_path: Path) -> None:
    masked_path = write_prepare_analysis_filter_input(
        tmp_path / "ib_001",
        _sample_analysis_bundle(),
    )
    out_dir = tmp_path / "filter_out"
    profile = _ib_clinical_safety_profile()

    with pytest.warns(UserWarning, match="privacy_audit.json"):
        result = run_filter_stage(
            bundle_path=masked_path,
            profile=profile,
            zone_key="ib_clinical_safety_zh",
            invocation=_invocation(tmp_path, custom_output_dir=out_dir),
            include_debug=True,
        )

    assert result.zone_bundle_path.is_file()
    assert result.zone_bundle_debug_path is None


def test_assert_public_artifact_safe_adds_error_prefix() -> None:
    from runtime.filter_stage import _assert_public_artifact_safe

    def _failing_checker(_payload: dict) -> None:
        raise ValueError("forbidden key 'raw_rows' at coverage_bundle.coverage[0]")

    with pytest.raises(
        ValueError,
        match=r"^\[filter_stage safety:coverage_bundle\] forbidden key 'raw_rows'",
    ):
        _assert_public_artifact_safe(
            artifact_name="coverage_bundle",
            payload={"coverage": []},
            checker=_failing_checker,
        )


def test_filter_stage_result_doc_id_is_source_identity_not_layout_leaf(
    tmp_path: Path,
) -> None:
    """doc_id in result is bundle document identity; layout uses output_leaf_name."""
    export_dir = tmp_path / "legacy_doc_export"
    bundle_path = write_prepare_analysis_filter_input(
        export_dir,
        {
            **_sample_analysis_bundle(),
            "doc_id": "canonical_source_doc",
        },
    )
    profile = _ib_clinical_safety_profile()

    result = run_filter_stage(
        bundle_path=bundle_path,
        profile=profile,
        zone_key="ib_clinical_safety_zh",
        invocation=_invocation(tmp_path),
    )

    assert result.doc_id == "canonical_source_doc"
    normalized_out = str(result.output_dir).replace("\\", "/")
    assert "doc_legacy_doc" in normalized_out
    assert "canonical_source_doc" not in normalized_out
