"""Import boundary guards for prepare-analysis privacy ownership migration (PR G1)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PREPARE_ANALYSIS_STEP = (
    BACKEND_ROOT / "steps" / "prepare_analysis.py"
)
PRIVACY_TRANSFORM_PATH = BACKEND_ROOT / "privacy" / "transform.py"
DOCUMENT_TRANSFORM_PATH = BACKEND_ROOT / "privacy" / "document_transform.py"
REMOVED_MASK_STEP = BACKEND_ROOT / "steps" / "mask.py"
REMOVED_PRIVACY_TRANSFORM_STEP = (
    BACKEND_ROOT / "steps" / "privacy_transform.py"
)
STEPS_DIR = BACKEND_ROOT / "steps"
PREPARE_ANALYSIS_RUNNER = (
    BACKEND_ROOT / "scripts" / "stage_runners" / "prepare_analysis_runner.py"
)
PRIVACY_ROOT = BACKEND_ROOT / "privacy"
CORE_ROOT = BACKEND_ROOT / "core"
PREPARE_ANALYSIS_OPERATIONS_DIR = (
    BACKEND_ROOT / "operations" / "prepare_analysis"
)
EXPECTED_PREPARE_ANALYSIS_OPERATIONS_MODULES = (
    "__init__.py",
    "contracts.py",
    "registry.py",
)
PREPARE_ANALYSIS_ARTIFACTS = (
    BACKEND_ROOT / "artifacts" / "prepare_analysis.py",
    BACKEND_ROOT / "artifacts" / "privacy_mapping.py",
    BACKEND_ROOT / "artifacts" / "block_manifest.py",
)

FORBIDDEN_OLD_IMPORTS = (
    "steps.mask",
    "steps.privacy_transform",
)

PRIVACY_FORBIDDEN_IMPORT_PREFIXES = (
    "runtime",
    "steps",
    "scripts",
)

PRODUCTION_SCAN_ROOTS = (
    BACKEND_ROOT / "steps",
    BACKEND_ROOT / "runtime",
    BACKEND_ROOT / "scripts",
    BACKEND_ROOT / "plugins",
)

EXPECTED_CANONICAL_PIPELINE_STEPS = (
    "extract.py",
    "request_file_intake.py",
    "prepare_analysis.py",
    "filter.py",
    "project_filter_output.py",
    "doc_meta.py",
    "route.py",
    "evidence_source_preparation.py",
    "evidence_comparison.py",
    "effective_candidate_scope.py",
)

ALLOWED_LEGACY_MASK_STRING_PATHS = (
    "runtime/run_ids.py",
    "scripts/tools/inspect_runs.py",
    "core/metadata/block_context.py",
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
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_privacy_owner_modules_exist() -> None:
    assert PRIVACY_TRANSFORM_PATH.is_file(), str(PRIVACY_TRANSFORM_PATH)
    assert DOCUMENT_TRANSFORM_PATH.is_file(), str(DOCUMENT_TRANSFORM_PATH)
    assert PREPARE_ANALYSIS_STEP.is_file(), str(PREPARE_ANALYSIS_STEP)


def test_removed_pipeline_mask_steps_are_absent() -> None:
    assert not REMOVED_MASK_STEP.exists(), str(REMOVED_MASK_STEP)
    assert not REMOVED_PRIVACY_TRANSFORM_STEP.exists(), str(
        REMOVED_PRIVACY_TRANSFORM_STEP
    )


def test_pipeline_steps_match_canonical_module_inventory() -> None:
    present = {
        path.name
        for path in STEPS_DIR.iterdir()
        if path.is_file() and path.suffix == ".py" and path.name != "__init__.py"
    }
    assert present == set(EXPECTED_CANONICAL_PIPELINE_STEPS)


def test_prepare_analysis_operations_package_has_no_execution_modules() -> None:
    present = {
        path.name
        for path in PREPARE_ANALYSIS_OPERATIONS_DIR.iterdir()
        if path.is_file() and path.suffix == ".py"
    }
    assert present == set(EXPECTED_PREPARE_ANALYSIS_OPERATIONS_MODULES)


def test_pipeline_prepare_analysis_sibling_package_is_absent() -> None:
    assert not (BACKEND_ROOT / "pipeline" / "prepare_analysis").exists()


def test_production_code_does_not_import_pipeline_prepare_analysis_package() -> None:
    violations: list[str] = []
    for root in PRODUCTION_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in _iter_py_files(root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/tests/" in rel or rel.startswith("tests/"):
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                if imported == "pipeline.prepare_analysis" or imported.startswith(
                    "pipeline.prepare_analysis."
                ):
                    violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_production_code_does_not_import_removed_mask_steps() -> None:
    violations: list[str] = []
    for root in PRODUCTION_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in _iter_py_files(root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/tests/" in rel or rel.startswith("tests/"):
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                for forbidden in FORBIDDEN_OLD_IMPORTS:
                    if imported == forbidden or imported.startswith(f"{forbidden}."):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_prepare_analysis_step_imports_privacy_transform() -> None:
    imported = _imported_module_names(_parse(PREPARE_ANALYSIS_STEP))
    assert not any(name.startswith("plugins.clinical_trial_doc") for name in imported)
    assert "privacy.document_transform" in imported
    assert "privacy.transform" in imported
    violations = [
        name
        for name in imported
        for forbidden in FORBIDDEN_OLD_IMPORTS
        if name == forbidden or name.startswith(f"{forbidden}.")
    ]
    assert not violations, violations


def test_runners_call_prepare_analysis_step_not_privacy_implementation() -> None:
    imported = _imported_module_names(_parse(PREPARE_ANALYSIS_RUNNER))
    assert "runtime.prepare_analysis" in imported
    assert "steps.prepare_analysis" not in imported
    assert "privacy.transform" not in imported
    assert "privacy.document_transform" not in imported


def test_privacy_package_does_not_import_runtime_or_pipeline_steps() -> None:
    violations: list[str] = []
    for path in _iter_py_files(PRIVACY_ROOT):
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        tree = _parse(path)
        for imported in _imported_module_names(tree):
            for prefix in PRIVACY_FORBIDDEN_IMPORT_PREFIXES:
                if imported == prefix or imported.startswith(f"{prefix}."):
                    violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_shared_privacy_and_core_do_not_import_concrete_clinical_plugin() -> None:
    violations: list[str] = []
    for root in (PRIVACY_ROOT, CORE_ROOT):
        for path in _iter_py_files(root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            for imported in _imported_module_names(_parse(path)):
                if imported == "plugins.clinical_trial_doc" or imported.startswith(
                    "plugins.clinical_trial_doc."
                ):
                    violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_step_has_no_filesystem_or_runtime_dependency() -> None:
    imported = _imported_module_names(_parse(PREPARE_ANALYSIS_STEP))
    assert not imported.intersection({"os", "pathlib", "runtime"})
    assert not any(name.startswith("runtime.") for name in imported)


def test_prepare_analysis_artifacts_do_not_select_semantic_strategy() -> None:
    for path in PREPARE_ANALYSIS_ARTIFACTS:
        imported = _imported_module_names(_parse(path))
        assert not any(name.startswith("plugins.") for name in imported)
        assert not any(name.startswith("runtime.") for name in imported)


def test_legacy_mask_stage_strings_may_persist_for_historical_runs() -> None:
    for rel in ALLOWED_LEGACY_MASK_STRING_PATHS:
        path = BACKEND_ROOT / rel
        assert path.is_file(), f"expected historical compatibility file: {rel}"
