"""Import boundary guards for core/metadata ownership (Doc Meta Slice 2)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

CORE_METADATA_ROOT = BACKEND_ROOT / "core" / "metadata"
FORBIDDEN_IMPORT_PREFIXES = ("plugins",)


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
    return names


def _is_forbidden_plugin_import(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_core_metadata_does_not_import_plugins() -> None:
    violations: list[str] = []
    for path in sorted(CORE_METADATA_ROOT.rglob("*.py")):
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        for imported in _imported_module_names(_parse(path)):
            if _is_forbidden_plugin_import(imported):
                violations.append(f"{rel}: {imported}")
    assert not violations, (
        "core/metadata must not import plugins.*; violations:\n"
        + "\n".join(violations)
    )
