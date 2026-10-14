from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
)
from artifacts.evidence_source_preparation.schema import (
    EVIDENCE_SOURCE_PREPARATION_STAGE,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import (
    run_prepare,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stop_points import (
    EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP,
)
from runtime.io import load_json
from runtime.prepare_upstream_paths import (
    discover_doc_meta_dir,
    resolve_prepare_upstream_inputs_from_dirs,
)
from runtime.run_ids import format_run_timestamp
from runtime.run_layout import (
    STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT,
    format_doc_run_dir_name,
)
from scripts.stage_runners.evidence_source_preparation.aggregate_evidence import prepare_runner
from tests.evidence_source_preparation_phase_test_helpers import (
    installed_prepare_phase_kwargs,
)
from tests.route_runtime_test_helpers import (
    PersistedRouteArtifacts,
    persist_route_artifacts_from_coverage,
    write_prepare_upstream_run_tree,
    write_upstream_route_fixtures,
)

DOC_ID_FIXTURE = "doc_test"
SEMANTIC_MODULE_ID_FIXTURE = "clinical_safety"


def _mock_git_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence import (
        operations,
    )

    monkeypatch.setattr(
        operations,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _persist_route_for_tree(
    paths: dict[str, Path],
    *,
    output_dir: Path,
    run_id: str,
) -> PersistedRouteArtifacts:
    return persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=output_dir,
        run_id=run_id,
    )


def _materialized_routed_aggregate(tmp_path: Path) -> dict[str, Path]:
    paths = write_upstream_route_fixtures(tmp_path / "inputs")
    route_out = tmp_path / "route_out"
    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=route_out,
        run_id="tag_prepare_cli_route",
    )
    return {
        "aggregate_bundle": route_result.routed_bundle_paths["aggregate"],
        "coverage": paths["coverage"],
        "block_manifest": paths["block_manifest"],
        "doc_meta": paths["doc_meta_bundle"],
        "analysis": paths["analysis"],
    }


def _run_prepare_on_materialized_inputs(
    tmp_path: Path,
    *,
    out_dir: Path | None = None,
) -> Path:
    paths = write_upstream_route_fixtures(tmp_path / "inputs")
    route_out = tmp_path / "route_out"
    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=route_out,
        run_id="evidence_source_preparation_prepare_test_route",
    )
    output = out_dir if out_dir is not None else tmp_path / "prepare_out"
    run_prepare(
        **installed_prepare_phase_kwargs(),
        routed_aggregate_bundle_path=route_result.routed_bundle_paths["aggregate"],
        routing_manifest_path=route_result.routing_manifest_path,
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=output,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        run_id="evidence_source_preparation_prepare_test",
    )
    return output


def test_run_summary_records_inputs_and_outputs(tmp_path: Path) -> None:
    out_dir = _run_prepare_on_materialized_inputs(tmp_path)

    summary = load_json(out_dir / "run_summary.json")
    assert summary["stage"] == EVIDENCE_SOURCE_PREPARATION_STAGE
    assert summary["stats"]["phase"] == EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE
    assert "comparison_type" not in summary.get("stats", {})
    assert summary["file_hash"]
    assert summary["inputs"]["coverage_bundle"].endswith("coverage_bundle.json")
    assert summary["inputs"]["block_manifest"].endswith("block_manifest.json")
    assert summary["inputs"]["doc_meta_bundle"].endswith("doc_meta_bundle.json")
    assert summary["inputs"]["analysis_bundle"].endswith("analysis_bundle.json")
    assert summary["inputs"]["routed_aggregate_bundle"].endswith(
        "routed_units_aggregate.json"
    )
    assert summary["outputs"]["assessment_input"] == "assessment_input.json"
    assert summary["outputs"]["assessment_input_preview"] == "assessment_input_preview.json"
    assert "pre_llm_review_bundle" not in summary["outputs"]
    assert "pre_llm_audit_bundle_private" not in summary["outputs"]
    assert "pre_llm_review_state" not in summary["outputs"]
    assert summary["outputs"]["run_summary"] == "run_summary.json"
    assert summary["stats"]["unit_count"] == summary["stats"]["aggregate_unit_count"]


