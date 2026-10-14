from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
)
from artifacts.zone_match_bundle import ZONE_MATCH_BUNDLE_DEBUG_FILENAME, ZONE_MATCH_BUNDLE_FILENAME
from core.document.sentence_index import build_sentences
from execution_flow.document_consistency_qc import flow as flow_module
from runtime.filter_stage import FilterStageResult
from scripts.stage_runners import filter_runner
import scripts.stage_runners.common as runner_common
from scripts.stage_runners.common import (
    ANALYSIS_BUNDLE_FILENAME,
    ensure_output_dir,
    resolve_artifact_dir,
    resolve_artifact_file,
)
from tests.filter_test_helpers import write_prepare_analysis_filter_input


LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)

_FILTER_JOB_VARIANTS = INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS
_LANGUAGE = "zh"


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


def _runner_argv(
    *,
    analysis_bundle: str,
    filter_job_ids: tuple[str, ...] = ("ib_clinical_safety",),
    language: str = _LANGUAGE,
    extra: tuple[str, ...] = (),
) -> list[str]:
    argv = [
        "filter_runner.py",
        "--analysis-bundle",
        analysis_bundle,
        "--language",
        language,
    ]
    for filter_job_id in filter_job_ids:
        argv.extend(["--filter-job-id", filter_job_id])
    argv.extend(extra)
    return argv


def test_ensure_output_dir_repo_root_style_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "backend"
    project_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runner_common, "PROJECT_ROOT", project_root)

    out_dir = ensure_output_dir("backend/runs/tag/demo")
    assert out_dir == (project_root.parent / "backend" / "runs" / "tag" / "demo").resolve()


def test_ensure_output_dir_backend_relative_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "backend"
    project_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runner_common, "PROJECT_ROOT", project_root)

    out_dir = ensure_output_dir("runs/tag/demo")
    assert out_dir == (project_root / "runs" / "tag" / "demo").resolve()


def test_filter_runner_does_not_bind_load_json() -> None:
    assert not hasattr(filter_runner, "load_json")


def test_filter_runner_resolves_same_profiles_as_flow() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    for filter_job_id in ("ib_clinical_safety", "ib_overview"):
        runner_job = filter_runner.resolve_runner_filter_jobs(
            filter_job_ids=(filter_job_id,),
            language=_LANGUAGE,
            filter_job_variants=composition.filter_job_variants,
        )[0]
        flow_profile = flow_module._resolve_slot_filter_jobs(
            filter_job_ids=(filter_job_id,),
            source_language=_LANGUAGE,
            filter_job_variants=composition.filter_job_variants,
        )[0][1]
        assert runner_job.profile is flow_profile


def test_filter_runner_source_has_no_retired_zone_cli() -> None:
    source = (BACKEND_ROOT / "scripts" / "stage_runners" / "filter_runner.py").read_text(
        encoding="utf-8"
    )
    assert "--zone-config" not in source
    assert "load_zone_config" not in source
    assert "resolve_zone_config_input" not in source
    assert "filter_configs" not in source


def test_zone_registry_has_no_retired_profile_loader() -> None:
    source = (BACKEND_ROOT / "runtime" / "zone_registry.py").read_text(encoding="utf-8")
    assert "load_zone_config" not in source
    assert "resolve_zone_config_input" not in source
    assert "lookup_installed_filter_config" not in source


def test_filter_runner_delegates_per_stage_naming_to_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    masked_path = write_prepare_analysis_filter_input(
        tmp_path / "ib_001",
        _sample_analysis_bundle(),
    )

    captured: list[dict] = []

    def fake_run_filter_stage(**kwargs):
        captured.append(kwargs)
        out_dir = tmp_path / "filter_out"
        out_dir.mkdir(parents=True, exist_ok=True)
        return FilterStageResult(
            output_dir=out_dir,
            run_id="captured_run",
            doc_id="ib_001",
            zone_key="ib_clinical_safety_zh",
            run_context="ib_clinical_safety_zh",
            zone_bundle_path=out_dir / ZONE_MATCH_BUNDLE_FILENAME,
            coverage_bundle_path=out_dir / "coverage_bundle.json",
            zone_bundle_debug_path=None,
            run_summary_path=out_dir / "run_summary.json",
            bundle=_sample_analysis_bundle(),
            bundle_path=masked_path,
        )

    monkeypatch.setattr(filter_runner, "run_filter_stage", fake_run_filter_stage)
    monkeypatch.setattr(filter_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        filter_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        _runner_argv(
            analysis_bundle=str(masked_path),
            extra=("--output-dir", str(tmp_path / "filter_out")),
        ),
    )

    filter_runner.main()

    assert len(captured) == 1
    call = captured[0]
    assert "invocation" in call
    assert call["zone_key"] == "ib_clinical_safety_zh"
    assert "output_dir" not in call
    assert "run_id" not in call
    assert "run_context" not in call
    assert "job_zone_key" not in call


