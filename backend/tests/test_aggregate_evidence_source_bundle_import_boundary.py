"""Import boundary guards for aggregate evidence source bundle artifact identity (PR5)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

ACTIVE_SCAN_ROOTS = (
    BACKEND_ROOT / "artifacts" / "process",
    BACKEND_ROOT / "plugins" / "clinical_trial_doc" / "evidence_source_preparation",
    BACKEND_ROOT / "pipeline" / "evidence_source_preparation",
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assemble.py",
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/persistence.py",
    BACKEND_ROOT
    / "scripts/stage_runners/evidence_source_preparation/aggregate_evidence/assemble_runner.py",
)

FORBIDDEN_LEGACY_IMPORTS = (
    "artifacts.evidence_source_preparation.evidence_processing_input",
)

FORBIDDEN_LEGACY_TOKENS = (
    "build_evidence_processing_input",
    "validate_evidence_processing_input",
    "assemble_evidence_input",
    "ASSEMBLE_EVIDENCE_INPUT_OPERATION",
    "source_evidence_processing_input_id",
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
    return names


def _iter_py_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def test_active_paths_do_not_import_frozen_legacy_producer_module() -> None:
    violations: list[str] = []
    for scan_root in ACTIVE_SCAN_ROOTS:
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel:
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                for forbidden in FORBIDDEN_LEGACY_IMPORTS:
                    if imported == forbidden or imported.startswith(f"{forbidden}."):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)
def test_active_paths_do_not_use_frozen_legacy_artifact_identity_tokens() -> None:
    violations: list[str] = []
    for scan_root in ACTIVE_SCAN_ROOTS:
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel:
                continue
            source = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_LEGACY_TOKENS:
                if token in source:
                    violations.append(f"{rel} contains forbidden token {token!r}")
    assert not violations, "\n".join(violations)


# End of active aggregate-evidence import-boundary checks.