def test_resolve_prepare_upstream_inputs_from_dirs_finds_all_artifacts(
    tmp_path: Path,
) -> None:
    paths = write_prepare_upstream_run_tree(tmp_path)
    resolved = resolve_prepare_upstream_inputs_from_dirs(
        filter_run_dir=paths["filter_run_dir"],
        doc_meta_dir=paths["doc_meta_dir"],
        project_root=tmp_path,
    )

    assert resolved["coverage_bundle_path"] == paths["coverage"].resolve()
    assert resolved["block_manifest_path"] == paths["block_manifest"].resolve()
    assert resolved["doc_meta_bundle_path"] == paths["doc_meta_bundle"].resolve()
    assert resolved["analysis_bundle_path"] == paths["analysis"].resolve()
    assert resolved["doc_id"] == DOC_ID_FIXTURE
    assert resolved["zone_key"] == "ib_clinical_safety_zh"


def test_aggregate_evidence_prepare_runner_cli_explicit_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_dir = tmp_path / "tag_prepare_cli"
    routed = _materialized_routed_aggregate(tmp_path)
    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(routed["aggregate_bundle"]),
            "--coverage-bundle",
            str(routed["coverage"]),
            "--block-manifest",
            str(routed["block_manifest"]),
            "--doc-meta-bundle",
            str(routed["doc_meta"]),
            "--analysis-bundle",
            str(routed["analysis"]),
            "--out",
            str(out_dir),
        ],
    )
    prepare_runner.main()

    assessment_input = load_json(out_dir / "assessment_input.json")
    assert assessment_input["stage"] == EVIDENCE_SOURCE_PREPARATION_STAGE
    assert assessment_input["phase"] == EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE
    assert "comparison_type" not in assessment_input
    assert not (out_dir / "llm_input_aggregate.json").exists()
    assert not (out_dir / "pre_llm_review_state.json").exists()
    index = load_json(out_dir / "index.json")
    assert index["step"] == EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP
    assert index["documents"][0]["outputs"]["assessment_input"] == "assessment_input.json"


def test_aggregate_evidence_prepare_runner_rejects_retired_pre_llm_review_flag(
) -> None:
    with pytest.raises(SystemExit):
        prepare_runner.parse_args(
            [
            "--routed-aggregate-bundle",
            "routed.json",
            "--coverage-bundle",
            "coverage.json",
            "--block-manifest",
            "block_manifest.json",
            "--doc-meta-bundle",
            "doc_meta.json",
            "--analysis-bundle",
            "analysis.json",
            "--pre-llm-review",
            "off",
            ]
        )


def test_aggregate_evidence_prepare_runner_cli_directory_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_dir = tmp_path / "tag_prepare_dir_cli"
    paths = write_prepare_upstream_run_tree(tmp_path)
    route_result = _persist_route_for_tree(
        paths,
        output_dir=tmp_path / "route_fixture",
        run_id="tag_prepare_dir_route",
    )
    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(prepare_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(route_result.routed_bundle_paths["aggregate"]),
            "--filter-run-dir",
            str(paths["filter_run_dir"]),
            "--doc-meta-dir",
            str(paths["doc_meta_dir"]),
            "--out",
            str(out_dir),
        ],
    )
    prepare_runner.main()

    summary = load_json(out_dir / "run_summary.json")
    assert summary["stage"] == "evidence_source_preparation"
    assert summary["stats"]["phase"] == EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE
    assert summary["outputs"]["assessment_input"] == "assessment_input.json"
    assert "llm_input_aggregate" not in summary["outputs"]
    assert "pre_llm_review_state" not in summary["outputs"]
    assert "tag_output" not in summary["outputs"]
    index = load_json(out_dir / "index.json")
    assert index["step"] == EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP


