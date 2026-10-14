"""Import boundary guards for canonical Extract runtime."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

EXTRACT_RUNTIME_ROOT = BACKEND_ROOT / "runtime" / "extract"

FORBIDDEN_EXTRACT_RUNTIME_IMPORTS = (
    "runtime.document_processing_bootstrap",
    "scripts.stage_runners.extract_reports",
    "plugins.clinical_trial_doc.consistency_qc",
    "runtime.request_file_intake",
    "runtime.request_file_intake.operations",
    "runtime.document_source_binding",
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


def test_extract_runtime_does_not_import_forbidden_modules() -> None:
    violations: list[str] = []
    for path in sorted(EXTRACT_RUNTIME_ROOT.rglob("*.py")):
        imported = _imported_module_names(_parse(path))
        for module in imported:
            for forbidden in FORBIDDEN_EXTRACT_RUNTIME_IMPORTS:
                if module == forbidden or module.startswith(f"{forbidden}."):
                    violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {module}")
    assert not violations, "forbidden imports in runtime/extract:\n" + "\n".join(violations)
