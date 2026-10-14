"""Neutral projection fan-in and consumer selection tests."""

from __future__ import annotations

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
from operations.filter_output_projection.contracts import (
    CanonicalSourceRef,
    FilterOutputProjectionStepResult,
    ProjectedSource,
    SemanticProjectionOutcome,
)
from tests.projection_test_helpers import (
    assembled_projected_source,
    projected_sentence,
    raw_projected_source,
)
from artifacts.filter_output_projection_bundle import (
    build_filter_output_projection_bundle,
    build_filter_output_projection_bundle_id,
)
from operations.filter_output_projection.fan_in import (
    ProjectionFanInInput,
    build_projection_fan_in_inputs_from_bundles,
    select_projected_sources_for_semantic_module,
)

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


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
    projected_sources: tuple[ProjectedSource, ...],
    semantic_outcomes: tuple[SemanticProjectionOutcome, ...] = (),
) -> FilterOutputProjectionStepResult:
    return FilterOutputProjectionStepResult(
        filter_job_id=filter_job_id,
        doc_id="doc_test",
        file_hash=LINEAGE_FILE_HASH,
        zone_key="ib_overview_zh",
        projected_sources=projected_sources,
        semantic_outcomes=semantic_outcomes,
    )


def _fan_in_input(
    *,
    step_result: FilterOutputProjectionStepResult,
    run_id: str,
) -> ProjectionFanInInput:
    return ProjectionFanInInput(
        step_result=step_result,
        filter_output_projection_bundle_id=build_filter_output_projection_bundle_id(
            filter_job_id=step_result.filter_job_id,
            run_id=run_id,
        ),
    )


def test_fan_in_selects_clinical_safety_and_preserves_unselected_modules() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
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
            _projected_source(
                block_id="C0004",
                semantic_module_id="pharmacokinetics",
            ),
        ),
        semantic_outcomes=(
            SemanticProjectionOutcome(
                semantic_module_id="other",
                source_refs=(
                    CanonicalSourceRef(
                        refs={
                            "block_id": "C0099",
                            "source_group": "blocks",
                            "source_item_index": "1",
                            "char_start": "0",
                            "char_end": "1",
                        }
                    ),
                ),
            ),
        ),
    )

    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(
            _fan_in_input(step_result=direct, run_id="fan_in_direct"),
            _fan_in_input(step_result=overview, run_id="fan_in_overview"),
        ),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )

    selected_block_ids = [
        source.source_refs[0].refs["block_id"]
        for source in selection.selected_projected_sources
    ]
    assert selected_block_ids == ["C0001", "C0002"]
    unselected_modules = {
        source.semantic_module_id for source in selection.unselected_projected_sources
    }
    assert unselected_modules == {"efficacy", "pharmacokinetics"}
    assert overview.semantic_outcomes[0].semantic_module_id == "other"


def test_fan_in_does_not_deduplicate_same_block_same_module() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    direct = _projection_result(
        filter_job_id="ib_clinical_safety",
        projected_sources=(
            _projected_source(block_id="C0004", semantic_module_id="clinical_safety"),
        ),
    )
    overview = _projection_result(
        filter_job_id="ib_overview",
        projected_sources=(
            _projected_source(
                block_id="C0004",
                semantic_module_id="clinical_safety",
                representation="assembled",
            ),
        ),
    )
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(
            _fan_in_input(step_result=direct, run_id="fan_in_direct"),
            _fan_in_input(step_result=overview, run_id="fan_in_overview"),
        ),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    assert len(selection.selected_projected_sources) == 2
    assert selection.selected_projected_sources[0].sentences
    assert selection.selected_projected_sources[1].sentences


def test_fan_in_rejects_mismatched_doc_identity() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    first = _projection_result(
        filter_job_id="ib_clinical_safety",
        projected_sources=(
            _projected_source(block_id="C0001", semantic_module_id="clinical_safety"),
        ),
    )
    second = FilterOutputProjectionStepResult(
        filter_job_id="ib_overview",
        doc_id="doc_other",
        file_hash=LINEAGE_FILE_HASH,
        zone_key="ib_overview_zh",
        projected_sources=(),
    )
    with pytest.raises(ValueError, match="doc_id"):
        select_projected_sources_for_semantic_module(
            projection_fan_in_inputs=(
                _fan_in_input(step_result=first, run_id="fan_in_first"),
                _fan_in_input(step_result=second, run_id="fan_in_second"),
            ),
            semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
        )


