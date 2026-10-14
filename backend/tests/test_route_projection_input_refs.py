"""Route artifact persistence of projection fan-in provenance."""

from __future__ import annotations

import json
import sys
from pathlib import Path

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
from artifacts.filter_output_projection_bundle import (
    build_filter_output_projection_bundle,
    build_filter_output_projection_bundle_id,
)
from artifacts.routing.schema import validate_route_routing_manifest, validate_routed_unit_bundle
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionStepResult,
    ProjectedSource,
)
from tests.projection_test_helpers import (
    assembled_projected_source,
    projected_sentence,
    raw_projected_source,
)
from operations.filter_output_projection.fan_in import (
    ProjectionFanInInput,
    select_projected_sources_for_semantic_module,
)
from steps.project_filter_output import run as run_project_filter_output
from steps.route import run_from_projected_sources
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from plugins.clinical_trial_doc.filter_profiles.ib.overview_zh import (
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)
from runtime.io import load_json
from runtime.projected_source_route_stage import run_projected_source_route_stage
from tests.route_test_fixtures import (
    LINEAGE_FILE_HASH,
    _minimal_doc_meta,
    _projection_fan_in_input_for_step_result,
    _projection_input_refs_dicts,
)
from tests.test_filter_output_projection_direct import (
    _filter_artifacts_for_profile,
    _projection_input_for_profile,
    _resolved_direct_job,
)

_SLOT_A_RUN = "filter_output_projection_slot_a_ib_clinical_safety"
_SLOT_B_RUN = "filter_output_projection_slot_b_ib_clinical_safety"


def _projected_source(
    *,
    block_id: str,
    semantic_module_id: str,
    representation: str = "raw",
) -> ProjectedSource:
    sentence = projected_sentence(
        sentence_id=f"{block_id}:S001",
        text="正文",
        source_block_id=block_id,
    )
    if representation == "assembled":
        return assembled_projected_source(
            semantic_module_id=semantic_module_id,
            sentences=(sentence,),
            heading_path=["摘要"],
        )
    return raw_projected_source(
        semantic_module_id=semantic_module_id,
        block_id=block_id,
        sentences=(sentence,),
        heading_path=["摘要"],
    )


def _projection_result(
    *,
    filter_job_id: str,
    zone_key: str,
    projected_sources: tuple[ProjectedSource, ...],
) -> FilterOutputProjectionStepResult:
    return FilterOutputProjectionStepResult(
        filter_job_id=filter_job_id,
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
        zone_key=zone_key,
        projected_sources=projected_sources,
        semantic_outcomes=(),
    )


def _fan_in_input(
    *,
    filter_job_id: str,
    zone_key: str,
    projected_sources: tuple[ProjectedSource, ...],
    run_id: str,
) -> ProjectionFanInInput:
    step_result = _projection_result(
        filter_job_id=filter_job_id,
        zone_key=zone_key,
        projected_sources=projected_sources,
    )
    return ProjectionFanInInput(
        step_result=step_result,
        filter_output_projection_bundle_id=build_filter_output_projection_bundle_id(
            filter_job_id=filter_job_id,
            run_id=run_id,
        ),
    )


def test_single_projection_bundle_contributes_one_ref() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    fan_in_input = _fan_in_input(
        filter_job_id="ib_clinical_safety",
        zone_key="ib_clinical_safety_zh",
        projected_sources=(
            _projected_source(block_id="C0001", semantic_module_id="clinical_safety"),
        ),
        run_id="projection_run_a",
    )
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(fan_in_input,),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    assert len(selection.projection_input_refs) == 1
    ref = selection.projection_input_refs[0]
    assert ref.filter_job_id == "ib_clinical_safety"
    assert ref.zone_key == "ib_clinical_safety_zh"
    assert ref.filter_output_projection_bundle_id == (
        "filter_output_projection_ib_clinical_safety_projection_run_a"
    )


def test_two_projection_bundles_contribute_refs_in_order() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    direct = _fan_in_input(
        filter_job_id="ib_clinical_safety",
        zone_key="ib_clinical_safety_zh",
        projected_sources=(
            _projected_source(block_id="C0001", semantic_module_id="clinical_safety"),
        ),
        run_id="projection_run_direct",
    )
    overview = _fan_in_input(
        filter_job_id="ib_overview",
        zone_key="ib_overview_zh",
        projected_sources=(
            _projected_source(
                block_id="C0002",
                semantic_module_id="clinical_safety",
                representation="assembled",
            ),
            _projected_source(block_id="C0003", semantic_module_id="efficacy"),
        ),
        run_id="projection_run_overview",
    )
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(direct, overview),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    assert [ref.filter_job_id for ref in selection.projection_input_refs] == [
        "ib_clinical_safety",
        "ib_overview",
    ]


