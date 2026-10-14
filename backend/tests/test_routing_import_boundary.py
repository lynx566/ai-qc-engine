"""Import boundary guards for routing processor ownership migration."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

ARTIFACTS_ROOT = BACKEND_ROOT / "artifacts"
PLUGIN_ROUTING_ROOT = BACKEND_ROOT / "plugins" / "clinical_trial_doc" / "routing"
REMOVED_ARTIFACT_MODULES = (
    ARTIFACTS_ROOT / "tag_prepare_routing.py",
    ARTIFACTS_ROOT / "routing" / "route_units.py",
)

FORBIDDEN_ARTIFACT_IMPORT_PREFIXES = (
    "plugins.clinical_trial_doc.routing",
    "plugins.clinical_trial_doc.routing.",
)

FORBIDDEN_PLUGIN_IMPORT_PREFIXES = (
    "runtime",
    "runtime.",
    "scripts.stage_runners",
    "scripts.stage_runners.",
    "scripts.dev",
    "scripts.dev.",
)

FORBIDDEN_ARTIFACT_ROUTING_SYMBOLS = frozenset(
    {
        "TABLE_TERMS",
        "CASE_TERMS",
        "AGGREGATE_TERMS",
        "infer_route_from_heading",
        "route_tag_prepare_units",
    }
)


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def _defined_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def test_removed_artifact_routing_modules_absent() -> None:
    for path in REMOVED_ARTIFACT_MODULES:
        assert not path.exists(), f"removed module still present: {path}"


def test_artifact_modules_do_not_import_plugin_routing() -> None:
    violations: list[str] = []
    for path in _iter_py_files(ARTIFACTS_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_module_names(tree):
            if any(
                imported == prefix.rstrip(".")
                or imported.startswith(prefix)
                for prefix in FORBIDDEN_ARTIFACT_IMPORT_PREFIXES
            ):
                violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_artifact_routing_modules_do_not_define_route_business_symbols() -> None:
    routing_dir = ARTIFACTS_ROOT / "routing"
    violations: list[str] = []
    for path in _iter_py_files(routing_dir):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defined = _defined_names(tree)
        overlap = sorted(defined & FORBIDDEN_ARTIFACT_ROUTING_SYMBOLS)
        if overlap:
            violations.append(
                f"{path.relative_to(BACKEND_ROOT)} defines forbidden symbols: {overlap}"
            )
    assert not violations, "\n".join(violations)


def test_plugin_routing_modules_do_not_import_runtime_or_runner() -> None:
    violations: list[str] = []
    for path in _iter_py_files(PLUGIN_ROUTING_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_module_names(tree):
            if any(
                imported == prefix.rstrip(".") or imported.startswith(prefix)
                for prefix in FORBIDDEN_PLUGIN_IMPORT_PREFIXES
            ):
                violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_plugin_routing_processor_has_no_file_io_symbols() -> None:
    processor_path = PLUGIN_ROUTING_ROOT / "processor.py"
    source = processor_path.read_text(encoding="utf-8")
    for forbidden in ("load_json", "save_json", "mkdir", "write_text", "open("):
        assert forbidden not in source, f"processor.py must not use {forbidden!r}"
