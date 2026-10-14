"""Tests for the canonical projected-source Route runner."""

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
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from artifacts.filter_output_projection_bundle import (
    FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME,
)
from artifacts.routing.schema import validate_route_routing_manifest, validate_routed_unit_bundle
from operations.filter_output_projection.fan_in import (
    build_projection_fan_in_inputs_from_bundles,
    select_projected_sources_for_semantic_module,
)
from runtime.io import load_json
from runtime.projected_source_route_stage import (
    PersistedProjectionRouteStageOutcome,
    ProjectedSourceRouteStageResult,
)
from scripts.stage_runners import route_runner
from tests.test_projection_fan_in import (
    LINEAGE_FILE_HASH,
    _persisted_bundle,
    _projected_source,
    _projection_result,
)

RUNNER_PATH = BACKEND_ROOT / "scripts" / "stage_runners" / "route_runner.py"

FORBIDDEN_RUNNER_TOKENS = (
    "runtime.route_stage",
    "run_route_stage",
    "coverage_bundle",
    "persist_route_artifacts_from_coverage",
    "route_tag_prepare_units",
    "run_from_projected_sources",
    "run_projected_source_route_stage",
    "run_filter_output_projection_stage",
    "run_filter_stage",
    "run_project_filter_output",
    "build_projection_fan_in_inputs_from_bundles",
    "select_projected_sources_for_semantic_module",
    "validate_filter_output_projection_bundle",
    "load_persisted_projection_bundles",
    "ProjectionFanInInput(",
    "ProjectionInputRef(",
    "plugins.clinical_trial_doc.routing",
)


def _isolate_route_runner_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    monkeypatch.setattr(route_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        route_runner,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )
    return tmp_path


