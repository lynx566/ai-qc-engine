"""Guardrails: canonical execution packages must not import legacy Route/Overview paths."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

CANONICAL_EXECUTION_FILES = (
    BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "flow.py",
    BACKEND_ROOT / "runtime" / "filter_output_projection_stage.py",
    BACKEND_ROOT / "runtime" / "projected_source_route_stage.py",
    BACKEND_ROOT / "steps" / "route.py",
    BACKEND_ROOT / "scripts" / "run_consistency_qc.py",
    BACKEND_ROOT / "scripts" / "stage_runners" / "filter_output_projection_runner.py",
    BACKEND_ROOT / "scripts" / "stage_runners" / "route_runner.py",
)

FORBIDDEN_LEGACY_TOKENS = (
    "overview_decompose_mock_runner",
    "overview_decompose_bundle",
    "runtime.route_stage",
    "run_route_stage",
)

CANONICAL_ROUTE_RUNNER_FORBIDDEN_TOKENS = (
    "runtime.route_stage",
    "run_route_stage",
    "coverage_bundle",
    "persist_route_artifacts_from_coverage",
    "route_tag_prepare_units",
    "build_projection_fan_in_inputs_from_bundles",
    "select_projected_sources_for_semantic_module",
    "run_projected_source_route_stage",
)


def _import_and_call_names(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.add(func.id)
            elif isinstance(func, ast.Attribute):
                calls.add(func.attr)
    return imports, calls


def test_canonical_execution_modules_avoid_legacy_route_and_overview_symbols() -> None:
    violations: list[str] = []
    for path in CANONICAL_EXECUTION_FILES:
        assert path.is_file(), f"missing canonical execution file: {path}"
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_LEGACY_TOKENS:
            if token in source:
                violations.append(f"{path.relative_to(BACKEND_ROOT)} contains {token!r}")
    assert not violations, "legacy references in canonical execution:\n" + "\n".join(violations)


def test_pipeline_route_step_has_single_projected_source_entry() -> None:
    route_path = BACKEND_ROOT / "steps" / "route.py"
    source = route_path.read_text(encoding="utf-8")
    assert "def run_from_projected_sources(" in source
    assert "def run(" not in source.replace("def run_from_projected_sources(", "")
    assert "route_tag_prepare_units" not in source
    assert "overview_decompose" not in source


def test_canonical_route_runner_avoids_legacy_coverage_route_symbols() -> None:
    route_runner_path = (
        BACKEND_ROOT / "scripts" / "stage_runners" / "route_runner.py"
    )
    source = route_runner_path.read_text(encoding="utf-8")
    violations = [
        f"route_runner.py contains {token!r}"
        for token in CANONICAL_ROUTE_RUNNER_FORBIDDEN_TOKENS
        if token in source
    ]
    assert not violations, "legacy coverage-route references in canonical runner:\n" + (
        "\n".join(violations)
    )
    assert "run_projected_source_route_from_projection_bundles" in source
    assert "build_projection_fan_in_inputs_from_bundles" not in source
    assert "run_projected_source_route_stage" not in source


def test_flow_uses_runtime_persisted_projection_route_entry() -> None:
    flow_path = BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "flow.py"
    source = flow_path.read_text(encoding="utf-8")
    assert "run_projected_source_route_from_projection_bundles" in source
    assert "build_projection_fan_in_inputs_from_bundles" not in source
    assert "select_projected_sources_for_semantic_module" not in source


def test_runtime_persisted_projection_entry_owns_fan_in_orchestration() -> None:
    runtime_path = BACKEND_ROOT / "runtime" / "projected_source_route_stage.py"
    source = runtime_path.read_text(encoding="utf-8")
    assert "run_projected_source_route_from_projection_bundles" in source
    assert "build_projection_fan_in_inputs_from_bundles" in source
    assert "select_projected_sources_for_semantic_module" in source
    assert "run_projected_source_route_stage" in source


def test_runtime_persisted_projection_entry_owns_fan_in_orchestration() -> None:
    runtime_path = BACKEND_ROOT / "runtime" / "projected_source_route_stage.py"
    source = runtime_path.read_text(encoding="utf-8")
    assert "run_projected_source_route_from_projection_bundles" in source
    assert "build_projection_fan_in_inputs_from_bundles" in source
    assert "select_projected_sources_for_semantic_module" in source
    assert "run_projected_source_route_stage" in source
