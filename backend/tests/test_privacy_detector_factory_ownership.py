"""Ownership boundary guards for PR G2 detector factory extraction.

Verifies that the 7 detector-construction symbols were correctly moved from
``privacy/document_transform.py`` to ``privacy/detectors/factory.py`` and that
neither the old module nor dead symbols are still accessible.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PRIVACY_ROOT = BACKEND_ROOT / "privacy"
FACTORY_PATH = PRIVACY_ROOT / "detectors" / "factory.py"
DOCUMENT_TRANSFORM_PATH = PRIVACY_ROOT / "document_transform.py"
TRANSFORM_PATH = PRIVACY_ROOT / "transform.py"

MOVED_SYMBOLS = frozenset(
    {
        "_regex_rules_for_language",
        "_try_uie_detector",
        "build_stage_detectors",
        "build_mask_detectors",
        "_build_composite_detector",
    }
)

DELETED_SYMBOLS = frozenset({"_resolve_detector"})

FACTORY_PUBLIC = frozenset({"build_stage_detectors", "build_mask_detectors"})

FORBIDDEN_IMPORTS = frozenset(
    {
        "privacy.document_transform",
        "privacy.transform",
        "pipeline",
        "runtime",
        "scripts",
        "artifacts",
    }
)

FORBIDDEN_DOCUMENT_TRANSFORM_SYMBOLS = MOVED_SYMBOLS | DELETED_SYMBOLS


def _def_names(path: Path) -> frozenset[str]:
    """Return all module-level function/class names defined in *path*."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return frozenset(names)


def _imports_from(path: Path) -> list[str]:
    """Return full module paths imported by *path*."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
    return imported


# ---------------------------------------------------------------------------
# 1. factory.py exists
# ---------------------------------------------------------------------------


def test_factory_module_exists() -> None:
    assert FACTORY_PATH.is_file(), f"{FACTORY_PATH} not found"


# ---------------------------------------------------------------------------
# 2. factory.py defines public symbols
# ---------------------------------------------------------------------------


def test_factory_defines_public_symbols() -> None:
    names = _def_names(FACTORY_PATH)
    for symbol in FACTORY_PUBLIC:
        assert symbol in names, f"factory.py missing public symbol {symbol!r}"


# ---------------------------------------------------------------------------
# 3. factory.py defines ALL moved private helpers
# ---------------------------------------------------------------------------


def test_factory_defines_all_moved_symbols() -> None:
    names = _def_names(FACTORY_PATH)
    missing = MOVED_SYMBOLS - names
    assert not missing, f"factory.py missing symbols: {sorted(missing)}"


# ---------------------------------------------------------------------------
# 4. document_transform.py NO LONGER defines moved/deleted symbols
# ---------------------------------------------------------------------------


def test_document_transform_no_longer_defines_moved_symbols() -> None:
    names = _def_names(DOCUMENT_TRANSFORM_PATH)
    remaining = names & FORBIDDEN_DOCUMENT_TRANSFORM_SYMBOLS
    assert not remaining, (
        f"document_transform.py still defines: {sorted(remaining)}"
    )


# ---------------------------------------------------------------------------
# 5. document_transform.py imports build_mask_detectors from factory
# ---------------------------------------------------------------------------


def test_document_transform_imports_from_factory() -> None:
    imports = _imports_from(DOCUMENT_TRANSFORM_PATH)
    assert "privacy.detectors.factory" in imports, (
        "document_transform.py must import from privacy.detectors.factory"
    )


# ---------------------------------------------------------------------------
# 6. transform.py imports build_stage_detectors from factory
# ---------------------------------------------------------------------------


def test_transform_imports_from_factory() -> None:
    imports = _imports_from(TRANSFORM_PATH)
    assert "privacy.detectors.factory" in imports, (
        "transform.py must import from privacy.detectors.factory"
    )


# ---------------------------------------------------------------------------
# 7. factory.py does NOT import forbidden modules
# ---------------------------------------------------------------------------


def test_factory_no_forbidden_imports() -> None:
    imports = _imports_from(FACTORY_PATH)
    violations: list[str] = []
    for module in FORBIDDEN_IMPORTS:
        if module in imports or any(i.startswith(module + ".") for i in imports):
            violations.append(module)
    assert not violations, (
        f"factory.py imports forbidden modules: {violations}"
    )


# ---------------------------------------------------------------------------
# 8. No compatibility re-exports in document_transform.py
# ---------------------------------------------------------------------------


def test_document_transform_no_compat_reexports() -> None:
    """Verify document_transform.py does not expose moved symbols via __all__."""
    source = DOCUMENT_TRANSFORM_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    all_names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant):
                                all_names.add(str(elt.value))

    # The import of build_mask_detectors for internal use (run()) is fine.
    # But moved symbols must not appear in __all__ as re-exports.
    exposed = all_names & MOVED_SYMBOLS
    assert not exposed, (
        f"document_transform.py __all__ re-exports: {sorted(exposed)}"
    )


# ---------------------------------------------------------------------------
# 9. EXPERIMENTS_ROOT no longer in document_transform.py
# ---------------------------------------------------------------------------


def test_experiments_root_removed_from_document_transform() -> None:
    source = DOCUMENT_TRANSFORM_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "EXPERIMENTS_ROOT":
                    raise AssertionError(
                        "document_transform.py still defines EXPERIMENTS_ROOT"
                    )