def _persisted_bundle(
    *,
    step_result: FilterOutputProjectionStepResult,
    run_id: str,
    bundle_id_override: str | None = None,
) -> dict:
    bundle = build_filter_output_projection_bundle(
        step_result=step_result,
        run_id=run_id,
    )
    if bundle_id_override is not None:
        bundle = dict(bundle)
        bundle["filter_output_projection_bundle_id"] = bundle_id_override
    return bundle


def test_build_fan_in_inputs_from_persisted_bundles() -> None:
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
        ),
    )
    direct_bundle = _persisted_bundle(step_result=direct, run_id="persist_direct")
    overview_bundle = _persisted_bundle(step_result=overview, run_id="persist_overview")

    fan_in_inputs = build_projection_fan_in_inputs_from_bundles(
        (direct_bundle, overview_bundle)
    )

    assert len(fan_in_inputs) == 2
    assert fan_in_inputs[0].filter_output_projection_bundle_id == direct_bundle[
        "filter_output_projection_bundle_id"
    ]
    assert fan_in_inputs[0].step_result.filter_job_id == "ib_clinical_safety"
    assert fan_in_inputs[0].step_result.zone_key == "ib_overview_zh"
    assert len(fan_in_inputs[0].step_result.projected_sources) == 1
    assert fan_in_inputs[1].step_result.filter_job_id == "ib_overview"
    assert fan_in_inputs[1].step_result.zone_key == "ib_overview_zh"


def test_build_fan_in_inputs_use_persisted_bundle_id_not_recomputation() -> None:
    step_result = _projection_result(
        filter_job_id="ib_clinical_safety",
        projected_sources=(
            _projected_source(block_id="C0001", semantic_module_id="clinical_safety"),
        ),
    )
    authoritative_id = "filter_output_projection_authoritative_bundle_id"
    bundle = _persisted_bundle(
        step_result=step_result,
        run_id="would_produce_different_id",
        bundle_id_override=authoritative_id,
    )
    recomputed_id = build_filter_output_projection_bundle_id(
        filter_job_id=step_result.filter_job_id,
        run_id="would_produce_different_id",
    )
    assert authoritative_id != recomputed_id

    fan_in_input = build_projection_fan_in_inputs_from_bundles((bundle,))[0]
    assert fan_in_input.filter_output_projection_bundle_id == authoritative_id


def test_build_fan_in_selection_matches_manual_fan_in_inputs() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
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
    manual_selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=(
            _fan_in_input(step_result=direct, run_id="manual_direct"),
            _fan_in_input(step_result=overview, run_id="manual_overview"),
        ),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    bundle_selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=build_projection_fan_in_inputs_from_bundles(
            (
                _persisted_bundle(step_result=direct, run_id="manual_direct"),
                _persisted_bundle(step_result=overview, run_id="manual_overview"),
            )
        ),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )

    assert manual_selection.selected_projected_sources == (
        bundle_selection.selected_projected_sources
    )
    assert manual_selection.unselected_projected_sources == (
        bundle_selection.unselected_projected_sources
    )
    assert manual_selection.projection_input_refs == bundle_selection.projection_input_refs


def test_build_fan_in_non_contributing_bundle_has_no_projection_input_ref() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    contributing = _projection_result(
        filter_job_id="ib_clinical_safety",
        projected_sources=(
            _projected_source(block_id="C0001", semantic_module_id="clinical_safety"),
        ),
    )
    non_contributing = _projection_result(
        filter_job_id="ib_overview",
        projected_sources=(
            _projected_source(block_id="C0002", semantic_module_id="efficacy"),
        ),
    )
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=build_projection_fan_in_inputs_from_bundles(
            (
                _persisted_bundle(step_result=contributing, run_id="contrib"),
                _persisted_bundle(step_result=non_contributing, run_id="non_contrib"),
            )
        ),
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )

    assert len(selection.projection_input_refs) == 1
    assert selection.projection_input_refs[0].filter_job_id == "ib_clinical_safety"


def test_flow_route_fan_in_uses_runtime_persisted_projection_entry() -> None:
    flow_path = (
        BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "flow.py"
    )
    source = flow_path.read_text(encoding="utf-8")
    assert "run_projected_source_route_from_projection_bundles" in source
    assert "build_projection_fan_in_inputs_from_bundles" not in source
    assert "select_projected_sources_for_semantic_module" not in source
    assert "ProjectionFanInInput(" not in source
    assert "step_result=projection_stage_result.step_result" not in source