def test_aggregate_evidence_prepare_runner_directory_mode_default_output_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = write_prepare_upstream_run_tree(tmp_path)
    route_result = _persist_route_for_tree(
        paths,
        output_dir=tmp_path / "route_fixture",
        run_id="tag_prepare_layout_route",
    )

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(prepare_runner, "PROJECT_ROOT", tmp_path)
    fixed_stamp = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.operations.utc_run_stamp",
        lambda: fixed_stamp,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(route_result.routed_bundle_paths["aggregate"]),
            "--filter-run-dir",
            str(paths["filter_run_dir"]),
            "--doc-meta-dir",
            str(paths["doc_meta_dir"]),
        ],
    )
    prepare_runner.main()

    captured = capsys.readouterr()
    assert "route=aggregate" in captured.out
    assert "evidence_form_id=aggregate_evidence" in captured.out
    assert "comparison_type=" not in captured.out
    assert "semantic_module_id=clinical_safety" in captured.out

    expected_run_id = format_run_timestamp(fixed_stamp)
    expected_out = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "prepare"
        / expected_run_id
        / DOC_ID_FIXTURE
        / SEMANTIC_MODULE_ID_FIXTURE
        / "aggregate_evidence"
    )
    assert expected_out.is_dir()
    assert (expected_out / "assessment_input.json").is_file()
    summary = load_json(expected_out / "run_summary.json")
    assert summary["run_dir_layout"] == STAGE_PHASE_EVIDENCE_FORM_RUN_DIR_LAYOUT
    assert summary["stage"] == "evidence_source_preparation"
    assert summary["run_id"] == expected_run_id
    session_index = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "prepare"
        / expected_run_id
        / "index.json"
    )
    assert session_index.is_file()
    index = load_json(session_index)
    assert index["step"] == EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP
    assert index["documents"][0]["outputs"]["assessment_input"].endswith(
        "assessment_input.json"
    )


def test_aggregate_evidence_prepare_runner_directory_mode_respects_custom_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = write_prepare_upstream_run_tree(tmp_path)
    route_result = _persist_route_for_tree(
        paths,
        output_dir=tmp_path / "route_fixture",
        run_id="tag_prepare_custom_route",
    )
    custom_run_id = "tag_prepare_custom_demo_001"

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(prepare_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(route_result.routed_bundle_paths["aggregate"]),
            "--filter-run-dir",
            str(paths["filter_run_dir"]),
            "--doc-meta-dir",
            str(paths["doc_meta_dir"]),
            "--run-id",
            custom_run_id,
        ],
    )
    prepare_runner.main()

    expected_out = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "prepare"
        / custom_run_id
        / DOC_ID_FIXTURE
        / SEMANTIC_MODULE_ID_FIXTURE
        / "aggregate_evidence"
    )
    assert expected_out.is_dir()
    summary = load_json(expected_out / "run_summary.json")
    assert summary["run_id"] == custom_run_id
    session_index = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "prepare"
        / custom_run_id
        / "index.json"
    )
    assert session_index.is_file()


def test_resolve_prepare_upstream_inputs_missing_block_manifest(
    tmp_path: Path,
) -> None:
    paths = write_prepare_upstream_run_tree(
        tmp_path,
        include_block_manifest=False,
    )

    with pytest.raises(ValueError, match="block_manifest must be a file"):
        resolve_prepare_upstream_inputs_from_dirs(
            filter_run_dir=paths["filter_run_dir"],
            doc_meta_dir=paths["doc_meta_dir"],
            project_root=tmp_path,
        )


def test_resolve_summary_path_uses_project_root_not_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_rel = "runs/prepare_analysis/missing/doc_x/analysis_bundle.json"
    other_cwd = tmp_path / "other_cwd"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    filter_dir = tmp_path / "filter" / "zone_test" / DOC_ID_FIXTURE
    filter_dir.mkdir(parents=True)
    _write_json(
        filter_dir / "run_summary.json",
        {
            "inputs": {"input_analysis_bundle": missing_rel},
            "outputs": {"coverage_bundle": "coverage_bundle.json"},
        },
    )
    _write_json(filter_dir / "coverage_bundle.json", {"doc_id": DOC_ID_FIXTURE})
    doc_meta_dir = tmp_path / "doc_meta" / DOC_ID_FIXTURE
    doc_meta_dir.mkdir(parents=True)
    _write_json(doc_meta_dir / "doc_meta_bundle.json", {"doc_id": DOC_ID_FIXTURE})

    with pytest.raises(ValueError) as exc:
        resolve_prepare_upstream_inputs_from_dirs(
            filter_run_dir=filter_dir,
            doc_meta_dir=doc_meta_dir,
            project_root=tmp_path,
        )
    assert str(tmp_path / missing_rel) in str(exc.value)
    assert "other_cwd" not in str(exc.value)


def test_resolve_prepare_upstream_inputs_doc_id_mismatch(tmp_path: Path) -> None:
    paths = write_prepare_upstream_run_tree(
        tmp_path,
        coverage_doc_id="doc_mismatch",
    )

    with pytest.raises(ValueError, match="doc_id mismatch"):
        resolve_prepare_upstream_inputs_from_dirs(
            filter_run_dir=paths["filter_run_dir"],
            doc_meta_dir=paths["doc_meta_dir"],
            project_root=tmp_path,
        )


