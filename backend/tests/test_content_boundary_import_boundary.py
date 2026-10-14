"""Import boundary guards for content boundary ownership (PR B)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

BOUNDARY_PATH = BACKEND_ROOT / "core" / "content" / "boundary.py"
REMOVED_BOUNDARY_PATH = BACKEND_ROOT / "pipeline" / "content_boundary.py"
FILTER_STEP_PATH = BACKEND_ROOT / "steps" / "filter.py"
HEADING_ZONE_PATH = BACKEND_ROOT / "core" / "filtering" / "heading_zone.py"

FORBIDDEN_OLD_CONTENT_BOUNDARY_IMPORTS = (
    "pipeline.content_boundary",
)

CANONICAL_CONTENT_BOUNDARY_IMPORT = "core.content.boundary"

BOUNDARY_FORBIDDEN_IMPORT_PREFIXES = (
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


def test_pipeline_content_boundary_module_is_removed() -> None:
    assert not REMOVED_BOUNDARY_PATH.exists(), (
        f"content boundary must not live under pipeline/: {REMOVED_BOUNDARY_PATH}"
    )
    assert BOUNDARY_PATH.is_file(), f"content boundary must exist at {BOUNDARY_PATH}"


def test_production_code_does_not_import_pipeline_content_boundary() -> None:
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
                for forbidden in FORBIDDEN_OLD_CONTENT_BOUNDARY_IMPORTS:
                    if imported == forbidden or imported.startswith(f"{forbidden}."):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_core_content_boundary_does_not_import_forbidden_packages() -> None:
    tree = _parse(BOUNDARY_PATH)
    violations: list[str] = []
    for imported in _imported_module_names(tree):
        for prefix in BOUNDARY_FORBIDDEN_IMPORT_PREFIXES:
            if imported == prefix or imported.startswith(f"{prefix}."):
                violations.append(f"core/content/boundary.py imports {imported}")
    assert not violations, "\n".join(violations)


def test_filter_step_and_heading_zone_use_canonical_content_boundary_import() -> None:
    for path in (FILTER_STEP_PATH, HEADING_ZONE_PATH):
        tree = _parse(path)
        imported = _imported_module_names(tree)
        assert CANONICAL_CONTENT_BOUNDARY_IMPORT in imported, (
            f"{path.relative_to(BACKEND_ROOT).as_posix()} must import "
            f"{CANONICAL_CONTENT_BOUNDARY_IMPORT}"
        )
