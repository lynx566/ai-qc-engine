# ruff: noqa: DTZ001
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE
from plugins.clinical_trial_doc.VERSION import (
    CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS,
    CLINICAL_TRIAL_DOC_PLUGIN_VERSION,
)
from runtime.run_ids import (
    build_run_id,
    build_run_id_from_session_dir,
    build_session_dir_segment,
    format_run_timestamp,
)
from runtime.run_layout import (
    ANALYSIS_RUN_DIR_LAYOUT,
    EXTRACT_RUN_DIR_LAYOUT,
    FILTER_RUN_DIR_LAYOUT,
    build_extract_run_naming,
    build_prepare_analysis_session_run_naming,
    build_stage_run_dir,
    build_stage_run_layout,
    resolve_stage_phase_artifact_dir,
)
from runtime.run_provenance import (
    GIT_DIRTY_CHECKED_AT_BEFORE_RUN,
    GIT_DIRTY_CHECKED_AT_SUMMARY,
    finalize_run_summary,
    load_upstream_run_summary,
    snapshot_git_provenance_before_run,
    upstream_provenance,
)
from runtime.run_summaries import (
    build_filter_output_privacy_contract,
    build_filter_run_summary,
    build_prepare_analysis_run_summary,
)
from runtime.run_layout import allocate_session_dir, resolve_unique_session_dir


class _ZoneConfig:
    language = "zh"
    zone_config_name = "ib_clinical_safety_zh"
    zone_config_version = "0.2.0"


def test_build_run_id_from_session_dir() -> None:
    assert (
        build_run_id_from_session_dir("extract", "20260521_164615__2")
        == "extract_20260521_164615__2"
    )


def test_allocate_extract_session_dir_timestamp_only(tmp_path: Path) -> None:
    stamp = datetime(2026, 5, 28, 16, 33, 38, tzinfo=timezone.utc)
    session_dir = allocate_session_dir(
        tmp_path,
        stage="extract",
        context="docx",
        stamp=stamp,
        run_dir_layout=EXTRACT_RUN_DIR_LAYOUT,
    )
    assert session_dir == (tmp_path / "extract" / "20260528_163338_000000Z")


def test_resolve_unique_session_dir_increments(tmp_path: Path) -> None:
    root = tmp_path / "exports"
    base = "20260521_164615"
    first = resolve_unique_session_dir(root, base)
    assert first.name == base
    second = resolve_unique_session_dir(root, base)
    assert second.name == f"{base}__2"
    third = resolve_unique_session_dir(root, base)
    assert third.name == f"{base}__3"


def test_extract_naming_uses_session_dir_for_run_id() -> None:
    naming = build_extract_run_naming(
        stamp=datetime(2026, 5, 20, 20, 40, 47),
        sample_slug="ib_001",
        git_root=BACKEND_ROOT,
        session_dir_name="20260520_204047__2",
    )
    assert naming.run_id == "extract_20260520_204047__2"
    assert naming.session_dir_name == "20260520_204047__2"
    assert naming.doc_id == "ib_001"
    assert naming.export_dir_name == "doc_ib_001"


def test_build_run_id_with_timestamp() -> None:
    stamp = datetime(2026, 5, 20, 20, 40, 47, tzinfo=timezone.utc)
    assert build_run_id("extract", stamp).startswith("extract_20260520_204047_")
    assert build_run_id("extract", stamp).endswith("Z")


def test_build_session_dir_segment() -> None:
    stamp = datetime(2026, 5, 20, 22, 0, 10, tzinfo=timezone.utc)
    assert build_session_dir_segment(stamp).startswith("20260520_220010_")
    assert build_session_dir_segment(stamp).endswith("Z")


def test_extract_naming_uses_unified_run_id() -> None:
    stamp = datetime(2026, 5, 20, 20, 40, 47, tzinfo=timezone.utc)
    naming = build_extract_run_naming(
        stamp=stamp,
        sample_slug="ib_001",
        git_root=BACKEND_ROOT,
    )
    assert naming.run_id.startswith("extract_20260520_204047_")
    assert naming.run_id.endswith("Z")
    assert naming.session_dir_name == naming.run_id.removeprefix("extract_")
    assert naming.doc_id == "ib_001"
    assert naming.export_dir_name == "doc_ib_001"


