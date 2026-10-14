"""Tests for manifest-driven aggregate-evidence prepare harness resolution."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare_harness_resolver import (
    resolve_prepare_harness_inputs,
)
from tests.test_projected_fan_in_aggregate_prepare_e2e import _build_fan_in_route_artifacts


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _filter_run_summary(*, analysis_bundle_path: Path, project_root: Path) -> dict:
    return {
        "doc_id": "doc_test",
        "inputs": {
            "input_analysis_bundle": analysis_bundle_path.resolve()
            .relative_to(project_root.resolve())
            .as_posix(),
        },
        "outputs": {"coverage_bundle": "coverage_bundle.json"},
    }


def test_resolve_prepare_harness_inputs_fan_in_requires_all_contributor_dirs(
    tmp_path: Path,
) -> None:
    artifacts = _build_fan_in_route_artifacts(tmp_path)
    route_result = artifacts["route_result"]
    routing_manifest = json.loads(route_result.routing_manifest_path.read_text(encoding="utf-8"))
    safety_dir = tmp_path / "filter" / "safety"
    safety_dir.mkdir(parents=True)
    _write_json(safety_dir / "coverage_bundle.json", json.loads(artifacts["safety_coverage_path"].read_text(encoding="utf-8")))
    _write_json(
        safety_dir / "run_summary.json",
        _filter_run_summary(
            analysis_bundle_path=artifacts["analysis_bundle_path"],
            project_root=tmp_path,
        ),
    )

    with pytest.raises(ValueError, match="requires exactly 2 --filter-run-dir"):
        resolve_prepare_harness_inputs(
            routing_manifest=routing_manifest,
            filter_run_dirs=[safety_dir],
            coverage_bundle=None,
            block_manifest=None,
            doc_meta_bundle_path=None,
            analysis_bundle=None,
            doc_meta_dir=artifacts["doc_meta_bundle_path"].parent,
            project_root=tmp_path,
        )


def test_resolve_prepare_harness_inputs_fan_in_maps_contributors(tmp_path: Path) -> None:
    artifacts = _build_fan_in_route_artifacts(tmp_path)
    route_result = artifacts["route_result"]
    routing_manifest = json.loads(route_result.routing_manifest_path.read_text(encoding="utf-8"))
    safety_dir = tmp_path / "filter" / "safety"
    overview_dir = tmp_path / "filter" / "overview"
    safety_dir.mkdir(parents=True)
    overview_dir.mkdir(parents=True)
    _write_json(
        safety_dir / "coverage_bundle.json",
        json.loads(artifacts["safety_coverage_path"].read_text(encoding="utf-8")),
    )
    _write_json(
        safety_dir / "run_summary.json",
        _filter_run_summary(
            analysis_bundle_path=artifacts["analysis_bundle_path"],
            project_root=tmp_path,
        ),
    )
    _write_json(
        overview_dir / "coverage_bundle.json",
        json.loads(artifacts["overview_coverage_path"].read_text(encoding="utf-8")),
    )
    _write_json(
        overview_dir / "run_summary.json",
        _filter_run_summary(
            analysis_bundle_path=artifacts["analysis_bundle_path"],
            project_root=tmp_path,
        ),
    )

    resolved, _ = resolve_prepare_harness_inputs(
        routing_manifest=routing_manifest,
        filter_run_dirs=[safety_dir, overview_dir],
        coverage_bundle=None,
        block_manifest=None,
        doc_meta_bundle_path=None,
        analysis_bundle=None,
        doc_meta_dir=artifacts["doc_meta_bundle_path"].parent,
        project_root=tmp_path,
    )

    assert resolved.projected_coverage_by_filter_job is not None
    assert resolved.coverage_bundle_path is None
    assert len(resolved.projection_input_refs) == 2
    assert set(resolved.projected_coverage_by_filter_job.bundles_by_filter_job_id) == {
        "ib_clinical_safety",
        "ib_overview",
    }


def test_resolve_prepare_harness_inputs_rejects_fan_in_explicit_mode(
    tmp_path: Path,
) -> None:
    artifacts = _build_fan_in_route_artifacts(tmp_path)
    routing_manifest = json.loads(
        artifacts["route_result"].routing_manifest_path.read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="explicit upstream file flags are not supported"):
        resolve_prepare_harness_inputs(
            routing_manifest=routing_manifest,
            filter_run_dirs=None,
            coverage_bundle=str(artifacts["safety_coverage_path"]),
            block_manifest=str(artifacts["block_manifest_path"]),
            doc_meta_bundle_path=str(artifacts["doc_meta_bundle_path"]),
            analysis_bundle=str(artifacts["analysis_bundle_path"]),
            doc_meta_dir=None,
            project_root=tmp_path,
        )