def test_aggregate_evidence_prepare_runner_rejects_mixed_input_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            "routed.json",
            "--filter-run-dir",
            "filter-run",
            "--coverage-bundle",
            "coverage.json",
        ],
    )
    with pytest.raises(SystemExit, match="input modes are mutually exclusive"):
        prepare_runner.main()


def test_aggregate_evidence_prepare_runner_rejects_partial_explicit_mode() -> None:
    with pytest.raises(SystemExit, match="explicit file mode requires all four input flags"):
        prepare_runner.parse_args(
            [
                "--routed-aggregate-bundle",
                "routed.json",
                "--coverage-bundle",
                "coverage.json",
            ]
        )


def test_aggregate_evidence_prepare_runner_rejects_doc_meta_dir_without_filter_run_dir() -> None:
    with pytest.raises(SystemExit, match="--doc-meta-dir requires --filter-run-dir"):
        prepare_runner.parse_args(
            [
                "--routed-aggregate-bundle",
                "routed.json",
                "--doc-meta-dir",
                "doc-meta-run",
            ]
        )


def test_aggregate_evidence_prepare_runner_accepts_filter_run_dir_alone() -> None:
    args = prepare_runner.parse_args(
        [
            "--routed-aggregate-bundle",
            "routed.json",
            "--filter-run-dir",
            "filter-run",
        ]
    )
    assert args.filter_run_dirs == ["filter-run"]
    assert args.doc_meta_dir is None




def _run_route_on_materialized_inputs(tmp_path: Path) -> Path:
    paths = write_upstream_route_fixtures(tmp_path / "inputs")
    route_out = tmp_path / "route_out"
    persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=route_out,
        run_id="route_fixture_test",
    )
    return route_out


def test_route_persist_artifacts_from_coverage_keeps_existing_counts(
    tmp_path: Path,
) -> None:
    route_out = _run_route_on_materialized_inputs(tmp_path)
    aggregate = load_json(route_out / "routed_units_aggregate.json")
    manifest = load_json(route_out / "routing_manifest.json")

    assert len(aggregate.get("units") or []) == 2
    assert manifest["route_counts"]["aggregate"] == 2
    assert not any(
        unit.get("source_stage") == "overview_decompose"
        for unit in aggregate.get("units") or []
    )


def test_discover_doc_meta_dir_finds_matching_run(tmp_path: Path) -> None:
    paths = write_prepare_upstream_run_tree(tmp_path)

    discovered = discover_doc_meta_dir(
        filter_run_dir=paths["filter_run_dir"],
        project_root=tmp_path,
    )
    assert discovered.resolve() == paths["doc_meta_dir"].resolve()


def test_discover_doc_meta_dir_returns_most_recent_when_multiple(tmp_path: Path) -> None:
    paths = write_prepare_upstream_run_tree(
        tmp_path,
        doc_meta_run_id="doc_meta_a",
    )

    # Create a second (newer) doc_meta run pointing to the same analysis.
    newer_doc_meta_dir = tmp_path / "runs" / "doc_meta" / "doc_meta_z" / DOC_ID_FIXTURE
    newer_doc_meta_dir.mkdir(parents=True)
    old_summary = load_json(paths["doc_meta_dir"] / "run_summary.json")
    _write_json(newer_doc_meta_dir / "run_summary.json", old_summary)
    _write_json(
        newer_doc_meta_dir / "doc_meta_bundle.json",
        load_json(paths["doc_meta_bundle"]),
    )

    discovered = discover_doc_meta_dir(
        filter_run_dir=paths["filter_run_dir"],
        project_root=tmp_path,
    )
    assert discovered.resolve() == newer_doc_meta_dir.resolve()


def test_discover_doc_meta_dir_raises_when_no_match(tmp_path: Path) -> None:
    paths = write_prepare_upstream_run_tree(tmp_path)
    # Remove all doc_meta runs.
    shutil.rmtree(tmp_path / "runs" / "doc_meta")

    with pytest.raises(ValueError, match="doc_meta_runner.py"):
        discover_doc_meta_dir(
            filter_run_dir=paths["filter_run_dir"],
            project_root=tmp_path,
        )