def test_mask_naming_uses_unified_run_id() -> None:
    stamp = datetime(2026, 5, 20, 22, 0, 10, tzinfo=timezone.utc)
    naming = build_prepare_analysis_session_run_naming(
        stamp=stamp,
        context="clinical_trial_doc",
        doc_id="ib_001",
        git_root=BACKEND_ROOT,
    )
    assert naming.run_id.startswith("prepare_analysis_20260520_220010_")
    assert naming.session_dir_name.startswith("20260520_220010_")
    assert naming.context == "clinical_trial_doc"


def test_build_prepare_analysis_run_dir() -> None:
    layout = build_stage_run_layout(
        stage="prepare_analysis",
        context="clinical_trial_doc",
        doc_id="ib_safety_tag_integration_001",
        stamp=datetime(2026, 5, 30, 17, 31, 49),
        session_dir_name="20260530_173149",
        run_dir_layout=ANALYSIS_RUN_DIR_LAYOUT,
    )
    assert layout.run_dir(BACKEND_ROOT / "runs") == (
        BACKEND_ROOT
        / "runs"
        / "prepare_analysis"
        / "20260530_173149"
        / "doc_ib_safety_tag_integration_001"
    )


def test_build_filter_run_dir() -> None:
    layout = build_stage_run_layout(
        stage="filter",
        context="ib_clinical_safety_zh",
        doc_id="ib_safety_tag_integration_001",
        stamp=datetime(2026, 5, 30, 17, 43, 3),
        session_dir_name="20260530_174303",
        task_key="ib_clinical_safety_zh",
        run_dir_layout=FILTER_RUN_DIR_LAYOUT,
    )
    assert layout.run_dir(BACKEND_ROOT / "runs") == (
        BACKEND_ROOT
        / "runs"
        / "filter"
        / "20260530_174303"
        / "doc_ib_safety_tag_integration_001"
        / "ib_clinical_safety_zh"
    )


def test_resolve_stage_phase_artifact_dir_uses_evidence_form_id_segment(tmp_path: Path) -> None:
    stamp = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    run_id = format_run_timestamp(stamp)
    out_dir, session_dir = resolve_stage_phase_artifact_dir(
        project_root=tmp_path,
        stage="evidence_source_preparation",
        zone_key="ib_clinical_safety_zh",
        doc_id="doc_test_001",
        run_id=run_id,
        stamp=stamp,
        phase="prepare",
        evidence_form_id="aggregate_evidence",
    )
    assert out_dir == (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "prepare"
        / run_id
        / "doc_test_001"
        / "ib_clinical_safety_zh"
        / "aggregate_evidence"
    )
    assert session_dir == (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "prepare"
        / run_id
    )
    assert "aggregate" not in out_dir.parts[-1:]


def test_aggregate_evidence_operations_use_evidence_source_preparation_stage(
    tmp_path: Path,
) -> None:
    stamp = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    run_id = format_run_timestamp(stamp)

    for phase in ("prepare", "assess", "eligibility", "assemble"):
        out_dir, session_dir = resolve_stage_phase_artifact_dir(
            project_root=tmp_path,
            stage=EVIDENCE_SOURCE_PREPARATION_STAGE,
            zone_key="ib_clinical_safety_zh",
            doc_id="doc_test_001",
            run_id=run_id,
            stamp=stamp,
            phase=phase,
            evidence_form_id="aggregate_evidence",
        )
        expected_session = (
            tmp_path
            / "runs"
            / EVIDENCE_SOURCE_PREPARATION_STAGE
            / phase
            / run_id
        )
        assert session_dir == expected_session
        assert out_dir == (
            expected_session
            / "doc_test_001"
            / "ib_clinical_safety_zh"
            / "aggregate_evidence"
        )
        assert tmp_path / "runs" / "process" not in out_dir.parents


def test_build_stage_run_dir_default_layout() -> None:
    path = build_stage_run_dir(
        BACKEND_ROOT / "runs",
        "tag",
        "clinical_safety",
        "20260527_214725",
        "ib_safety_tag_integration_001",
    )
    assert path == (
        BACKEND_ROOT
        / "runs"
        / "tag"
        / "20260527_214725"
        / "doc_ib_safety_tag_integration_001"
    )


def test_upstream_provenance_without_summary() -> None:
    assert upstream_provenance(None) == {
        "upstream_run_id": None,
        "upstream_stage": None,
    }