def test_non_contributing_projection_bundle_is_excluded() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    direct = _fan_in_input(
        filter_job_id="ib_clinical_safety",
        zone_key="ib_clinical_safety_zh",
        projected_sources=(
            _projected_source(block_id="C0001", semantic_module_id="clinical_safety"),
        ),
        run_id="projection_run_direct",
    )
    overview = _fan_in_input(
        filter_job_id="ib_overview",
        zone_key="ib_overview_zh",
        projected_sources=(
            _projected_source(block_id="C0003", semantic_module_id="efficacy"),
        ),
        run_id="projection_run_overview",
    )
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(direct, overview),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    assert len(selection.projection_input_refs) == 1
    assert selection.projection_input_refs[0].filter_job_id == "ib_clinical_safety"


def test_duplicate_bundle_id_in_fan_in_inputs_raises() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    duplicate = _fan_in_input(
        filter_job_id="ib_clinical_safety",
        zone_key="ib_clinical_safety_zh",
        projected_sources=(
            _projected_source(block_id="C0001", semantic_module_id="clinical_safety"),
        ),
        run_id="projection_run_duplicate",
    )
    with pytest.raises(ValueError, match="duplicate filter_output_projection_bundle_id"):
        select_projected_sources_for_semantic_module(
            projection_fan_in_inputs=(duplicate, duplicate),
            semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
        )


def test_persisted_route_artifact_projection_refs_match_upstream_bundle_ids(
    tmp_path: Path,
) -> None:
    profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    zone_match_bundle, _, block_manifest, analysis_bundle = _filter_artifacts_for_profile(profile)
    projection_input = _projection_input_for_profile(profile, zone_match_bundle)
    step_result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=analysis_bundle,
        job=_resolved_direct_job(profile),
        facade=DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
    )
    bundle = build_filter_output_projection_bundle(
        step_result=step_result,
        run_id="projection_runtime_test",
    )
    fan_in_input = ProjectionFanInInput(
        step_result=step_result,
        filter_output_projection_bundle_id=str(
            bundle["filter_output_projection_bundle_id"]
        ),
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(fan_in_input,),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
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
        output_dir=tmp_path / "route",
        run_id="route_runtime_test",
        route_executor=composition.projected_source_route_executor,
    )
    aggregate_bundle = load_json(route_result.routed_bundle_paths["aggregate"])
    manifest = load_json(route_result.routing_manifest_path)
    run_summary = load_json(route_result.run_summary_path)
    expected_refs = [ref.to_dict() for ref in selection.projection_input_refs]
    assert aggregate_bundle["source_refs"]["projection_input_refs"] == expected_refs
    assert manifest["source_refs"]["projection_input_refs"] == expected_refs
    assert aggregate_bundle["source_refs"]["route_input_id"] == (
        "projected_route_clinical_safety"
    )
    assert run_summary["inputs"]["projection_input_refs"] == expected_refs
    validate_routed_unit_bundle(aggregate_bundle, expected_route="aggregate")
    validate_route_routing_manifest(manifest)


def test_multi_slot_projection_bundle_identities_do_not_collide() -> None:
    slot_a = _fan_in_input(
        filter_job_id="ib_clinical_safety",
        zone_key="ib_clinical_safety_zh",
        projected_sources=(
            _projected_source(block_id="C0001", semantic_module_id="clinical_safety"),
        ),
        run_id=_SLOT_A_RUN,
    )
    slot_b = _fan_in_input(
        filter_job_id="ib_clinical_safety",
        zone_key="ib_clinical_safety_zh",
        projected_sources=(
            _projected_source(block_id="C0002", semantic_module_id="clinical_safety"),
        ),
        run_id=_SLOT_B_RUN,
    )
    assert (
        slot_a.filter_output_projection_bundle_id
        != slot_b.filter_output_projection_bundle_id
    )


def test_route_step_rejects_projected_route_without_projection_input_refs() -> None:
    profile = IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH
    zone_match_bundle, _, block_manifest, analysis_bundle = _filter_artifacts_for_profile(profile)
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
    with pytest.raises(ValueError, match="projection_input_refs are required"):
        run_from_projected_sources(
            projected_sources=selection.selected_projected_sources,
            block_manifest=block_manifest,
            doc_meta_bundle=_minimal_doc_meta(doc_id=projection_input.doc_id),
            analysis_bundle={
                "analysis_bundle_id": "prepare_analysis_test",
                "doc_id": projection_input.doc_id,
                "file_hash": projection_input.file_hash,
            },
            expected_semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            route_executor=composition.projected_source_route_executor,
        )