def test_aggregate_evidence_prepare_runner_cli_auto_discover_doc_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_dir = tmp_path / "tag_prepare_auto"
    paths = write_prepare_upstream_run_tree(tmp_path)
    route_result = _persist_route_for_tree(
        paths,
        output_dir=tmp_path / "route_fixture",
        run_id="tag_prepare_auto_route",
    )
    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(prepare_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(route_result.routed_bundle_paths["aggregate"]),
            "--filter-run-dir",
            str(paths["filter_run_dir"]),
            "--out",
            str(out_dir),
        ],
    )
    prepare_runner.main()

    assert (out_dir / "assessment_input.json").is_file()
    summary = load_json(out_dir / "run_summary.json")
    assert summary["stage"] == "evidence_source_preparation"
    assert "doc_meta_bundle" in summary["inputs"] or "assessment_input" in summary["inputs"]


def _expected_prepare_out(
    tmp_path: Path,
    *,
    run_id: str,
    doc_id: str,
    semantic_module_id: str = SEMANTIC_MODULE_ID_FIXTURE,
) -> Path:
    return (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "prepare"
        / run_id
        / format_doc_run_dir_name(doc_id)
        / semantic_module_id
        / "aggregate_evidence"
    )


def _route_fixture_in_tmp(
    tmp_path: Path,
) -> tuple[dict[str, Path], PersistedRouteArtifacts]:
    paths = write_prepare_upstream_run_tree(tmp_path)
    route_result = _persist_route_for_tree(
        paths,
        output_dir=tmp_path / "route_fixture",
        run_id="prepare_path_test_route",
    )
    return paths, route_result


def test_aggregate_evidence_prepare_runner_directory_mode_no_pollute_route_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, route_result = _route_fixture_in_tmp(tmp_path)
    route_dir = route_result.output_dir
    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(prepare_runner, "PROJECT_ROOT", tmp_path)
    run_id = "prepare_dir_canonical_test"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(route_result.routed_bundle_paths["aggregate"]),
            "--filter-run-dir",
            str(paths["filter_run_dir"]),
            "--run-id",
            run_id,
        ],
    )
    prepare_runner.main()
    expected_out = _expected_prepare_out(
        tmp_path,
        run_id=run_id,
        doc_id=DOC_ID_FIXTURE,
    )
    assert expected_out.is_dir()
    assert (expected_out / "assessment_input.json").is_file()
    assert not (route_dir / "assessment_input.json").exists()
    assert not (route_dir / "pre_llm_review_state.json").exists()
    assert not (route_dir / "unit_integrity_report.json").exists()


def test_aggregate_evidence_prepare_runner_explicit_mode_default_canonical_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routed = _materialized_routed_aggregate(tmp_path)
    route_dir = routed["aggregate_bundle"].parent
    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(prepare_runner, "PROJECT_ROOT", tmp_path)
    run_id = "prepare_explicit_canonical_test"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(routed["aggregate_bundle"]),
            "--coverage-bundle",
            str(routed["coverage"]),
            "--block-manifest",
            str(routed["block_manifest"]),
            "--doc-meta-bundle",
            str(routed["doc_meta"]),
            "--analysis-bundle",
            str(routed["analysis"]),
            "--run-id",
            run_id,
        ],
    )
    prepare_runner.main()
    expected_out = _expected_prepare_out(
        tmp_path,
        run_id=run_id,
        doc_id=DOC_ID_FIXTURE,
    )
    assert expected_out.is_dir()
    assert (expected_out / "assessment_input.json").is_file()
    assert not (route_dir / "assessment_input.json").exists()
    session_index = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "prepare"
        / run_id
        / "index.json"
    )
    assert session_index.is_file()
    index = load_json(session_index)
    assert index["step"] == EVIDENCE_SOURCE_PREPARATION_PREPARE_STEP
    assert index["documents"][0]["outputs"]["assessment_input"].endswith(
        "assessment_input.json"
    )


