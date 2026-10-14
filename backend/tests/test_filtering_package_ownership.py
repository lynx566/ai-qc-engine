"""Import boundary guards for filtering package ownership (PR C2)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

OLD_FILTERING_ROOT = BACKEND_ROOT / "pipeline" / "filtering"
CORE_FILTERING_ROOT = BACKEND_ROOT / "core" / "filtering"
FILTER_STEP_PATH = BACKEND_ROOT / "steps" / "filter.py"
RUN_SUMMARIES_PATH = BACKEND_ROOT / "runtime" / "run_summaries.py"

FORBIDDEN_OLD_FILTERING_IMPORT = "pipeline.filtering"

CORE_FILTERING_FORBIDDEN_IMPORT_PREFIXES = (
    "pipeline",
    "runtime",
    "scripts",
    "plugins.clinical_trial_doc",
)

PRODUCTION_SCAN_ROOTS = (
    BACKEND_ROOT / "steps",
    BACKEND_ROOT / "core",
    BACKEND_ROOT / "runtime",
    BACKEND_ROOT / "scripts",
    BACKEND_ROOT / "plugins",
)

EXPECTED_CORE_FILTERING_FILES = (
    "__init__.py",
    "block_universe.py",
    "strategies.py",
    "registry.py",
    "heading_zone.py",
    "jobs.py",
    "profiles.py",
)


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _iter_py_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
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


def _function_local_imports(path: Path, function_name: str) -> set[str]:
    tree = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            names: set[str] = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Import):
                    for alias in child.names:
                        names.add(alias.name)
                elif isinstance(child, ast.ImportFrom) and child.module:
                    names.add(child.module)
            return names
    return set()


def test_pipeline_filtering_package_is_removed() -> None:
    assert not OLD_FILTERING_ROOT.exists(), (
        f"filtering package must not live under pipeline/: {OLD_FILTERING_ROOT}"
    )


def test_core_filtering_package_exists_with_expected_files() -> None:
    assert CORE_FILTERING_ROOT.is_dir(), (
        f"filtering package must exist at {CORE_FILTERING_ROOT}"
    )
    present = {path.name for path in CORE_FILTERING_ROOT.iterdir() if path.is_file()}
    missing = set(EXPECTED_CORE_FILTERING_FILES) - present
    assert not missing, f"missing core/filtering files: {sorted(missing)}"


def test_production_code_does_not_import_pipeline_filtering() -> None:
    violations: list[str] = []
    for root in PRODUCTION_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in _iter_py_files(root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/__pycache__/" in rel:
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                if imported == FORBIDDEN_OLD_FILTERING_IMPORT or imported.startswith(
                    f"{FORBIDDEN_OLD_FILTERING_IMPORT}."
                ):
                    violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_core_filtering_modules_avoid_forbidden_packages() -> None:
    violations: list[str] = []
    for path in _iter_py_files(CORE_FILTERING_ROOT):
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        tree = _parse(path)
        for imported in _imported_module_names(tree):
            for prefix in CORE_FILTERING_FORBIDDEN_IMPORT_PREFIXES:
                if imported == prefix or imported.startswith(f"{prefix}."):
                    violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_filter_step_imports_core_filtering_not_pipeline_filtering() -> None:
    tree = _parse(FILTER_STEP_PATH)
    imported = _imported_module_names(tree)
    assert any(
        name == "core.filtering" or name.startswith("core.filtering.")
        for name in imported
    ), "filter step must import core.filtering"
    violations = [
        name
        for name in imported
        if name == FORBIDDEN_OLD_FILTERING_IMPORT
        or name.startswith(f"{FORBIDDEN_OLD_FILTERING_IMPORT}.")
    ]
    assert not violations, f"filter step must not import pipeline.filtering: {violations}"


def test_run_summaries_fallback_imports_core_filtering() -> None:
    tree = _parse(RUN_SUMMARIES_PATH)
    imported = _imported_module_names(tree)
    violations = [
        name
        for name in imported
        if name == FORBIDDEN_OLD_FILTERING_IMPORT
        or name.startswith(f"{FORBIDDEN_OLD_FILTERING_IMPORT}.")
    ]
    assert not violations, (
        "run_summaries must not import pipeline.filtering at module level"
    )

    fallback_imports = _function_local_imports(
        RUN_SUMMARIES_PATH,
        "_resolved_filter_strategy_id_for_summary",
    )
    assert "core.filtering.profiles" in fallback_imports
    assert "core.filtering.registry" in fallback_imports
    assert not any(
        name == FORBIDDEN_OLD_FILTERING_IMPORT
        or name.startswith(f"{FORBIDDEN_OLD_FILTERING_IMPORT}.")
        for name in fallback_imports
    )
