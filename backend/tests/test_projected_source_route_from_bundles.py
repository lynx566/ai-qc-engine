"""Runtime tests for persisted-projection Route orchestration."""

from __future__ import annotations

import ast
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
from operations.filter_output_projection.fan_in import (
    build_projection_fan_in_inputs_from_bundles,
    select_projected_sources_for_semantic_module,
)
from runtime.projected_source_route_stage import (
    ProjectedSourceRouteStageResult,
    load_persisted_projection_bundles,
    run_projected_source_route_from_projection_bundles,
    run_projected_source_route_stage,
)
from tests.test_projection_fan_in import (
    _persisted_bundle,
    _projected_source,
    _projection_result,
)
from tests.test_route_runner import _write_projection_bundle, _write_upstream_artifacts

RUNTIME_PATH = BACKEND_ROOT / "runtime" / "projected_source_route_stage.py"


def test_runtime_loads_and_validates_persisted_projection_bundles(
    tmp_path: Path,
) -> None:
    bundle_path = _write_projection_bundle(
        tmp_path,
        filter_job_id="ib_clinical_safety",
        block_id="C0001",
        run_id="runtime_load_test",
    )
    bundles = load_persisted_projection_bundles([bundle_path])
    fan_in_inputs = build_projection_fan_in_inputs_from_bundles(bundles)
    assert fan_in_inputs[0].filter_output_projection_bundle_id == bundles[0][
        "filter_output_projection_bundle_id"
    ]


def test_runtime_entry_uses_fan_in_builder_and_selection(
    tmp_path: Path,
) -> None:
    upstream = _write_upstream_artifacts(tmp_path)
    bundle_path = _write_projection_bundle(
        tmp_path,
        filter_job_id="ib_clinical_safety",
        block_id="C0001",
        run_id="runtime_fan_in_test",
    )
    composition = build_installed_document_consistency_qc_application_composition()
    captured: dict[str, object] = {}

    def _capture_stage(**kwargs: object) -> ProjectedSourceRouteStageResult:
        captured.update(kwargs)
        return ProjectedSourceRouteStageResult(
            output_dir=tmp_path / "route_out",
            run_id="runtime_fan_in_test",
            doc_id="doc_test",
            semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            route_counts={"total_routed_unit_count": 1},
            routed_bundle_paths={
                "aggregate": tmp_path / "route_out" / "routed_units_aggregate.json",
                "table": tmp_path / "route_out" / "routed_units_table.json",
                "case": tmp_path / "route_out" / "routed_units_case.json",
                "unknown": tmp_path / "route_out" / "routed_units_unknown.json",
            },
            routing_manifest_path=tmp_path / "route_out" / "routing_manifest.json",
            run_summary_path=tmp_path / "route_out" / "run_summary.json",
        )

    with (
        patch(
            "runtime.projected_source_route_stage.build_projection_fan_in_inputs_from_bundles",
            wraps=build_projection_fan_in_inputs_from_bundles,
        ) as mock_fan_in,
        patch(
            "runtime.projected_source_route_stage.select_projected_sources_for_semantic_module",
            wraps=select_projected_sources_for_semantic_module,
        ) as mock_select,
        patch(
            "runtime.projected_source_route_stage.run_projected_source_route_stage",
            side_effect=_capture_stage,
        ),
    ):
        outcome = run_projected_source_route_from_projection_bundles(
            projection_bundle_paths=[bundle_path],
            semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
            block_manifest_path=upstream["block_manifest"],
            doc_meta_bundle_path=upstream["doc_meta_bundle"],
            analysis_bundle_path=upstream["analysis_bundle"],
            route_executor=composition.projected_source_route_executor,
            output_dir=tmp_path / "route_out",
            run_id="runtime_fan_in_test",
        )

    assert mock_fan_in.called
    assert mock_select.called
    assert outcome.route_result is not None
    assert outcome.selected_projected_source_count == 1
    assert captured["route_executor"] is composition.projected_source_route_executor


