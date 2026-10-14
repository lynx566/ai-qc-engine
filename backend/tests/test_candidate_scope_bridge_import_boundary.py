"""Import boundary guards for candidate-scope bridge."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

BRIDGE_ROOT = BACKEND_ROOT / "bridge" / "candidate_scope"

RETIRED_BRIDGE_MODULES = (
    "execution_input.py",
    "route_handoff.py",
    "projection_resolver.py",
    "artifact_paths.py",
    "installed_filter_jobs.py",
)

FORBIDDEN_BRIDGE_IMPORTS = ("runtime.filter_output_projection_stage",)

PRODUCTION_BRIDGE_MODULES = (
    "app.py",
    "bridge_runtime.py",
    "canonical_context.py",
    "errors.py",
    "next_service.py",
    "routes.py",
    "schemas.py",
    "selection_ops.py",
    "selection_view.py",
    "state_service.py",
)


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_retired_candidate_scope_bridge_modules_removed() -> None:
    for module_name in RETIRED_BRIDGE_MODULES:
        assert not (BRIDGE_ROOT / module_name).exists(), module_name


def test_candidate_scope_bridge_production_modules_do_not_import_projection_stage() -> (
    None
):
    violations: list[str] = []
    for module_name in PRODUCTION_BRIDGE_MODULES:
        path = BRIDGE_ROOT / module_name
        assert path.is_file(), module_name
        imported = _imported_module_names(_parse(path))
        for forbidden in FORBIDDEN_BRIDGE_IMPORTS:
            if forbidden in imported:
                violations.append(f"{module_name} imports {forbidden}")
    assert not violations, "\n".join(violations)


def test_all_bridge_modules_do_not_import_runner_tooling() -> None:
    violations: list[str] = []
    for path in sorted((BACKEND_ROOT / "bridge").rglob("*.py")):
        for module in _imported_module_names(_parse(path)):
            if module in {
                "scripts.stage_runners",
                "experiments.scripts.stage_runners",
                "backend.scripts.stage_runners",
            } or module.startswith(
                (
                    "scripts.stage_runners.",
                    "experiments.scripts.stage_runners.",
                    "backend.scripts.stage_runners.",
                )
            ):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} imports {module}"
                )
    assert not violations, "\n".join(violations)