def test_load_upstream_run_summary(tmp_path: Path) -> None:
    upstream_dir = tmp_path / "extract_run"
    upstream_dir.mkdir()
    summary = {
        "run_id": "extract_20260520_204047",
        "stage": "extract",
    }
    (upstream_dir / "run_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    bundle_path = upstream_dir / "bundle.json"
    bundle_path.write_text("{}", encoding="utf-8")

    loaded = load_upstream_run_summary(bundle_path)
    assert loaded == summary
    assert upstream_provenance(loaded) == {
        "upstream_run_id": "extract_20260520_204047",
        "upstream_stage": "extract",
    }


def test_mask_run_summary_links_upstream_extract(tmp_path: Path) -> None:
    upstream_dir = tmp_path / "extract"
    upstream_dir.mkdir()
    upstream_summary = {
        "run_id": "extract_20260520_204047",
        "stage": "extract",
    }
    (upstream_dir / "run_summary.json").write_text(
        json.dumps(upstream_summary),
        encoding="utf-8",
    )
    input_bundle = upstream_dir / "bundle.json"
    input_bundle.write_text("{}", encoding="utf-8")

    out_dir = tmp_path / "mask"
    out_dir.mkdir()
    summary = build_prepare_analysis_run_summary(
        run_id="mask_20260520_220010",
        bundle_dict={
            "doc_id": "ib_001",
            "file_name": "ib_001.docx",
            "file_hash": "sha256:test",
            "source_type": "docx",
            "document_meta": {"bundle_schema_version": "0.1.2"},
        },
        language="zh",
        input_bundle=input_bundle,
        output_bundle_path=None,
        analysis_bundle_path=out_dir / "analysis_bundle.json",
        privacy_audit_path=out_dir / "privacy_audit.json",
        mapping_path=out_dir / "mapping.json",
        privacy_transform_applied=True,
        privacy_detectors_configured=["registry", "regex", "uie"],
        privacy_detectors_used=["registry", "regex", "uie"],
        date_shift_offset_days=17,
        analysis_block_count=3,
        privacy_profile_ref="clinical_trial_doc",
        session_segment="clinical_trial_doc",
        paths_base=tmp_path,
        plugin_provenance={
            "name": "clinical_trial_doc",
            "version": CLINICAL_TRIAL_DOC_PLUGIN_VERSION,
            "components": {
                "privacy_profile": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS[
                    "privacy_profile"
                ],
                "registry": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["registry"],
                "regex_rules_zh": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS[
                    "regex_rules_zh"
                ],
                "uie_schema_zh": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS[
                    "uie_schema_zh"
                ],
            },
        },
    )

    assert summary["run_id"] == "mask_20260520_220010"
    assert "file_name" not in summary
    assert summary["file_hash"] == "sha256:test"
    assert summary["privacy_profile_ref"] == "clinical_trial_doc"
    assert summary["analysis_transform"] == "privacy_transform"
    assert summary["privacy_transform_applied"] is True
    assert summary["privacy_detectors_configured"] == ["registry", "regex", "uie"]
    assert summary["privacy_detectors_used"] == ["registry", "regex", "uie"]
    assert summary["privacy_transform"]["settings"]["date_shift_offset_days"] == 17
    assert "privacy_transforms" not in summary
    assert "privacy_transform_slot" not in summary
    assert summary["plugin"]["name"] == "clinical_trial_doc"
    assert summary["plugin"]["version"] == CLINICAL_TRIAL_DOC_PLUGIN_VERSION
    assert summary["plugin"]["components"] == {
        "privacy_profile": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["privacy_profile"],
        "registry": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["registry"],
        "regex_rules_zh": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["regex_rules_zh"],
        "uie_schema_zh": CLINICAL_TRIAL_DOC_COMPONENT_VERSIONS["uie_schema_zh"],
    }
    assert "session_segment" not in summary
    assert "context" not in summary
    assert summary["stage_scope"] == "analysis_preparation"
    assert summary["run_dir_layout"] == ANALYSIS_RUN_DIR_LAYOUT
    assert summary["stage"] == "prepare_analysis"
    assert summary["inputs"] == {"input_bundle": "extract/bundle.json"}
    assert "source_docx" not in summary["inputs"]
    assert summary["upstream_run_id"] == "extract_20260520_204047"
    assert summary["upstream_stage"] == "extract"
    assert "git_commit" in summary
    assert "git_dirty" in summary


def test_filter_run_summary_links_upstream_prepare_analysis(tmp_path: Path) -> None:
    upstream_dir = tmp_path / "prepare_analysis"
    upstream_dir.mkdir()
    upstream_summary = {
        "run_id": "prepare_analysis_20260520_220010",
        "stage": "prepare_analysis",
    }
    (upstream_dir / "run_summary.json").write_text(
        json.dumps(upstream_summary),
        encoding="utf-8",
    )
    input_analysis_bundle = upstream_dir / "analysis_bundle.json"
    input_analysis_bundle.write_text("{}", encoding="utf-8")

    out_dir = tmp_path / "filter"
    out_dir.mkdir()
    summary = build_filter_run_summary(
        run_id="filter_20260520_224445",
        bundle={
            "doc_id": "ib_001",
            "file_name": "ib_001.docx",
            "file_hash": "sha256:filter",
            "source_type": "docx",
        },
        bundle_path=input_analysis_bundle,
        zone_config=_ZoneConfig(),
        zone_bundle_path=out_dir / "zone_match_bundle.json",
        zone_bundle_debug_path=None,
        input_parser_type="docx_handlers",
        input_parser_version="0.1.3",
        run_context="ib_overview_zh+ib_clinical_safety_zh",
        zone_key="ib_overview_zh+ib_clinical_safety_zh",
        paths_base=tmp_path,
    )

    assert summary["run_id"] == "filter_20260520_224445"
    assert "file_name" not in summary
    assert summary["file_hash"] == "sha256:filter"
    assert summary["inputs"]["input_analysis_bundle"] == (
        "prepare_analysis/analysis_bundle.json"
    )
    assert "source_docx" not in summary["inputs"]
    assert summary["upstream_run_id"] == "prepare_analysis_20260520_220010"
    assert summary["upstream_stage"] == "prepare_analysis"
    assert summary["zone_key"] == "ib_overview_zh+ib_clinical_safety_zh"
    assert summary["stage_scope"] == "zone_key"
    assert "session_segment" not in summary
    assert "context" not in summary
    assert summary["run_dir_layout"] == FILTER_RUN_DIR_LAYOUT
    assert summary["outputs"] == {"zone_match_bundle": "zone_match_bundle.json"}
    assert summary["artifacts"] == {
        "zone_match_bundle": "zone_match_bundle.json",
        "zone_match_bundle_debug": None,
    }
    assert summary["output_privacy_contract"] == build_filter_output_privacy_contract(
        include_debug_bundle=False,
        include_coverage_bundle=False,
    )
    assert summary["resolved_filter_strategy_id"] == "heading_zone"
    assert summary["output_privacy_contract"] == build_filter_output_privacy_contract(
        include_debug_bundle=False,
        include_coverage_bundle=False,
    )


def test_filter_run_summary_reads_resolved_strategy_from_zone_bundle(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "filter"
    out_dir.mkdir()
    zone_bundle = {
        "resolved_filter_strategy_id": "heading_zone",
    }
    input_bundle = tmp_path / "analysis_bundle.json"
    input_bundle.write_text("{}", encoding="utf-8")

    summary = build_filter_run_summary(
        run_id="filter_20260520_224445",
        bundle={"doc_id": "ib_001", "file_name": "ib_001.docx", "source_type": "docx"},
        bundle_path=input_bundle,
        zone_config=_ZoneConfig(),
        zone_bundle=zone_bundle,
        zone_bundle_path=out_dir / "zone_match_bundle.json",
        zone_bundle_debug_path=None,
        input_parser_type="docx_handlers",
        input_parser_version="0.1.3",
        paths_base=tmp_path,
    )

    assert summary["resolved_filter_strategy_id"] == "heading_zone"
    assert summary["output_privacy_contract"] == build_filter_output_privacy_contract(
        include_debug_bundle=False,
        include_coverage_bundle=False,
    )


def test_filter_run_summary_re_resolves_strategy_without_zone_bundle(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "filter"
    out_dir.mkdir()
    input_bundle = tmp_path / "analysis_bundle.json"
    input_bundle.write_text("{}", encoding="utf-8")

    summary = build_filter_run_summary(
        run_id="filter_20260520_224445",
        bundle={"doc_id": "ib_001", "file_name": "ib_001.docx", "source_type": "docx"},
        bundle_path=input_bundle,
        zone_config=_ZoneConfig(),
        zone_bundle_path=out_dir / "zone_match_bundle.json",
        zone_bundle_debug_path=None,
        input_parser_type="docx_handlers",
        input_parser_version="0.1.3",
        paths_base=tmp_path,
    )

    assert summary["resolved_filter_strategy_id"] == "heading_zone"
    assert summary["output_privacy_contract"] == build_filter_output_privacy_contract(
        include_debug_bundle=False,
        include_coverage_bundle=False,
    )


def test_filter_output_privacy_contract_with_debug_and_coverage() -> None:
    contract = build_filter_output_privacy_contract(
        include_debug_bundle=True,
        include_coverage_bundle=True,
    )
    assert contract["zone_match_bundle"]["artifact_privacy_level"] == "public_masked_v0.2"
    assert contract["coverage_bundle"]["artifact_privacy_level"] == "public_structural_v0.1"
    assert contract["private_outputs"]["zone_match_bundle_debug"] == "local_debug_raw"


def test_filter_run_summary_includes_coverage_contract_when_present(tmp_path: Path) -> None:
    out_dir = tmp_path / "filter"
    out_dir.mkdir()
    input_bundle = tmp_path / "analysis_bundle.json"
    input_bundle.write_text("{}", encoding="utf-8")

    summary = build_filter_run_summary(
        run_id="filter_20260520_224445",
        bundle={"doc_id": "ib_001", "file_name": "ib_001.docx", "source_type": "docx"},
        bundle_path=input_bundle,
        zone_config=_ZoneConfig(),
        zone_bundle_path=out_dir / "zone_match_bundle.json",
        zone_bundle_debug_path=None,
        coverage_bundle_path=out_dir / "coverage_bundle.json",
        input_parser_type="docx_handlers",
        input_parser_version="0.1.3",
        paths_base=tmp_path,
    )

    assert summary["outputs"]["coverage_bundle"] == "coverage_bundle.json"
    assert summary["artifacts"]["coverage_bundle"] == "coverage_bundle.json"
    assert summary["output_privacy_contract"] == build_filter_output_privacy_contract(
        include_debug_bundle=False,
        include_coverage_bundle=True,
    )


def test_snapshot_git_provenance_before_run_tags_checked_at() -> None:
    provenance = snapshot_git_provenance_before_run(root=BACKEND_ROOT)
    assert provenance["git_dirty_checked_at"] == GIT_DIRTY_CHECKED_AT_BEFORE_RUN
    assert "git_commit" in provenance
    assert "git_dirty" in provenance


def test_finalize_run_summary_uses_before_run_provenance() -> None:
    git_prov = {
        "git_commit": "abc1234",
        "git_dirty": False,
        "git_dirty_checked_at": GIT_DIRTY_CHECKED_AT_BEFORE_RUN,
    }
    summary = finalize_run_summary(
        stage="extract",
        run_id="extract_20260520_204047",
        pipeline=["extract"],
        doc_id="ib_001",
        file_name="ib_001.docx",
        inputs={"source_docx": "/tmp/ib_001.docx"},
        outputs={"bundle": "bundle.json"},
        git_root=BACKEND_ROOT,
        upstream_summary=None,
        git_provenance=git_prov,
    )
    assert summary["git_dirty"] is False
    assert summary["git_dirty_checked_at"] == GIT_DIRTY_CHECKED_AT_BEFORE_RUN


def test_finalize_run_summary_field_order() -> None:
    summary = finalize_run_summary(
        stage="extract",
        run_id="extract_20260520_204047",
        pipeline=["extract"],
        doc_id="ib_001",
        file_name="ib_001.docx",
        inputs={"source_docx": "/tmp/ib_001.docx"},
        outputs={"bundle": "bundle.json"},
        git_root=BACKEND_ROOT,
        upstream_summary=None,
    )
    keys = list(summary.keys())
    assert keys[:9] == [
        "stage",
        "run_id",
        "pipeline",
        "doc_id",
        "file_name",
        "git_commit",
        "git_dirty",
        "git_dirty_checked_at",
        "upstream_run_id",
    ]
    assert summary["upstream_stage"] is None
    assert summary["git_dirty_checked_at"] == GIT_DIRTY_CHECKED_AT_SUMMARY


def test_finalize_run_summary_omits_file_name_when_unset() -> None:
    summary = finalize_run_summary(
        stage="tag",
        run_id="tag_20260612_164633",
        pipeline=["extract", "prepare_analysis", "doc_meta", "filter", "tag_prepare", "tag"],
        doc_id="doc_00000000-0000-4000-8000-000000000001",
        inputs={"llm_input_bundle": "runs/tag_prepare/demo/llm_input_bundle.json"},
        outputs={"tag_output": "tag_output.json"},
        git_root=BACKEND_ROOT,
        upstream_summary=None,
    )
    assert "file_name" not in summary
    keys = list(summary.keys())
    assert keys[:8] == [
        "stage",
        "run_id",
        "pipeline",
        "doc_id",
        "git_commit",
        "git_dirty",
        "git_dirty_checked_at",
        "upstream_run_id",
    ]