def test_runtime_entry_projection_refs_match_slice1_semantics() -> None:
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
        _persisted_bundle(step_result=direct, run_id="runtime_ref_direct"),
        _persisted_bundle(step_result=overview, run_id="runtime_ref_overview"),
    )
    fan_in_inputs = build_projection_fan_in_inputs_from_bundles(bundles)
    selection = select_projected_sources_for_semantic_module(
        projection_fan_in_inputs=fan_in_inputs,
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
    )
    assert selection.projection_input_refs
    assert {ref.filter_job_id for ref in selection.projection_input_refs} == {
        "ib_clinical_safety",
        "ib_overview",
    }


def test_runtime_entry_has_no_application_imports() -> None:
    tree = ast.parse(RUNTIME_PATH.read_text(encoding="utf-8"), filename=str(RUNTIME_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(module.startswith("application.") for module in imported)


def test_runtime_entry_delegates_to_lower_stage_not_step(
    tmp_path: Path,
) -> None:
    upstream = _write_upstream_artifacts(tmp_path)
    bundle_path = _write_projection_bundle(
        tmp_path,
        filter_job_id="ib_clinical_safety",
        block_id="C0001",
        run_id="runtime_delegate_test",
    )
    composition = build_installed_document_consistency_qc_application_composition()
    stage_result = ProjectedSourceRouteStageResult(
        output_dir=tmp_path / "route_out",
        run_id="runtime_delegate_test",
        doc_id="doc_test",
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        route_counts={"total_routed_unit_count": 1},
        routed_bundle_paths={
            "aggregate": tmp_path / "route_out" / "routed_units_aggregate.json",
            "table": tmp_path / "route_out" / "routed_units_table.json",
            "case": tmp_path / "route_out" / "routed_units_case.json",
            "unknown": tmp_path / "route_out" / "routed_units_unknown.json",
        },
        routing_manifest_path=tmp_path / "route_out" / "routing_manifest.json",
        run_summary_path=tmp_path / "route_out" / "run_summary.json",
    )

    with patch(
        "runtime.projected_source_route_stage.run_projected_source_route_stage",
        return_value=stage_result,
    ) as mock_stage:
        outcome = run_projected_source_route_from_projection_bundles(
            projection_bundle_paths=[bundle_path],
            semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
            block_manifest_path=upstream["block_manifest"],
            doc_meta_bundle_path=upstream["doc_meta_bundle"],
            analysis_bundle_path=upstream["analysis_bundle"],
            route_executor=composition.projected_source_route_executor,
            output_dir=tmp_path / "route_out",
            run_id="runtime_delegate_test",
        )

    assert mock_stage.called
    assert outcome.route_result is stage_result


def test_runtime_entry_rejects_mixed_document_projection_and_static_upstream(
    tmp_path: Path,
) -> None:
    upstream = _write_upstream_artifacts(tmp_path, doc_id="doc_b")
    bundle_path = _write_projection_bundle(
        tmp_path,
        filter_job_id="ib_clinical_safety",
        block_id="C0001",
        run_id="mixed_document_test",
    )
    composition = build_installed_document_consistency_qc_application_composition()
    route_out = tmp_path / "route_out"

    with pytest.raises(
        ValueError,
        match="doc_id mismatch between projection fan-in and static upstream",
    ):
        run_projected_source_route_from_projection_bundles(
            projection_bundle_paths=[bundle_path],
            semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            enabled_route_semantic_module_ids=composition.enabled_route_semantic_module_ids(),
            block_manifest_path=upstream["block_manifest"],
            doc_meta_bundle_path=upstream["doc_meta_bundle"],
            analysis_bundle_path=upstream["analysis_bundle"],
            route_executor=composition.projected_source_route_executor,
            output_dir=route_out,
            run_id="mixed_document_test",
        )

    assert not (route_out / "routed_units_aggregate.json").exists()