def test_aggregate_evidence_prepare_runner_input_mode_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, route_result = _route_fixture_in_tmp(tmp_path)
    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(prepare_runner, "PROJECT_ROOT", tmp_path)
    run_id = "prepare_parity_test"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(route_result.routed_bundle_paths["aggregate"]),
            "--filter-run-dir",
            str(paths["filter_run_dir"]),
            "--run-id",
            run_id,
        ],
    )
    prepare_runner.main()
    dir_mode_out = _expected_prepare_out(
        tmp_path,
        run_id=run_id,
        doc_id=DOC_ID_FIXTURE,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(route_result.routed_bundle_paths["aggregate"]),
            "--coverage-bundle",
            str(paths["coverage"]),
            "--block-manifest",
            str(paths["block_manifest"]),
            "--doc-meta-bundle",
            str(paths["doc_meta_bundle"]),
            "--analysis-bundle",
            str(paths["analysis"]),
            "--run-id",
            run_id,
        ],
    )
    prepare_runner.main()
    explicit_out = _expected_prepare_out(
        tmp_path,
        run_id=run_id,
        doc_id=DOC_ID_FIXTURE,
    )
    assert explicit_out == dir_mode_out


def test_aggregate_evidence_prepare_runner_explicit_out_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routed = _materialized_routed_aggregate(tmp_path)
    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(prepare_runner, "PROJECT_ROOT", tmp_path)
    custom_out = tmp_path / "custom_prepare_out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(routed["aggregate_bundle"]),
            "--coverage-bundle",
            str(routed["coverage"]),
            "--block-manifest",
            str(routed["block_manifest"]),
            "--doc-meta-bundle",
            str(routed["doc_meta"]),
            "--analysis-bundle",
            str(routed["analysis"]),
            "--out",
            str(custom_out),
            "--run-id",
            "prepare_custom_out",
        ],
    )
    prepare_runner.main()
    assert (custom_out / "assessment_input.json").is_file()
    assert not (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "prepare"
        / "prepare_custom_out"
    ).exists()


def test_aggregate_evidence_prepare_runner_projected_fan_in_directory_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_projected_fan_in_aggregate_prepare_e2e import (
        _build_fan_in_route_artifacts,
    )

    artifacts = _build_fan_in_route_artifacts(tmp_path)
    route_result = artifacts["route_result"]
    safety_dir = tmp_path / "filter" / "safety"
    overview_dir = tmp_path / "filter" / "overview"
    safety_dir.mkdir(parents=True)
    overview_dir.mkdir(parents=True)

    def _write_json_local(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    _write_json_local(
        safety_dir / "coverage_bundle.json",
        json.loads(artifacts["safety_coverage_path"].read_text(encoding="utf-8")),
    )
    _write_json_local(
        overview_dir / "coverage_bundle.json",
        json.loads(artifacts["overview_coverage_path"].read_text(encoding="utf-8")),
    )
    _write_json_local(
        safety_dir / "run_summary.json",
        {
            "doc_id": "doc_test",
            "inputs": {
                "input_analysis_bundle": artifacts["analysis_bundle_path"]
                .resolve()
                .relative_to(tmp_path.resolve())
                .as_posix(),
            },
            "outputs": {"coverage_bundle": "coverage_bundle.json"},
        },
    )
    _write_json_local(
        overview_dir / "run_summary.json",
        {
            "doc_id": "doc_test",
            "inputs": {
                "input_analysis_bundle": artifacts["analysis_bundle_path"]
                .resolve()
                .relative_to(tmp_path.resolve())
                .as_posix(),
            },
            "outputs": {"coverage_bundle": "coverage_bundle.json"},
        },
    )

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(prepare_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_runner.py",
            "--routed-aggregate-bundle",
            str(route_result.routed_bundle_paths["aggregate"]),
            "--filter-run-dir",
            str(safety_dir),
            "--filter-run-dir",
            str(overview_dir),
            "--doc-meta-dir",
            str(artifacts["doc_meta_bundle_path"].parent),
        ],
    )
    prepare_runner.main()

    assessment_inputs = list(
        tmp_path.glob(
            "runs/evidence_source_preparation/prepare/*/*/clinical_safety/aggregate_evidence/assessment_input.json"
        )
    )
    assert len(assessment_inputs) == 1
    assessment_input = json.loads(assessment_inputs[0].read_text(encoding="utf-8"))
    assert "zone_key" not in assessment_input or not str(
        assessment_input.get("zone_key") or ""
    ).strip()

    run_summaries = list(
        tmp_path.glob(
            "runs/evidence_source_preparation/prepare/*/*/clinical_safety/aggregate_evidence/run_summary.json"
        )
    )
    assert len(run_summaries) == 1
    prepare_summary = json.loads(run_summaries[0].read_text(encoding="utf-8"))
    assert "pre_llm_review_status" not in prepare_summary.get("stats", {})
    assert "pre_llm_review_bundle" not in prepare_summary.get("outputs", {})
