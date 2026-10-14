"""Ownership boundary guards for aggregate application layer migration (PR D2)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

OLD_ADAPTER_PATH = (
    BACKEND_ROOT
    / "pipeline"
    / "evidence_source_preparation"
    / "aggregate_evidence_adapter.py"
)
OLD_TYPES_PATH = (
    BACKEND_ROOT
    / "pipeline"
    / "evidence_source_preparation"
    / "aggregate_evidence_types.py"
)
DOMAIN_ROOT_ADAPTER_PATH = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "phase_facade.py"
)
NEW_ADAPTER_PATH = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "clinical_safety"
    / "aggregate_evidence"
    / "phase_facade.py"
)
NEW_EXECUTION_TYPES_PATH = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "clinical_safety"
    / "aggregate_evidence"
    / "execution_types.py"
)

FORBIDDEN_OLD_IMPORT_PREFIXES = (
    "pipeline.evidence_source_preparation.aggregate_evidence_adapter",
    "pipeline.evidence_source_preparation.aggregate_evidence_types",
)

FORBIDDEN_ADAPTER_IMPORT_PREFIXES = (
    "runtime",
    "runtime.",
    "scripts",
    "scripts.",
    "steps",
    "steps.",
)

FORBIDDEN_EXECUTION_TYPES_IMPORT_PREFIXES = (
    "runtime",
    "runtime.",
    "scripts",
    "scripts.",
    "steps",
    "steps.",
)

ACTIVE_SCAN_ROOTS = (
    BACKEND_ROOT / "steps",
    BACKEND_ROOT / "runtime",
    BACKEND_ROOT / "plugins" / "clinical_trial_doc",
    BACKEND_ROOT / "scripts",
)

RUNTIME_OPERATION_PATHS = (
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/prepare.py",
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assess.py",
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/eligibility.py",
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assemble.py",
)

RETIRED_RUNTIME_STAGE_PATHS = tuple(
    BACKEND_ROOT / "runtime" / name
    for name in (
        "process_prepare_stage.py",
        "process_assess_stage.py",
        "process_eligibility_stage.py",
        "process_assemble_stage.py",
    )
)

EXPECTED_APPLICATION_HARNESS_RESOLVER_IMPORT = (
    "application.clinical_trial_doc_consistency_qc.evidence_source_preparation_phase_harness_installation"
)

PRODUCTION_INSTALLATION_PATH = (
    BACKEND_ROOT
    / "application/clinical_trial_doc_consistency_qc/evidence_source_preparation_installation.py"
)

FORBIDDEN_APPLICATION_IMPORT_PREFIX = "application.clinical_trial_doc_consistency_qc"

RUNNER_PATHS = tuple(
    (
        BACKEND_ROOT
        / "scripts/stage_runners/evidence_source_preparation/aggregate_evidence"
    ).glob("*_runner.py")
)

FORBIDDEN_PHASE_RUNTIME_IMPORTS = (
    "steps",
    "steps.evidence_source_preparation",
    "plugins.clinical_trial_doc.evidence_source_preparation.phase_facade",
    "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade",
    "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assemble_aggregate_evidence_source_bundle",
    "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding",
)

OPERATIONS_PATH = (
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/operations.py"
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


def _forbidden_import_violations(
    path: Path,
    *,
    forbidden_prefixes: tuple[str, ...],
) -> list[str]:
    tree = _parse(path)
    violations: list[str] = []
    for imported in _imported_module_names(tree):
        if any(
            imported == prefix.rstrip(".") or imported.startswith(prefix)
            for prefix in forbidden_prefixes
        ):
            violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")
    return violations


def test_old_adapter_module_removed() -> None:
    assert not OLD_ADAPTER_PATH.is_file()


def test_old_execution_types_module_removed() -> None:
    assert not OLD_TYPES_PATH.is_file()


def test_phase_facade_exists_in_clinical_safety_aggregate_package() -> None:
    assert NEW_ADAPTER_PATH.is_file()


def test_domain_root_phase_facade_is_removed() -> None:
    assert not DOMAIN_ROOT_ADAPTER_PATH.is_file()


def test_new_execution_types_exists() -> None:
    assert NEW_EXECUTION_TYPES_PATH.is_file()


def test_active_production_code_has_no_old_import_paths() -> None:
    violations: list[str] = []
    for scan_root in ACTIVE_SCAN_ROOTS:
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel:
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                for forbidden in FORBIDDEN_OLD_IMPORT_PREFIXES:
                    if imported == forbidden or imported.startswith(f"{forbidden}."):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_phase_facade_import_boundary() -> None:
    violations = _forbidden_import_violations(
        NEW_ADAPTER_PATH,
        forbidden_prefixes=FORBIDDEN_ADAPTER_IMPORT_PREFIXES,
    )
    assert not violations, "\n".join(violations)


def test_execution_types_import_boundary() -> None:
    violations = _forbidden_import_violations(
        NEW_EXECUTION_TYPES_PATH,
        forbidden_prefixes=FORBIDDEN_EXECUTION_TYPES_IMPORT_PREFIXES,
    )
    assert not violations, "\n".join(violations)


def test_phase_runtime_imports_no_pipeline_step_or_plugin_adapter() -> None:
    for path in RUNTIME_OPERATION_PATHS:
        tree = _parse(path)
        imported = _imported_module_names(tree)
        source = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_PHASE_RUNTIME_IMPORTS:
            assert forbidden not in imported, (
                f"{path.relative_to(BACKEND_ROOT)} must not import {forbidden}"
            )
        assert "run_prepare_phase" in source or "run_assess_phase" in source or (
            "run_evaluate_eligibility_phase" in source
        ) or ("run_assemble_phase" in source)


def test_operations_accepts_injected_phase_dependencies_only() -> None:
    tree = _parse(OPERATIONS_PATH)
    imported = _imported_module_names(tree)
    source = OPERATIONS_PATH.read_text(encoding="utf-8")
    assert "phase_dependencies" in source
    assert "resolve_installed_aggregate_evidence_phase_harness_dependencies" not in source
    assert "resolve_installed_aggregate_evidence_phase_dependencies" not in source
    assert not any(
        module.startswith(FORBIDDEN_APPLICATION_IMPORT_PREFIX) for module in imported
    ), (
        f"{OPERATIONS_PATH.relative_to(BACKEND_ROOT)} must not import application installation"
    )
    for forbidden in FORBIDDEN_PHASE_RUNTIME_IMPORTS:
        assert forbidden not in imported, (
            f"{OPERATIONS_PATH.relative_to(BACKEND_ROOT)} must not import {forbidden}"
        )


def test_runners_resolve_installed_phase_harness_dependencies() -> None:
    for path in RUNNER_PATHS:
        tree = _parse(path)
        imported = _imported_module_names(tree)
        source = path.read_text(encoding="utf-8")
        assert EXPECTED_APPLICATION_HARNESS_RESOLVER_IMPORT in imported, path.name
        assert "resolve_installed_aggregate_evidence_phase_harness_dependencies" in source, path.name
        assert "phase_dependencies=" in source, path.name


def test_production_installation_has_no_phase_harness_surface() -> None:
    source = PRODUCTION_INSTALLATION_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "INSTALLED_AGGREGATE_EVIDENCE_PREPARE_PHASE",
        "INSTALLED_AGGREGATE_EVIDENCE_ASSESS_PHASE",
        "INSTALLED_AGGREGATE_EVIDENCE_ELIGIBILITY_PHASE",
        "INSTALLED_AGGREGATE_EVIDENCE_ASSEMBLE_PHASE",
        "AggregateEvidencePhaseDependencies",
        "AggregateEvidencePhaseHarnessDependencies",
        "resolve_installed_aggregate_evidence_phase_dependencies",
        "resolve_installed_aggregate_evidence_phase_harness_dependencies",
        "resolve_installed_aggregate_evidence_semantic_module_id",
        "resolve_installed_aggregate_evidence_harness_semantic_module_id",
    ):
        assert forbidden not in source


def test_runtime_evidence_source_preparation_has_no_application_imports() -> None:
    runtime_root = BACKEND_ROOT / "runtime" / "evidence_source_preparation"
    violations: list[str] = []
    for path in _iter_py_files(runtime_root):
        for module in _imported_module_names(_parse(path)):
            if module and module.startswith(FORBIDDEN_APPLICATION_IMPORT_PREFIX):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} imports {module}"
                )
    assert not violations, "\n".join(violations)


def test_concrete_runtime_ownership_paths_replace_false_generic_stage_modules() -> None:
    assert all(path.is_file() for path in RUNTIME_OPERATION_PATHS)
    assert all(not path.exists() for path in RETIRED_RUNTIME_STAGE_PATHS)
    expected_entrypoints = ("run_prepare", "run_assess", "run_eligibility", "run_assemble")
    for path, entrypoint in zip(RUNTIME_OPERATION_PATHS, expected_entrypoints, strict=True):
        assert f"def {entrypoint}(" in path.read_text(encoding="utf-8")


def test_legacy_orchestrator_and_resolver_modules_removed() -> None:
    orchestrator_path = (
        BACKEND_ROOT / "pipeline" / "evidence_source_preparation" / "orchestrator.py"
    )
    resolver_path = (
        BACKEND_ROOT / "pipeline" / "evidence_source_preparation" / "resolver.py"
    )
    assert not orchestrator_path.is_file()
    assert not resolver_path.is_file()


def test_legacy_pipeline_evidence_source_preparation_package_removed() -> None:
    pipeline_root = BACKEND_ROOT / "pipeline" / "evidence_source_preparation"
    assert not pipeline_root.exists(), (
        f"legacy pipeline package must be removed: {pipeline_root}"
    )


def test_no_forwarding_wrapper_modules() -> None:
    assert not OLD_ADAPTER_PATH.is_file()
    assert not OLD_TYPES_PATH.is_file()
    pipeline_root = BACKEND_ROOT / "pipeline" / "evidence_source_preparation"
    assert not pipeline_root.exists()
