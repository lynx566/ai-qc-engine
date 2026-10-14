"""Canonical projected-source Route runtime tests."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from operations.filter_output_projection.fan_in import (
    select_projected_sources_for_semantic_module,
)
from steps.project_filter_output import run as run_project_filter_output
from steps.route import RouteStepResult
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from runtime.projected_source_route_stage import run_projected_source_route_stage
from tests.test_filter_output_projection_direct import (
    _filter_artifacts_for_profile,
    _projection_input_for_profile,
    _resolved_direct_job,
)
from tests.route_test_fixtures import (
    _minimal_doc_meta,
    _projection_fan_in_input_for_step_result,
    _projection_input_refs_dicts,
)


def test_canonical_route_runtime_signature_has_no_legacy_inputs() -> None:
    signature = inspect.signature(run_projected_source_route_stage)
    assert "coverage_bundle" not in signature.parameters
    assert "overview_decompose_bundle" not in signature.parameters
    assert "zone_key" not in signature.parameters


@pytest.mark.parametrize("profile", (IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,))
def test_direct_projection_route_runtime_matches_baseline(profile: Any, tmp_path: Path) -> None:
    zone_match_bundle, _coverage, block_manifest, analysis_bundle = _filter_artifacts_for_profile(profile)
    projection_input = _projection_input_for_profile(profile, zone_match_bundle)
    step_result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=analysis_bundle,
        job=_resolved_direct_job(profile),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(
            _projection_fan_in_input_for_step_result(step_result),
        ),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    route_dir = tmp_path / "route"
    block_manifest_path = tmp_path / "block_manifest.json"
    block_manifest_path.write_text(
        json.dumps(block_manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    doc_meta_bundle_path = tmp_path / "doc_meta_bundle.json"
    doc_meta_bundle_path.write_text(
        json.dumps(_minimal_doc_meta(doc_id=projection_input.doc_id), ensure_ascii=False),
        encoding="utf-8",
    )
    analysis_bundle_path = tmp_path / "analysis_bundle.json"
    analysis_bundle_path.write_text(
        json.dumps(analysis_bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    route_result = run_projected_source_route_stage(
        projected_sources=selection.selected_projected_sources,
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        projection_input_refs=_projection_input_refs_dicts(selection),
        projection_doc_id=step_result.doc_id,
        projection_file_hash=step_result.file_hash,
        block_manifest_path=block_manifest_path,
        doc_meta_bundle_path=doc_meta_bundle_path,
        analysis_bundle_path=analysis_bundle_path,
        output_dir=route_dir,
        run_id="route_runtime_test",
        route_executor=composition.projected_source_route_executor,
    )
    assert route_result.routing_manifest_path.is_file()
    assert route_result.route_counts["total_routed_unit_count"] >= 0


def test_runtime_forwards_route_executor_to_step(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    forwarded: list[object] = []

    def _capture_run_from_projected_sources(**kwargs: Any) -> RouteStepResult:
        forwarded.append(kwargs.get("route_executor"))
        return RouteStepResult(
            doc_id="doc_test",
            zone_key="",
            route_artifacts={
                "routed_bundles": {
                    route: {"route": route, "units": []}
                    for route in ("aggregate", "table", "case", "unknown")
                },
                "routing_manifest": {
                    "route_counts": {"total_routed_unit_count": 0},
                },
                "route_counts": {"total_routed_unit_count": 0},
                "units_by_route": {
                    route: [] for route in ("aggregate", "table", "case", "unknown")
                },
            },
        )

    monkeypatch.setattr(
        "runtime.projected_source_route_stage.run_from_projected_sources",
        _capture_run_from_projected_sources,
    )

    block_manifest_path = tmp_path / "block_manifest.json"
    block_manifest_path.write_text(
        json.dumps(
            {
                "doc_id": "doc_test",
                "file_hash": "sha256:" + "a" * 64,
                "blocks": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    doc_meta_bundle_path = tmp_path / "doc_meta_bundle.json"
    doc_meta_bundle_path.write_text(
        json.dumps(_minimal_doc_meta(doc_id="doc_test"), ensure_ascii=False),
        encoding="utf-8",
    )
    analysis_bundle_path = tmp_path / "analysis_bundle.json"
    analysis_bundle_path.write_text(
        json.dumps(
            {
                "analysis_bundle_id": "test",
                "doc_id": "doc_test",
                "file_hash": "sha256:" + "a" * 64,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    run_projected_source_route_stage(
        projected_sources=(),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        block_manifest_path=block_manifest_path,
        doc_meta_bundle_path=doc_meta_bundle_path,
        analysis_bundle_path=analysis_bundle_path,
        output_dir=tmp_path / "route",
        run_id="route_forward_test",
        route_executor=composition.projected_source_route_executor,
    )

    assert forwarded == [composition.projected_source_route_executor]


def test_validate_route_stage_semantic_module_identity_accepts_matching_result() -> None:
    from runtime.projected_source_route_stage import (
        ProjectedSourceRouteStageResult,
        validate_route_stage_semantic_module_identity,
    )

    result = ProjectedSourceRouteStageResult(
        output_dir=Path("route_out"),
        run_id="run_test",
        doc_id="doc_test",
        semantic_module_id="clinical_safety",
        route_counts={"total_routed_unit_count": 0},
        routed_bundle_paths={},
        routing_manifest_path=Path("route_out/routing_manifest.json"),
        run_summary_path=Path("route_out/run_summary.json"),
    )

    validate_route_stage_semantic_module_identity(
        requested_semantic_module_id="clinical_safety",
        route_stage_result=result,
    )


def test_validate_route_stage_semantic_module_identity_rejects_mismatch() -> None:
    from runtime.projected_source_route_stage import (
        ProjectedSourceRouteStageResult,
        validate_route_stage_semantic_module_identity,
    )

    result = ProjectedSourceRouteStageResult(
        output_dir=Path("route_out"),
        run_id="run_test",
        doc_id="doc_test",
        semantic_module_id="efficacy",
        route_counts={"total_routed_unit_count": 0},
        routed_bundle_paths={},
        routing_manifest_path=Path("route_out/routing_manifest.json"),
        run_summary_path=Path("route_out/run_summary.json"),
    )

    with pytest.raises(ValueError, match="route stage semantic_module_id mismatch"):
        validate_route_stage_semantic_module_identity(
            requested_semantic_module_id="clinical_safety",
            route_stage_result=result,
        )
