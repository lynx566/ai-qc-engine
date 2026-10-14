"""Neutral Evidence Source Preparation stage input validation tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationStageContext,
    EvidenceSourcePreparationStageInput,
    EvidenceSourcePreparationUpstreamReferences,
    EvidenceSourcePreparationExecutionDependencies,
    FilterJobCoverageReference,
    ProjectionInputRefRecord,
    RouteStageReference,
    SelectedRouteOutputReference,
)
from operations.evidence_source_preparation.stage_validation import (
    validate_evidence_source_preparation_stage_input,
)
from operations.projected_source_route.output_contract import route_unit_count_key

RUNTIME_ADAPTER_PATH = (
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/stage.py"
)


class _NeutralExecutionDependencies(EvidenceSourcePreparationExecutionDependencies):
    pass


def _stage_input(
    *,
    route_counts: dict[str, int],
    routed_bundle_paths: dict[str, Path],
    selected_route_output: SelectedRouteOutputReference,
    evidence_form_id: str = "form_alpha",
) -> EvidenceSourcePreparationStageInput:
    return EvidenceSourcePreparationStageInput(
        route_stage=RouteStageReference(
            output_dir=Path("runs/route"),
            run_id="route_run",
            doc_id="doc_test",
            semantic_module_id="module_alpha",
            route_counts=route_counts,
            routed_bundle_paths=routed_bundle_paths,
            routing_manifest_path=Path("runs/route/routing_manifest.json"),
        ),
        projection_input_refs=(
            ProjectionInputRefRecord(
                filter_job_id="filter_job_alpha",
                zone_key="zone_alpha",
                filter_output_projection_bundle_id="projection_bundle_alpha",
            ),
        ),
        filter_job_coverage_refs=(
            FilterJobCoverageReference(
                filter_job_id="filter_job_alpha",
                coverage_bundle_path=Path("runs/filter/coverage_bundle.json"),
            ),
        ),
        upstream=EvidenceSourcePreparationUpstreamReferences(
            block_manifest_path=Path("runs/prepare/block_manifest.json"),
            doc_meta_bundle_path=Path("runs/doc_meta/doc_meta_bundle.json"),
            analysis_bundle_path=Path("runs/prepare/analysis_bundle.json"),
        ),
        context=EvidenceSourcePreparationStageContext(
            output_dir=Path("runs/esp"),
            run_id="esp_run",
        ),
        execution_dependencies=_NeutralExecutionDependencies(),
        evidence_form_id=evidence_form_id,
        selected_route_output=selected_route_output,
    )


def test_stage_input_rejects_mismatched_selected_route_path(tmp_path: Path) -> None:
    table_path = tmp_path / "routed_units_table.json"
    other_path = tmp_path / "routed_units_other.json"
    route_counts = {route_unit_count_key("table"): 1, "total_routed_unit_count": 1}
    routed_bundle_paths = {"table": table_path}
    selected = SelectedRouteOutputReference(
        route_output_kind="table",
        unit_count=1,
        routed_bundle_path=other_path,
    )

    with pytest.raises(ValueError, match="routed_bundle_path must match"):
        _stage_input(
            route_counts=route_counts,
            routed_bundle_paths=routed_bundle_paths,
            selected_route_output=selected,
        )


def test_stage_input_rejects_mismatched_unit_count(tmp_path: Path) -> None:
    table_path = tmp_path / "routed_units_table.json"
    route_counts = {route_unit_count_key("table"): 2, "total_routed_unit_count": 2}
    routed_bundle_paths = {"table": table_path}
    selected = SelectedRouteOutputReference(
        route_output_kind="table",
        unit_count=1,
        routed_bundle_path=table_path,
    )

    with pytest.raises(ValueError, match="unit_count must match"):
        _stage_input(
            route_counts=route_counts,
            routed_bundle_paths=routed_bundle_paths,
            selected_route_output=selected,
        )


def test_stage_input_accepts_consistent_handoff(tmp_path: Path) -> None:
    table_path = tmp_path / "routed_units_table.json"
    route_counts = {route_unit_count_key("table"): 2, "total_routed_unit_count": 2}
    routed_bundle_paths = {"table": table_path}
    selected = SelectedRouteOutputReference(
        route_output_kind="table",
        unit_count=2,
        routed_bundle_path=table_path,
    )

    stage_input = _stage_input(
        route_counts=route_counts,
        routed_bundle_paths=routed_bundle_paths,
        selected_route_output=selected,
    )

    validate_evidence_source_preparation_stage_input(stage_input)


def test_aggregate_runtime_does_not_dispatch_via_aggregate_path_literal() -> None:
    source = RUNTIME_ADAPTER_PATH.read_text(encoding="utf-8")
    assert 'routed_bundle_paths["aggregate"]' not in source
    assert "evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID" not in source