def test_filter_runner_default_layout_uses_single_zone_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    masked_path = write_prepare_analysis_filter_input(
        tmp_path / "ib_001",
        _sample_analysis_bundle(),
    )

    monkeypatch.setattr(filter_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        filter_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        _runner_argv(analysis_bundle=str(masked_path)),
    )

    filter_runner.main()

    outputs = list(
        (tmp_path / "runs" / "filter").glob(
            f"*/doc_ib_001/ib_clinical_safety_zh/{ZONE_MATCH_BUNDLE_FILENAME}"
        )
    )
    assert len(outputs) == 1
    assert not outputs[0].with_name(ZONE_MATCH_BUNDLE_DEBUG_FILENAME).exists()
    summary = json.loads(outputs[0].parent.joinpath("run_summary.json").read_text())
    assert summary["zone_key"] == "ib_clinical_safety_zh"
    assert "session_segment" not in summary
    assert "context" not in summary


def test_filter_runner_multi_job_default_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mask_dir = tmp_path / "ib_safety_tag_integration_001"
    masked_path = write_prepare_analysis_filter_input(
        mask_dir,
        _sample_ib_dual_zone_bundle(),
    )

    monkeypatch.setattr(filter_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        filter_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        _runner_argv(
            analysis_bundle=str(masked_path),
            filter_job_ids=("ib_overview", "ib_clinical_safety"),
        ),
    )

    filter_runner.main()

    runs_filter = tmp_path / "runs" / "filter"
    composite = list(runs_filter.glob("*/ib_overview_zh+ib_clinical_safety_zh"))
    assert composite == []

    summary_outputs = list(
        runs_filter.glob(
            f"*/doc_ib_safety_tag_integration_001/ib_overview_zh/{ZONE_MATCH_BUNDLE_FILENAME}"
        )
    )
    safety_outputs = list(
        runs_filter.glob(
            f"*/doc_ib_safety_tag_integration_001/ib_clinical_safety_zh/{ZONE_MATCH_BUNDLE_FILENAME}"
        )
    )
    assert len(summary_outputs) == 1
    assert len(safety_outputs) == 1

    summary_run = json.loads(
        summary_outputs[0].parent.joinpath("run_summary.json").read_text()
    )
    safety_run = json.loads(
        safety_outputs[0].parent.joinpath("run_summary.json").read_text()
    )
    assert summary_run["zone_key"] == "ib_overview_zh"
    assert safety_run["zone_key"] == "ib_clinical_safety_zh"
    assert summary_outputs[0].parent != safety_outputs[0].parent
    assert summary_run["run_id"] == safety_run["run_id"]


def test_filter_runner_multi_job_debug_per_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mask_dir = tmp_path / "ib_safety_tag_integration_001"
    masked_path = write_prepare_analysis_filter_input(
        mask_dir,
        _sample_ib_dual_zone_bundle(),
    )
    (mask_dir / "privacy_audit.json").write_text(
        json.dumps(_mask_output_for_debug()),
        encoding="utf-8",
    )

    monkeypatch.setattr(filter_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        filter_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        _runner_argv(
            analysis_bundle=str(masked_path),
            filter_job_ids=("ib_overview", "ib_clinical_safety"),
            extra=("--debug",),
        ),
    )

    filter_runner.main()

    runs_filter = tmp_path / "runs" / "filter"
    summary_debug = list(
        runs_filter.glob(
            f"*/doc_ib_safety_tag_integration_001/ib_overview_zh/{ZONE_MATCH_BUNDLE_DEBUG_FILENAME}"
        )
    )
    safety_debug = list(
        runs_filter.glob(
            f"*/doc_ib_safety_tag_integration_001/ib_clinical_safety_zh/{ZONE_MATCH_BUNDLE_DEBUG_FILENAME}"
        )
    )
    assert len(summary_debug) == 1
    assert len(safety_debug) == 1