def _write_upstream_artifacts(
    tmp_path: Path,
    *,
    doc_id: str = "doc_test",
    block_ids: tuple[str, ...] = ("C0001",),
) -> dict[str, Path]:
    blocks = [
        {
            "block_id": block_id,
            "kind": "paragraph",
            "order": index + 1,
            "heading_path": ["12 临床安全性", "12.3 概述"],
            "analysis_text": "正文",
            "text_ref": {
                "analysis_bundle_id": "analysis_test",
                "block_id": block_id,
            },
            "sentence_provenance": "legacy_whole_block",
        }
        for index, block_id in enumerate(block_ids)
    ]
    block_manifest = {
        "block_manifest_id": "block_manifest_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "blocks": blocks,
    }
    doc_meta_bundle = {
        "doc_meta_bundle_id": "doc_meta_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
        "summary": {"doc_type": "IB"},
    }
    analysis_bundle = {
        "analysis_bundle_id": "analysis_test",
        "doc_id": doc_id,
        "file_hash": LINEAGE_FILE_HASH,
    }
    paths = {
        "block_manifest": tmp_path / "block_manifest.json",
        "doc_meta_bundle": tmp_path / "doc_meta_bundle.json",
        "analysis_bundle": tmp_path / "analysis_bundle.json",
    }
    paths["block_manifest"].write_text(
        json.dumps(block_manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    paths["doc_meta_bundle"].write_text(
        json.dumps(doc_meta_bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    paths["analysis_bundle"].write_text(
        json.dumps(analysis_bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    return paths


def _write_projection_bundle(
    tmp_path: Path,
    *,
    filter_job_id: str,
    block_id: str,
    run_id: str,
    bundle_id_override: str | None = None,
) -> Path:
    step_result = _projection_result(
        filter_job_id=filter_job_id,
        projected_sources=(
            _projected_source(block_id=block_id, semantic_module_id="clinical_safety"),
        ),
    )
    bundle = _persisted_bundle(
        step_result=step_result,
        run_id=run_id,
        bundle_id_override=bundle_id_override,
    )
    bundle_dir = tmp_path / filter_job_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / FILTER_OUTPUT_PROJECTION_BUNDLE_FILENAME
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    return bundle_path


def test_runner_resolves_default_semantic_module_when_unambiguous() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    resolved = route_runner.resolve_runner_semantic_module_id(
        semantic_module_id=None,
        composition=composition,
    )
    assert resolved == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert len(composition.route_semantic_module_sequence) == 1


def test_runner_rejects_unknown_semantic_module() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    with pytest.raises(SystemExit, match="unknown or disabled"):
        route_runner.resolve_runner_semantic_module_id(
            semantic_module_id="efficacy",
            composition=composition,
        )


def test_runner_source_has_no_legacy_route_or_route_assembly_coupling() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    for token in FORBIDDEN_RUNNER_TOKENS:
        assert token not in source, f"runner must not reference {token!r}"
    assert "run_projected_source_route_from_projection_bundles" in source


def test_runner_import_graph_avoids_plugin_route_executor() -> None:
    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"), filename=str(RUNNER_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(module.startswith("plugins.") for module in imported)


def test_parse_args_rejects_missing_route_key_without_output_dir() -> None:
    with pytest.raises(SystemExit):
        route_runner.parse_args(
            [
                "--projection-bundle",
                "bundle.json",
                "--block-manifest",
                "block_manifest.json",
                "--doc-meta-bundle",
                "doc_meta_bundle.json",
                "--analysis-bundle",
                "analysis_bundle.json",
            ]
        )


def test_parse_args_does_not_accept_coverage_bundle_flag() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "--coverage-bundle" not in source


def test_runner_calls_runtime_persisted_projection_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _isolate_route_runner_project_root(tmp_path, monkeypatch)
    upstream = _write_upstream_artifacts(project_root, block_ids=("C0001", "C0002"))
    safety_bundle = _write_projection_bundle(
        project_root,
        filter_job_id="ib_clinical_safety",
        block_id="C0001",
        run_id="runner_runtime_test",
    )
    overview_bundle = _write_projection_bundle(
        project_root,
        filter_job_id="ib_overview",
        block_id="C0002",
        run_id="runner_runtime_test_overview",
    )
    composition = build_installed_document_consistency_qc_application_composition()
    stage_result = ProjectedSourceRouteStageResult(
        output_dir=project_root / "route_out",
        run_id="route_runner_test",
        doc_id="doc_test",
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        route_counts={"total_routed_unit_count": 1},
        routed_bundle_paths={
            "aggregate": project_root / "route_out" / "routed_units_aggregate.json",
            "table": project_root / "route_out" / "routed_units_table.json",
            "case": project_root / "route_out" / "routed_units_case.json",
            "unknown": project_root / "route_out" / "routed_units_unknown.json",
        },
        routing_manifest_path=project_root / "route_out" / "routing_manifest.json",
        run_summary_path=project_root / "route_out" / "run_summary.json",
    )
    captured: dict[str, object] = {}

    def _capture_runtime_entry(**kwargs: object) -> PersistedProjectionRouteStageOutcome:
        captured.update(kwargs)
        return PersistedProjectionRouteStageOutcome(
            route_result=stage_result,
            selected_projected_source_count=2,
            projection_bundle_count=2,
            projection_input_refs=(
                {
                    "filter_output_projection_bundle_id": "bundle_a",
                    "filter_job_id": "ib_clinical_safety",
                    "zone_key": "ib_overview_zh",
                },
                {
                    "filter_output_projection_bundle_id": "bundle_b",
                    "filter_job_id": "ib_overview",
                    "zone_key": "ib_overview_zh",
                },
            ),
        )

    monkeypatch.setattr(
        route_runner,
        "build_installed_document_consistency_qc_application_composition",
        lambda: composition,
    )

    with patch.object(
        route_runner,
        "run_projected_source_route_from_projection_bundles",
        side_effect=_capture_runtime_entry,
    ):
        route_runner.main(
            [
                "--projection-bundle",
                safety_bundle.as_posix(),
                "--projection-bundle",
                overview_bundle.as_posix(),
                "--block-manifest",
                upstream["block_manifest"].as_posix(),
                "--doc-meta-bundle",
                upstream["doc_meta_bundle"].as_posix(),
                "--analysis-bundle",
                upstream["analysis_bundle"].as_posix(),
                "--route-key",
                "ib_clinical_safety_zh",
                "--output-dir",
                (project_root / "route_out").as_posix(),
            ]
        )

    assert captured["route_executor"] is composition.projected_source_route_executor
    assert captured["semantic_module_id"] == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert len(captured["projection_bundle_paths"]) == 2


def test_runner_standalone_layout_under_tmp_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _isolate_route_runner_project_root(tmp_path, monkeypatch)
    upstream = _write_upstream_artifacts(project_root)
    bundle_path = _write_projection_bundle(
        project_root,
        filter_job_id="ib_clinical_safety",
        block_id="C0001",
        run_id="runner_layout_test",
    )
    composition = build_installed_document_consistency_qc_application_composition()

    monkeypatch.setattr(
        route_runner,
        "build_installed_document_consistency_qc_application_composition",
        lambda: composition,
    )

    route_runner.main(
        [
            "--projection-bundle",
            bundle_path.as_posix(),
            "--block-manifest",
            upstream["block_manifest"].as_posix(),
            "--doc-meta-bundle",
            upstream["doc_meta_bundle"].as_posix(),
            "--analysis-bundle",
            upstream["analysis_bundle"].as_posix(),
            "--route-key",
            "ib_clinical_safety_zh",
        ]
    )

    route_dirs = list((project_root / "runs" / "route").glob("*"))
    assert len(route_dirs) == 1
    aggregate_paths = list(route_dirs[0].glob("**/routed_units_aggregate.json"))
    assert len(aggregate_paths) == 1
    aggregate = load_json(aggregate_paths[0])
    validate_routed_unit_bundle(aggregate, expected_route="aggregate")
    manifest = load_json(aggregate_paths[0].parent / "routing_manifest.json")
    validate_route_routing_manifest(manifest)


def test_runner_multi_bundle_selection_matches_flow_semantics() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    direct = _projection_result(
        filter_job_id="ib_clinical_safety",
        projected_sources=(
            _projected_source(block_id="C0001", semantic_module_id="clinical_safety"),
        ),
    )
    overview = _projection_result(
        filter_job_id="ib_overview",
        projected_sources=(
            _projected_source(
                block_id="C0002",
                semantic_module_id="clinical_safety",
                representation="assembled",
            ),
            _projected_source(block_id="C0003", semantic_module_id="efficacy"),
        ),
    )
    bundles = (
        _persisted_bundle(step_result=direct, run_id="flow_parity_direct"),
        _persisted_bundle(step_result=overview, run_id="flow_parity_overview"),
    )
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=build_projection_fan_in_inputs_from_bundles(bundles),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    assert len(selection.selected_projected_sources) == 2
    assert len(selection.projection_input_refs) == 2
    assert {ref.filter_job_id for ref in selection.projection_input_refs} == {
        "ib_clinical_safety",
        "ib_overview",
    }
