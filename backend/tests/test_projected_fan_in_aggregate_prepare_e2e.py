"""E2E: projected multi-source Route fan-in through real Aggregate ESP Prepare."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_ids import (
    build_projected_fan_in_llm_input_bundle_id,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import ASSESSMENT_RUNTIME_CONTEXT_FILENAME
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import validate_assessment_input
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationStageContext,
    EvidenceSourcePreparationStageInput,
    EvidenceSourcePreparationUpstreamReferences,
    FilterJobCoverageReference,
    ProjectionInputRefRecord,
    RouteStageReference,
    SelectedRouteOutputReference,
)
from operations.projected_source_route.output_contract import resolve_route_unit_count
from artifacts.routing.types import ROUTES
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies,
)
from operations.filter_output_projection.fan_in import (
    select_projected_sources_for_semantic_module,
)
from steps.project_filter_output import run as run_project_filter_output
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    build_overview_semantic_decomposition_facade,
)
from runtime.evidence_source_preparation_stage import run_evidence_source_preparation_stage
from runtime.io import load_json, save_json
from runtime.projected_source_route_stage import run_projected_source_route_stage
from tests.route_test_fixtures import (
    _minimal_doc_meta,
    _projection_fan_in_input_for_step_result,
    _projection_input_refs_dicts,
)
from tests.test_filter_output_projection_direct import (
    LINEAGE_FILE_HASH,
    _analysis_bundle_for_zone_match,
    _filter_artifacts_for_profile,
    _projection_input_for_profile,
)
from tests.test_filter_output_projection_overview import (
    FakeOverviewProvider,
    _assessment_response,
    _paragraph_block,
    _zone_match_bundle,
)


def _build_fan_in_route_artifacts(tmp_path: Path) -> dict[str, object]:
    safety_profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    overview_profile = IB_OVERVIEW_FILTER_PROFILE_ZH
    safety_zone, safety_coverage, block_manifest, safety_analysis = _filter_artifacts_for_profile(
        safety_profile
    )
    overview_zone = _zone_match_bundle(
        blocks=[_paragraph_block("C2000", "概述安全性。")]
    )
    overview_zone["doc_id"] = safety_zone["doc_id"]
    overview_zone["file_hash"] = LINEAGE_FILE_HASH
    overview_analysis = _analysis_bundle_for_zone_match(overview_zone)
    _, overview_coverage, _, _ = _filter_artifacts_for_profile(overview_profile)
    overview_coverage = dict(overview_coverage)
    overview_coverage["doc_id"] = safety_zone["doc_id"]
    overview_coverage["file_hash"] = LINEAGE_FILE_HASH

    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    direct_result = run_project_filter_output(
        projection_input=_projection_input_for_profile(safety_profile, safety_zone),
        analysis_bundle=safety_analysis,
        job=composition.resolve_filter_output_projection_job(safety_profile.filter_job_id),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )
    prepared_alias = "O001"
    overview_result = run_project_filter_output(
        projection_input=_projection_input_for_profile(overview_profile, overview_zone),
        analysis_bundle=overview_analysis,
        job=composition.resolve_filter_output_projection_job(overview_profile.filter_job_id),
        facade=build_overview_semantic_decomposition_facade(
            llm_provider=FakeOverviewProvider(
                response_text=_assessment_response(
                    [(prepared_alias, ["clinical_safety"])]
                )
            )
        ),
    )
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(
            _projection_fan_in_input_for_step_result(
                direct_result,
                run_id="fan_in_direct",
            ),
            _projection_fan_in_input_for_step_result(
                overview_result,
                run_id="fan_in_overview",
            ),
        ),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    assert len(selection.projection_input_refs) == 2

    upstream_dir = tmp_path / "upstream"
    upstream_dir.mkdir()
    block_manifest_path = upstream_dir / "block_manifest.json"
    doc_meta_bundle_path = upstream_dir / "doc_meta_bundle.json"
    analysis_bundle_path = upstream_dir / "analysis_bundle.json"
    safety_coverage_path = upstream_dir / "safety_coverage.json"
    overview_coverage_path = upstream_dir / "overview_coverage.json"
    save_json(block_manifest_path, block_manifest)
    save_json(doc_meta_bundle_path, _minimal_doc_meta(doc_id=str(safety_zone["doc_id"])))
    save_json(analysis_bundle_path, safety_analysis)
    save_json(safety_coverage_path, safety_coverage)
    save_json(overview_coverage_path, overview_coverage)

    route_result = run_projected_source_route_stage(
        projected_sources=selection.selected_projected_sources,
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        projection_input_refs=_projection_input_refs_dicts(selection),
        projection_doc_id=str(safety_zone["doc_id"]),
        projection_file_hash=str(safety_zone.get("file_hash") or safety_coverage["file_hash"]),
        block_manifest_path=block_manifest_path,
        doc_meta_bundle_path=doc_meta_bundle_path,
        analysis_bundle_path=analysis_bundle_path,
        output_dir=tmp_path / "route",
        run_id="projected_fan_in_route",
        route_executor=composition.projected_source_route_executor,
    )
    return {
        "selection": selection,
        "route_result": route_result,
        "block_manifest_path": block_manifest_path,
        "doc_meta_bundle_path": doc_meta_bundle_path,
        "analysis_bundle_path": analysis_bundle_path,
        "safety_coverage_path": safety_coverage_path,
        "overview_coverage_path": overview_coverage_path,
    }


def test_projected_fan_in_route_to_real_aggregate_prepare_e2e(tmp_path: Path) -> None:
    artifacts = _build_fan_in_route_artifacts(tmp_path)
    selection = artifacts["selection"]
    route_result = artifacts["route_result"]

    aggregate_bundle = load_json(route_result.routed_bundle_paths["aggregate"])
    routing_manifest = load_json(route_result.routing_manifest_path)
    projection_refs = routing_manifest["source_refs"]["projection_input_refs"]
    assert len(projection_refs) == 2
    assert str(aggregate_bundle.get("zone_key") or "") == ""

    projection_input_refs = tuple(
        ProjectionInputRefRecord(
            filter_job_id=ref.filter_job_id,
            zone_key=ref.zone_key,
            filter_output_projection_bundle_id=ref.filter_output_projection_bundle_id,
        )
        for ref in selection.projection_input_refs
    )
    filter_job_coverage_refs = (
        FilterJobCoverageReference(
            filter_job_id=IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH.filter_job_id,
            coverage_bundle_path=artifacts["safety_coverage_path"],
        ),
        FilterJobCoverageReference(
            filter_job_id=IB_OVERVIEW_FILTER_PROFILE_ZH.filter_job_id,
            coverage_bundle_path=artifacts["overview_coverage_path"],
        ),
    )

    route_stage = RouteStageReference(
        output_dir=route_result.output_dir,
        run_id=route_result.run_id,
        doc_id=route_result.doc_id,
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        route_counts=dict(route_result.route_counts),
        routed_bundle_paths=dict(route_result.routed_bundle_paths),
        routing_manifest_path=route_result.routing_manifest_path,
    )
    selected_route_output = None
    for route_output_kind in ROUTES:
        unit_count = resolve_route_unit_count(route_stage.route_counts, route_output_kind)
        if unit_count <= 0:
            continue
        selected_route_output = SelectedRouteOutputReference(
            route_output_kind=route_output_kind,
            unit_count=unit_count,
            routed_bundle_path=route_stage.routed_bundle_paths[route_output_kind],
        )
        break
    assert selected_route_output is not None
    stage_input = EvidenceSourcePreparationStageInput(
        route_stage=route_stage,
        projection_input_refs=projection_input_refs,
        filter_job_coverage_refs=filter_job_coverage_refs,
        upstream=EvidenceSourcePreparationUpstreamReferences(
            block_manifest_path=artifacts["block_manifest_path"],
            doc_meta_bundle_path=artifacts["doc_meta_bundle_path"],
            analysis_bundle_path=artifacts["analysis_bundle_path"],
        ),
        context=EvidenceSourcePreparationStageContext(
            output_dir=tmp_path / "esp_out",
            run_id="projected_fan_in_prepare_e2e",
        ),
        execution_dependencies=ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
            llm_mode="mock",
        ),
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        selected_route_output=selected_route_output,
    )

    result = run_evidence_source_preparation_stage(
        stage_input=stage_input,
        stage_executor=INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
    )

    assessment_input_path = result.output_dir / "assessment_input.json"
    assessment_input = load_json(assessment_input_path)
    runtime_context = load_json(result.output_dir / ASSESSMENT_RUNTIME_CONTEXT_FILENAME)

    validate_assessment_input(assessment_input)

    assert "zone_key" not in assessment_input or not str(
        assessment_input.get("zone_key") or ""
    ).strip()
    assert "coverage_bundle_ref" not in (runtime_context.get("source_refs") or {})
    assert "coverage_bundle_id" not in assessment_input

    aggregate_units = aggregate_bundle.get("units") or []
    contributor_filter_job_ids = {
        ref.filter_job_id for ref in selection.projection_input_refs
    }
    for unit in aggregate_units:
        assert unit.get("filter_job_id") in contributor_filter_job_ids
        assert unit.get("source_zone_key")
        unit_id = unit["unit_id"]
        provenance = runtime_context["unit_provenance"][unit_id]
        assert provenance.get("filter_job_id") == unit.get("filter_job_id")
        assert provenance.get("source_zone_key") == unit.get("source_zone_key")

    expected_id = build_projected_fan_in_llm_input_bundle_id(
        file_hash=LINEAGE_FILE_HASH,
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        projection_input_refs=projection_refs,
        route="aggregate",
    )
    assert assessment_input["llm_input_bundle_id"] == expected_id

    reversed_refs = list(reversed(projection_refs))
    reversed_id = build_projected_fan_in_llm_input_bundle_id(
        file_hash=LINEAGE_FILE_HASH,
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        projection_input_refs=reversed_refs,
        route="aggregate",
    )
    assert reversed_id != expected_id

    other_hash_id = build_projected_fan_in_llm_input_bundle_id(
        file_hash="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        projection_input_refs=projection_refs,
        route="aggregate",
    )
    assert other_hash_id != expected_id