def test_filter_runner_rejects_unknown_filter_job_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "filter_runner.py",
            "--analysis-bundle",
            "analysis_bundle.json",
            "--filter-job-id",
            "ib_zh",
            "--language",
            _LANGUAGE,
        ],
    )
    with pytest.raises(SystemExit):
        filter_runner.parse_args(filter_job_variants=_FILTER_JOB_VARIANTS)


def test_filter_runner_rejects_retired_zone_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "filter_runner.py",
            "--analysis-bundle",
            "analysis_bundle.json",
            "--zone",
            "ib_clinical_safety_zh",
        ],
    )
    with pytest.raises(SystemExit):
        filter_runner.parse_args(filter_job_variants=_FILTER_JOB_VARIANTS)


def test_filter_runner_rejects_retired_zone_config_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "filter_runner.py",
            "--analysis-bundle",
            "analysis_bundle.json",
            "--zone-config",
            "plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh:"
            "IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH",
        ],
    )
    with pytest.raises(SystemExit):
        filter_runner.parse_args(filter_job_variants=_FILTER_JOB_VARIANTS)


def test_filter_runner_bundle_dir_finds_masked_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_dir = tmp_path / "mask_session" / "ib_001"
    write_prepare_analysis_filter_input(session_dir, _sample_analysis_bundle())

    out_root = tmp_path / "filter_out"
    monkeypatch.setattr(filter_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        filter_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "filter_runner.py",
            "--analysis-bundle-dir",
            str(tmp_path / "mask_session"),
            "--filter-job-id",
            "ib_clinical_safety",
            "--language",
            _LANGUAGE,
            "--output-dir",
            str(out_root),
        ],
    )

    filter_runner.main()

    assert (out_root / ZONE_MATCH_BUNDLE_FILENAME).is_file()


def test_filter_runner_default_skips_debug_even_with_mask_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mask_dir = tmp_path / "ib_001"
    masked_path = write_prepare_analysis_filter_input(
        mask_dir,
        _sample_analysis_bundle(),
    )
    (mask_dir / "privacy_audit.json").write_text(
        json.dumps(_mask_output_for_debug()),
        encoding="utf-8",
    )

    out_root = tmp_path / "filter_out"
    monkeypatch.setattr(filter_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        filter_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        _runner_argv(
            analysis_bundle=str(masked_path),
            extra=("--output-dir", str(out_root)),
        ),
    )

    filter_runner.main()

    assert (out_root / ZONE_MATCH_BUNDLE_FILENAME).is_file()
    assert not (out_root / ZONE_MATCH_BUNDLE_DEBUG_FILENAME).exists()


def test_filter_runner_rejects_extract_bundle(tmp_path: Path) -> None:
    extract_path = tmp_path / "bundle.json"
    extract_path.write_text(json.dumps(_sample_analysis_bundle()), encoding="utf-8")

    with pytest.raises(SystemExit, match="run prepare_analysis first"):
        resolve_artifact_file(str(extract_path), filename=ANALYSIS_BUNDLE_FILENAME)


def test_filter_runner_bundle_dir_missing_masked_bundle(tmp_path: Path) -> None:
    extract_dir = tmp_path / "extract_only"
    extract_dir.mkdir()
    (extract_dir / "bundle.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit, match="Run the prepare_analysis step first"):
        resolve_artifact_dir(str(extract_dir), filename=ANALYSIS_BUNDLE_FILENAME)


def test_filter_runner_rejects_raw_bundle_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        _runner_argv(analysis_bundle="analysis_bundle.json") + ["--raw-bundle"],
    )
    with pytest.raises(SystemExit):
        filter_runner.parse_args(filter_job_variants=_FILTER_JOB_VARIANTS)
