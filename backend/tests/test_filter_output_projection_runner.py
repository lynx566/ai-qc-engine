"""Tests for the standalone Filter-output projection runner."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc import (
    projection_runtime as projection_runtime_module,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from artifacts.filter_output_projection_bundle import (
    FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME,
    validate_filter_output_projection_bundle,
)
from artifacts.zone_match_bundle import ZONE_MATCH_BUNDLE_FILENAME
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionStepResult,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from runtime.filter_output_projection_stage import (
    FilterOutputProjectionStageResult,
    run_filter_output_projection_stage,
)
from runtime.io import load_json
from scripts.stage_runners import filter_output_projection_runner
from scripts.stage_runners.filter_output_projection_overview_mock_provider import (
    OverviewStandaloneMockProvider,
)
from tests.test_filter_output_projection_direct import (
    _filter_artifacts_for_profile,
    _resolved_direct_job,
)

RUNNER_PATH = (
    BACKEND_ROOT / "scripts" / "stage_runners" / "filter_output_projection_runner.py"
)

FORBIDDEN_RUNNER_TOKENS = (
    "DIRECT_FILTER_OUTPUT_PROJECTION_FACADE",
    "build_overview_semantic_decomposition_facade",
    "project_direct_filter_output",
    "project_overview_semantic_decomposition",
    "run_project_filter_output",
    "run_filter_stage",
    "steps.project_filter_output",
    "steps.filter",
    "materialize_installed_projection_runtime_dependencies",
)


def _base_runner_argv(
    zone_path: Path,
    analysis_path: Path,
    filter_job_id: str,
    *,
    llm_mode: str = "mock",
    llm_profile: str | None = None,
    thinking_flag: str | None = None,
) -> list[str]:
    argv = [
        "--zone-match-bundle",
        str(zone_path),
        "--analysis-bundle",
        str(analysis_path),
        "--filter-job-id",
        filter_job_id,
        "--llm",
        llm_mode,
    ]
    if llm_profile is not None:
        argv.extend(["--llm-profile", llm_profile])
    if thinking_flag is not None:
        argv.append(thinking_flag)
    return argv


def _isolate_projection_runner_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Keep standalone runner layout tests off the real backend/runs tree."""

    monkeypatch.setattr(filter_output_projection_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        filter_output_projection_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    return tmp_path


def _write_zone_match_bundle(tmp_path: Path) -> tuple[Path, Path]:
    zone_match_bundle, _coverage, _block_manifest, analysis_bundle = _filter_artifacts_for_profile(
        IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    )
    zone_path = tmp_path / ZONE_MATCH_BUNDLE_FILENAME
    zone_path.write_text(
        json.dumps(zone_match_bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    analysis_path = tmp_path / "analysis_bundle.json"
    analysis_path.write_text(
        json.dumps(analysis_bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    return zone_path, analysis_path


def test_runner_resolves_same_installed_projection_job_as_composition() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    filter_job_id = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id
    runner_job = filter_output_projection_runner.resolve_runner_projection_job(
        filter_job_id=filter_job_id,
        composition=composition,
    )
    composition_job = composition.resolve_filter_output_projection_job(filter_job_id)
    assert runner_job == composition_job
    assert runner_job.strategy_id == DIRECT_FILTER_OUTPUT_PROJECTION_STRATEGY_ID
    assert (
        runner_job.strategy_config["semantic_module_id"]
        == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    )


def test_unknown_filter_job_fails_cleanly() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    with pytest.raises(ValueError, match="unknown Filter-output projection job"):
        filter_output_projection_runner.resolve_runner_projection_job(
            filter_job_id="unknown_filter_job",
            composition=composition,
        )


def test_runner_source_has_no_direct_plugin_facade_coupling() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    for token in FORBIDDEN_RUNNER_TOKENS:
        assert token not in source, f"runner must not reference {token!r}"


def test_runner_does_not_bind_load_json() -> None:
    assert not hasattr(filter_output_projection_runner, "load_json")


def test_runner_import_graph_avoids_plugin_projection_facades() -> None:
    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"), filename=str(RUNNER_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden_prefix = "plugins.clinical_trial_doc.filter_output_projection"
    assert not any(module.startswith(forbidden_prefix) for module in imported)


def test_runner_requires_explicit_llm_mode() -> None:
    with pytest.raises(SystemExit):
        filter_output_projection_runner.parse_args(
            [
                "--zone-match-bundle",
                "zone.json",
                "--analysis-bundle",
                "analysis.json",
                "--filter-job-id",
                "ib_clinical_safety",
            ]
        )


def test_runner_api_requires_explicit_profile() -> None:
    with pytest.raises(SystemExit, match="API execution requires explicit --llm-profile"):
        filter_output_projection_runner.parse_args(
            [
                "--zone-match-bundle",
                "zone.json",
                "--analysis-bundle",
                "analysis.json",
                "--filter-job-id",
                "ib_overview",
                "--llm",
                "api",
            ]
        )


def test_runner_mock_accepts_without_profile() -> None:
    args = filter_output_projection_runner.parse_args(
        [
            "--zone-match-bundle",
            "zone.json",
            "--analysis-bundle",
            "analysis.json",
            "--filter-job-id",
            "ib_overview",
            "--llm",
            "mock",
        ]
    )
    assert args.llm == "mock"
    assert args.llm_profile is None


def test_build_runner_dependencies_direct_mock_uses_no_provider() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    resolved_job = composition.resolve_filter_output_projection_job(
        IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id
    )
    args = filter_output_projection_runner.parse_args(
        [
            "--zone-match-bundle",
            "zone.json",
            "--analysis-bundle",
            "analysis.json",
            "--filter-job-id",
            resolved_job.filter_job_id,
            "--llm",
            "mock",
        ]
    )
    runtime_dependencies = filter_output_projection_runner.build_runner_projection_runtime_dependencies(
        args=args,
        resolved_job=resolved_job,
    )
    assert runtime_dependencies.llm_provider is None


def test_build_runner_dependencies_direct_api_does_not_materialize_provider() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    resolved_job = composition.resolve_filter_output_projection_job(
        IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id
    )
    args = filter_output_projection_runner.parse_args(
        [
            "--zone-match-bundle",
            "zone.json",
            "--analysis-bundle",
            "analysis.json",
            "--filter-job-id",
            resolved_job.filter_job_id,
            "--llm",
            "api",
            "--llm-profile",
            "qwen3_7_plus_2026_05_26",
            "--no-thinking",
        ]
    )
    with patch(
        "scripts.stage_runners.filter_output_projection_runner.build_llm_provider_from_cli_args",
    ) as build_provider:
        runtime_dependencies = (
            filter_output_projection_runner.build_runner_projection_runtime_dependencies(
                args=args,
                resolved_job=resolved_job,
            )
        )
    build_provider.assert_not_called()
    assert runtime_dependencies.llm_provider is None


def test_build_runner_dependencies_overview_mock_uses_overview_mock_provider() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    resolved_job = composition.resolve_filter_output_projection_job("ib_overview")
    args = filter_output_projection_runner.parse_args(
        [
            "--zone-match-bundle",
            "zone.json",
            "--analysis-bundle",
            "analysis.json",
            "--filter-job-id",
            "ib_overview",
            "--llm",
            "mock",
        ]
    )
    with (
        patch(
            "scripts.stage_runners.filter_output_projection_runner.build_llm_provider_from_cli_args",
        ) as build_provider,
        patch(
            "llm.execution_configs.materialize_llm_provider",
        ) as materialize_provider,
    ):
        runtime_dependencies = (
            filter_output_projection_runner.build_runner_projection_runtime_dependencies(
                args=args,
                resolved_job=resolved_job,
            )
        )
    build_provider.assert_not_called()
    materialize_provider.assert_not_called()
    assert isinstance(runtime_dependencies.llm_provider, OverviewStandaloneMockProvider)


def test_build_runner_dependencies_overview_api_uses_cli_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    resolved_job = composition.resolve_filter_output_projection_job("ib_overview")
    args = filter_output_projection_runner.parse_args(
        [
            "--zone-match-bundle",
            "zone.json",
            "--analysis-bundle",
            "analysis.json",
            "--filter-job-id",
            "ib_overview",
            "--llm",
            "api",
            "--llm-profile",
            "qwen3_7_plus_2026_05_26",
            "--no-thinking",
        ]
    )
    sentinel = object()

    def _fake_build_api(*_args, **_kwargs):
        return sentinel

    monkeypatch.setattr(
        "llm.provider_cli.build_api_provider",
        _fake_build_api,
    )
    with patch.object(
        projection_runtime_module,
        "materialize_installed_projection_runtime_dependencies",
    ) as materialize_installed:
        runtime_dependencies = (
            filter_output_projection_runner.build_runner_projection_runtime_dependencies(
                args=args,
                resolved_job=resolved_job,
            )
        )
    materialize_installed.assert_not_called()
    assert runtime_dependencies.llm_provider is sentinel


def test_runner_calls_runtime_stage_not_filter_or_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _isolate_projection_runner_project_root(tmp_path, monkeypatch)
    zone_path, analysis_path = _write_zone_match_bundle(tmp_path)
    composition = build_installed_document_consistency_qc_application_composition()
    filter_job_id = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id
    resolved_job = composition.resolve_filter_output_projection_job(filter_job_id)
    stage_result = FilterOutputProjectionStageResult(
        output_dir=tmp_path / "out",
        run_id="projection_runner_test",
        filter_job_id=filter_job_id,
        doc_id="doc_test",
        zone_key="ib_clinical_safety_zh",
        step_result=FilterOutputProjectionStepResult(
            filter_job_id=filter_job_id,
            doc_id="doc_test",
            file_hash=(
                "sha256:0123456789abcdef0123456789abcdef"
                "0123456789abcdef0123456789abcdef"
            ),
            zone_key="ib_clinical_safety_zh",
        ),
        projection_bundle_path=tmp_path / "out" / FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME,
        run_summary_path=tmp_path / "out" / "run_summary.json",
    )

    monkeypatch.setattr(
        filter_output_projection_runner,
        "build_installed_document_consistency_qc_application_composition",
        lambda: composition,
    )

    with (
        patch.object(
            filter_output_projection_runner,
            "run_filter_output_projection_stage",
            return_value=stage_result,
        ) as mock_stage,
        patch("runtime.filter_stage.run_filter_stage") as mock_filter,
        patch.object(
            projection_runtime_module,
            "materialize_installed_projection_runtime_dependencies",
        ) as materialize_installed,
    ):
        filter_output_projection_runner.main(
            _base_runner_argv(zone_path, analysis_path, filter_job_id, llm_mode="mock")
        )

    mock_filter.assert_not_called()
    materialize_installed.assert_not_called()
    mock_stage.assert_called_once()
    call_kwargs = mock_stage.call_args.kwargs
    assert call_kwargs["filter_job_id"] == filter_job_id
    assert call_kwargs["resolved_job"] == resolved_job
    assert call_kwargs["zone_match_bundle_path"] == zone_path.resolve()
    assert call_kwargs["analysis_bundle_path"] == analysis_path.resolve()
    output_dir = call_kwargs["output_dir"]
    assert output_dir.is_relative_to(project_root / "runs" / "filter_output_projection")
    assert call_kwargs["run_id"].startswith("filter_output_projection_")
    expected_dependencies = FilterOutputProjectionRuntimeDependencies(llm_provider=None)
    assert call_kwargs["facade"] == composition.filter_output_projection_facade_builder(
        job=call_kwargs["resolved_job"],
        runtime_dependencies=expected_dependencies,
    )
    assert call_kwargs["facade"] is DIRECT_FILTER_OUTPUT_PROJECTION_FACADE
    session_dirs = list((project_root / "runs" / "filter_output_projection").iterdir())
    assert len(session_dirs) == 1
    assert output_dir.is_relative_to(session_dirs[0])


def test_overview_runner_does_not_use_installed_projection_runtime_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _isolate_projection_runner_project_root(tmp_path, monkeypatch)
    zone_path, analysis_path = _write_zone_match_bundle(tmp_path)
    composition = build_installed_document_consistency_qc_application_composition()

    monkeypatch.setattr(
        filter_output_projection_runner,
        "build_installed_document_consistency_qc_application_composition",
        lambda: composition,
    )
    monkeypatch.setattr(
        filter_output_projection_runner,
        "run_filter_output_projection_stage",
        lambda **kwargs: FilterOutputProjectionStageResult(
            output_dir=kwargs["output_dir"],
            run_id=kwargs["run_id"],
            filter_job_id="ib_overview",
            doc_id="doc_regression",
            zone_key="ib_overview_zh",
            step_result=FilterOutputProjectionStepResult(
                filter_job_id="ib_overview",
                doc_id="doc_regression",
                file_hash=(
                    "sha256:0123456789abcdef0123456789abcdef"
                    "0123456789abcdef0123456789abcdef"
                ),
                zone_key="ib_overview_zh",
            ),
            projection_bundle_path=kwargs["output_dir"]
            / FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME,
            run_summary_path=kwargs["output_dir"] / "run_summary.json",
        ),
    )

    with (
        patch.object(
            projection_runtime_module,
            "materialize_installed_projection_runtime_dependencies",
        ) as materialize_installed,
        patch(
            "llm.providers.factory.build_api_provider",
        ) as build_api_provider,
    ):
        filter_output_projection_runner.main(
            _base_runner_argv(zone_path, analysis_path, "ib_overview", llm_mode="mock")
        )

    materialize_installed.assert_not_called()
    build_api_provider.assert_not_called()
    layout_dirs = list(
        (project_root / "runs" / "filter_output_projection").glob(
            "*/doc_regression/ib_overview"
        )
    )
    assert len(layout_dirs) == 1


def test_direct_projection_runtime_integration_persists_artifacts(
    tmp_path: Path,
) -> None:
    zone_path, analysis_path = _write_zone_match_bundle(tmp_path)
    composition = build_installed_document_consistency_qc_application_composition()
    filter_job_id = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id
    resolved_job = _resolved_direct_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH)
    runtime_dependencies = FilterOutputProjectionRuntimeDependencies(llm_provider=None)
    facade = composition.filter_output_projection_facade_builder(
        job=resolved_job,
        runtime_dependencies=runtime_dependencies,
    )
    output_dir = tmp_path / "projection_out"

    result = run_filter_output_projection_stage(
        filter_job_id=filter_job_id,
        resolved_job=resolved_job,
        zone_match_bundle_path=zone_path,
        analysis_bundle_path=analysis_path,
        facade=facade,
        output_dir=output_dir,
        run_id="projection_runner_integration",
    )

    bundle = load_json(result.projection_bundle_path)
    validate_filter_output_projection_bundle(bundle)
    assert result.run_summary_path.is_file()
    assert len(result.step_result.projected_sources) >= 1


def test_runner_layout_chain_writes_under_isolated_runs_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _isolate_projection_runner_project_root(tmp_path, monkeypatch)
    zone_path, analysis_path = _write_zone_match_bundle(tmp_path)
    composition = build_installed_document_consistency_qc_application_composition()
    filter_job_id = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id

    monkeypatch.setattr(
        filter_output_projection_runner,
        "build_installed_document_consistency_qc_application_composition",
        lambda: composition,
    )

    captured: dict[str, object] = {}

    def _capture_stage_call(**kwargs):
        captured.update(kwargs)
        output_dir = kwargs["output_dir"]
        return FilterOutputProjectionStageResult(
            output_dir=output_dir,
            run_id=str(kwargs["run_id"]),
            filter_job_id=filter_job_id,
            doc_id="doc_regression",
            zone_key="ib_clinical_safety_zh",
            step_result=FilterOutputProjectionStepResult(
                filter_job_id=filter_job_id,
                doc_id="doc_regression",
                file_hash=(
                    "sha256:0123456789abcdef0123456789abcdef"
                    "0123456789abcdef0123456789abcdef"
                ),
                zone_key="ib_clinical_safety_zh",
            ),
            projection_bundle_path=output_dir / FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME,
            run_summary_path=output_dir / "run_summary.json",
        )

    with patch.object(
        filter_output_projection_runner,
        "run_filter_output_projection_stage",
        side_effect=_capture_stage_call,
    ):
        filter_output_projection_runner.main(
            _base_runner_argv(zone_path, analysis_path, filter_job_id, llm_mode="mock")
        )

    output_dir = captured["output_dir"]
    assert isinstance(output_dir, Path)
    assert output_dir.is_relative_to(project_root / "runs" / "filter_output_projection")
    assert str(captured["run_id"]).startswith("filter_output_projection_")
    layout_dirs = list(
        (project_root / "runs" / "filter_output_projection").glob(
            f"*/doc_regression/{filter_job_id}"
        )
    )
    assert layout_dirs == [output_dir]
