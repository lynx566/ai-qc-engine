"""Import boundary guards for filter step injection (PR C1)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

FILTER_STEP_PATH = BACKEND_ROOT / "steps" / "filter.py"
FILTER_STAGE_PATH = BACKEND_ROOT / "runtime" / "filter_stage.py"
JOBS_PATH = BACKEND_ROOT / "core" / "filtering" / "jobs.py"
PROFILES_PATH = BACKEND_ROOT / "core" / "filtering" / "profiles.py"
ZONE_REGISTRY_PATH = BACKEND_ROOT / "runtime" / "zone_registry.py"

INSTALLED_FILTER_CONFIG_IDS = frozenset(
    {
        "ib_clinical_safety_zh",
        "ib_overview_zh",
        "dsur_clinical_safety_zh",
        "dsur_overview_zh",
        "csr_clinical_safety_zh",
        "csr_overview_zh",
    }
)

FILTER_PROFILE_PLUGIN_PREFIX = "plugins.clinical_trial_doc.filter_profiles"

FILTER_STEP_FORBIDDEN_IMPORT_PREFIXES = (
    "runtime",
)

FILTER_STEP_FORBIDDEN_IMPORTS = frozenset(
    {
        "resolve_filter_strategy_for_config",
    }
)

JOBS_PROFILES_FORBIDDEN_IMPORT_PREFIXES = (
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

OLD_NORMALIZE_IMPORT = "runtime.zone_registry.normalize_filter_profiles"


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


def _imported_names_from_module(tree: ast.AST, module: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            for alias in node.names:
                names.add(alias.name)
    return names


def _defined_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            names.add(node.name)
    return names


def test_filter_stage_does_not_import_scripts() -> None:
    tree = _parse(FILTER_STAGE_PATH)
    imported = _imported_module_names(tree)
    violations = [
        name
        for name in imported
        if name == "scripts" or name.startswith("scripts.")
    ]
    assert not violations, f"filter_stage.py imports scripts: {violations}"


def test_filter_step_does_not_define_dead_run_wrapper() -> None:
    source = FILTER_STEP_PATH.read_text(encoding="utf-8")
    tree = _parse(FILTER_STEP_PATH)
    assert "run" not in _defined_names(tree)
    assert "\ndef run(" not in source


def test_filter_step_does_not_import_runtime_or_strategy_resolver() -> None:
    tree = _parse(FILTER_STEP_PATH)
    imported = _imported_module_names(tree)
    violations: list[str] = []
    for name in imported:
        for prefix in FILTER_STEP_FORBIDDEN_IMPORT_PREFIXES:
            if name == prefix or name.startswith(f"{prefix}."):
                violations.append(f"filter.py imports {name}")
    from_registry = _imported_names_from_module(tree, "core.filtering.registry")
    overlap = from_registry & FILTER_STEP_FORBIDDEN_IMPORTS
    if overlap:
        violations.append(f"filter.py imports from registry: {sorted(overlap)}")
    assert not violations, "\n".join(violations)


def test_filter_jobs_and_profiles_avoid_forbidden_packages() -> None:
    violations: list[str] = []
    for path in (JOBS_PATH, PROFILES_PATH):
        tree = _parse(path)
        for imported in _imported_module_names(tree):
            for prefix in JOBS_PROFILES_FORBIDDEN_IMPORT_PREFIXES:
                if imported == prefix or imported.startswith(f"{prefix}."):
                    rel = path.relative_to(BACKEND_ROOT).as_posix()
                    violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_zone_registry_no_longer_defines_normalize_filter_profiles() -> None:
    tree = _parse(ZONE_REGISTRY_PATH)
    assert "normalize_filter_profiles" not in _defined_names(tree)


def test_zone_registry_does_not_own_installed_clinical_catalog() -> None:
    source = ZONE_REGISTRY_PATH.read_text(encoding="utf-8")
    tree = _parse(ZONE_REGISTRY_PATH)
    imported = _imported_module_names(tree)

    assert "ZONE_REGISTRY" not in source
    assert "ZONE_CLI_CHOICES" not in source
    assert not any(
        module == FILTER_PROFILE_PLUGIN_PREFIX
        or module.startswith(f"{FILTER_PROFILE_PLUGIN_PREFIX}.")
        for module in imported
    )
    assert "load_zone_config" not in source
    assert "resolve_zone_config_input" not in source
    assert "lookup_installed_filter_config" not in source
    for config_id in INSTALLED_FILTER_CONFIG_IDS:
        assert f'"{config_id}":' not in source
        assert f"'{config_id}':" not in source
    assert "_load_registry_zone_key" not in source


def test_production_code_does_not_import_runtime_normalize_filter_profiles() -> None:
    violations: list[str] = []
    for root in PRODUCTION_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in _iter_py_files(root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/__pycache__/" in rel:
                continue
            if path == PROFILES_PATH:
                continue
            text = path.read_text(encoding="utf-8")
            if "from runtime.zone_registry import normalize_filter_profiles" in text:
                violations.append(rel)
            if OLD_NORMALIZE_IMPORT in text:
                violations.append(f"{rel} references {OLD_NORMALIZE_IMPORT}")
    assert not violations, "\n".join(violations)
