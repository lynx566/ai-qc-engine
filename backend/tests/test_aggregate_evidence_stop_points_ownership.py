"""Ownership guards for Aggregate Evidence durable stop points."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

STOP_POINTS_PATH = (
    BACKEND_ROOT
    / "runtime"
    / "evidence_source_preparation"
    / "clinical_trial_doc"
    / "clinical_safety"
    / "aggregate_evidence"
    / "stop_points.py"
)
RETIRED_ROOT_RUNTIME_PATHS = tuple(
    BACKEND_ROOT / "runtime" / name
    for name in (
        "evidence_source_preparation_operations.py",
        "process_stage_results.py",
        "process_phase_sequence.py",
        "process_artifact_persistence.py",
        "process_phase_compat.py",
    )
)
REMOVED_COMPAT_PATH = (
    BACKEND_ROOT
    / "pipeline"
    / "evidence_source_preparation"
    / "stop_at_compat.py"
)

FORBIDDEN_OLD_STOP_AT_COMPAT_IMPORTS = (
    "pipeline.evidence_source_preparation.stop_at_compat",
)

CANONICAL_STOP_POINTS_IMPORT = (
    "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stop_points"
)

COMPAT_FORBIDDEN_IMPORT_PREFIXES = (
    "pipeline",
    "scripts",
    "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.sequence",
    "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare",
    "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assess",
    "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.eligibility",
    "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assemble",
    "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence",
)

PRODUCTION_SCAN_ROOTS = (
    BACKEND_ROOT / "steps",
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


def test_stop_points_live_with_aggregate_evidence_runtime() -> None:
    assert not REMOVED_COMPAT_PATH.exists(), (
        f"stop-at compatibility must not live under pipeline/evidence_source_preparation/: "
        f"{REMOVED_COMPAT_PATH}"
    )
    assert STOP_POINTS_PATH.is_file(), f"stop points must exist at {STOP_POINTS_PATH}"
    for retired_path in RETIRED_ROOT_RUNTIME_PATHS:
        assert not retired_path.exists(), f"retired runtime module remains: {retired_path}"


def test_production_code_does_not_import_pipeline_stop_at_compat() -> None:
    violations: list[str] = []
    for root in PRODUCTION_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in _iter_py_files(root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/__pycache__/" in rel or "/runs/" in rel:
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                for forbidden in FORBIDDEN_OLD_STOP_AT_COMPAT_IMPORTS:
                    if imported == forbidden or imported.startswith(f"{forbidden}."):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_runtime_stop_points_does_not_import_forbidden_packages() -> None:
    tree = _parse(STOP_POINTS_PATH)
    violations: list[str] = []
    for imported in _imported_module_names(tree):
        for prefix in COMPAT_FORBIDDEN_IMPORT_PREFIXES:
            if imported == prefix or imported.startswith(f"{prefix}."):
                violations.append(f"aggregate_evidence/stop_points.py imports {imported}")
    assert not violations, "\n".join(violations)


def test_no_forwarding_wrapper_for_old_stop_at_compat_path() -> None:
    esp_root = (
        BACKEND_ROOT / "pipeline" / "evidence_source_preparation"
    )
    assert not esp_root.exists(), (
        "pipeline/evidence_source_preparation/ must not exist after D3d input migration"
    )
