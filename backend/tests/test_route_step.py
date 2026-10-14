"""Canonical route step: pure orchestration and import boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from artifacts.routing.schema import ROUTED_UNITS_ROUTE_FILENAMES
from artifacts.routing.types import ROUTES, RoutedUnitSet
from operations.filter_output_projection.fan_in import (
    select_projected_sources_for_semantic_module,
)
from steps.project_filter_output import run as run_project_filter_output
from steps.route import RouteStepResult, run_from_projected_sources
from plugins.clinical_trial_doc.filter_output_projection import (
    DIRECT_FILTER_OUTPUT_PROJECTION_FACADE,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from tests.test_filter_output_projection_direct import (
    _filter_artifacts_for_profile,
    _projection_input_for_profile,
    _resolved_direct_job,
)
from tests.route_test_fixtures import (
    _analysis_bundle_for_manifest,
    _minimal_doc_meta,
    _projection_fan_in_input_for_step_result,
    _projection_input_refs_dicts,
)

ROUTE_STEP_FORBIDDEN_IMPORT_MODULES = (
    "runtime",
    "runtime.io",
    "runtime.projected_source_route_stage",
    "scripts.stage_runners",
    "scripts.dev",
    "plugins.clinical_trial_doc",
)

ROUTE_STEP_FORBIDDEN_IMPORT_PREFIXES = (
    "runtime.",
    "scripts.stage_runners.",
    "scripts.dev.",
    "plugins.clinical_trial_doc.",
)

ROUTE_STEP_FORBIDDEN_CALLS = (
    "save_json",
    "load_json",
    "mkdir",
    "write_text",
    "read_text",
    "open",
)


def _neutral_routed_unit_set() -> RoutedUnitSet:
    unit = {
        "unit_id": "TU0001",
        "unit_kind": "text_unit",
        "route": "aggregate",
        "route_basis": "neutral_test",
    }
    units_by_route = {route: ([] if route != "aggregate" else [unit]) for route in ROUTES}
    route_counts = {
        f"{route}_unit_count": len(units_by_route[route]) for route in ROUTES
    }
    route_counts["total_routed_unit_count"] = sum(
        route_counts[f"{route}_unit_count"] for route in ROUTES
    )
    return RoutedUnitSet(
        units_by_route=units_by_route,
        route_counts=route_counts,
        all_units=tuple(units_by_route["aggregate"]),
    )


def _recording_route_executor(calls: list[dict[str, Any]]):
    def executor(**kwargs: Any) -> RoutedUnitSet:
        calls.append(kwargs)
        return _neutral_routed_unit_set()

    return executor


def _canonical_route_inputs() -> dict[str, Any]:
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
    projected_sources = selection.selected_projected_sources
    doc_id = str(block_manifest.get("doc_id") or projection_input.doc_id)
    return {
        "projected_sources": projected_sources,
        "projection_input_refs": _projection_input_refs_dicts(selection),
        "projection_doc_id": step_result.doc_id,
        "projection_file_hash": step_result.file_hash,
        "block_manifest": block_manifest,
        "doc_meta_bundle": _minimal_doc_meta(doc_id=doc_id),
        "analysis_bundle": _analysis_bundle_for_manifest(block_manifest),
        "expected_semantic_module_id": CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        "route_executor": composition.projected_source_route_executor,
    }


def test_route_step_returns_identity_and_route_artifacts() -> None:
    inputs = _canonical_route_inputs()
    result = run_from_projected_sources(**inputs)

    assert isinstance(result, RouteStepResult)
    assert result.doc_id == inputs["block_manifest"]["doc_id"]
    assert result.zone_key == ""
    assert "routed_bundles" in result.route_artifacts
    assert "routing_manifest" in result.route_artifacts
    assert "route_counts" in result.route_artifacts
    assert "units_by_route" in result.route_artifacts


def test_route_step_returns_four_routed_bundles_and_manifest() -> None:
    result = run_from_projected_sources(**_canonical_route_inputs())
    artifacts = result.route_artifacts

    for route in ROUTED_UNITS_ROUTE_FILENAMES:
        bundle = artifacts["routed_bundles"][route]
        assert bundle["route"] == route
    manifest = artifacts["routing_manifest"]
    assert manifest["route_counts"]["aggregate"] >= 1


def test_route_step_invokes_injected_route_executor_once() -> None:
    calls: list[dict[str, Any]] = []
    inputs = _canonical_route_inputs()
    inputs["route_executor"] = _recording_route_executor(calls)
    run_from_projected_sources(**inputs)
    assert len(calls) == 1
    assert calls[0]["projected_sources"] == inputs["projected_sources"]
    assert calls[0]["block_manifest"] is inputs["block_manifest"]
    assert calls[0]["analysis_bundle"] is inputs["analysis_bundle"]
    assert (
        calls[0]["expected_semantic_module_id"]
        == inputs["expected_semantic_module_id"]
    )
    assert calls[0]["doc_id"] == inputs["block_manifest"]["doc_id"]
    assert calls[0]["file_hash"] == inputs["block_manifest"]["file_hash"]


def test_route_step_has_no_legacy_coverage_entry() -> None:
    source = (BACKEND_ROOT / "steps" / "route.py").read_text(
        encoding="utf-8"
    )
    assert "def run(" not in source or "def run_from_projected_sources(" in source
    assert "overview_decompose_bundle" not in source
    assert "route_tag_prepare_units" not in source


def _route_step_module_ast() -> ast.Module:
    source_path = BACKEND_ROOT / "steps" / "route.py"
    return ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_route_step_has_no_runtime_or_runner_imports() -> None:
    imported = _imported_module_names(_route_step_module_ast())
    for module_name in ROUTE_STEP_FORBIDDEN_IMPORT_MODULES:
        assert module_name not in imported
    for imported_name in imported:
        assert not any(
            imported_name == prefix.rstrip(".") or imported_name.startswith(prefix)
            for prefix in ROUTE_STEP_FORBIDDEN_IMPORT_PREFIXES
        )


def test_route_step_has_no_file_io_calls() -> None:
    tree = _route_step_module_ast()
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in ROUTE_STEP_FORBIDDEN_CALLS:
            offenders.append(name)
    assert not offenders, f"forbidden IO calls in route.py: {offenders}"
