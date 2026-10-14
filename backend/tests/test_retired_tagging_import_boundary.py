"""Architecture guards: retired per-unit tagging must not re-enter production imports."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

FORBIDDEN_RETIRED_TAGGING_IMPORTS = (
    "core.tagging.run_stage",
    "core.tagging.taggers.api",
    "core.tagging.taggers.mock",
    "plugins.clinical_trial_doc.tagging.registry",
    "plugins.clinical_trial_doc.tagging.profile",
    "plugins.clinical_trial_doc.tagging.prompts._legacy",
    "runtime.tag_registry",
)

PRODUCTION_CODE_SCAN_ROOTS = (
    BACKEND_ROOT / "steps",
    BACKEND_ROOT / "runtime",
    BACKEND_ROOT / "plugins",
    BACKEND_ROOT / "scripts",
    BACKEND_ROOT / "artifacts",
    BACKEND_ROOT / "core",
)


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


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


def _iter_py_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def test_production_code_does_not_import_retired_per_unit_tagging_modules() -> None:
    violations: list[str] = []
    for scan_root in PRODUCTION_CODE_SCAN_ROOTS:
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel or rel.startswith("tests/"):
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                for forbidden in FORBIDDEN_RETIRED_TAGGING_IMPORTS:
                    if imported == forbidden or imported.startswith(f"{forbidden}."):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)
