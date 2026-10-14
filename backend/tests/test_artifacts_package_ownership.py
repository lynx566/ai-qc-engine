"""Import boundary guards for artifacts package ownership migration (PR E)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

ARTIFACTS_ROOT = BACKEND_ROOT / "artifacts"
OLD_ARTIFACTS_ROOT = BACKEND_ROOT / "pipeline" / "artifacts"

EXPECTED_TRACKED_ARTIFACT_MODULES = (
    "__init__.py",
    "block_manifest.py",
    "coverage_bundle.py",
    "zone_match_bundle.py",
    "privacy_safety.py",
    "private_audit_bundle.py",
    "taggable_units.py",
    "upstream_validation.py",
    "evidence_source_preparation/__init__.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/aggregate_evidence_source_bundle.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assessment_input.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assessment_input_compact.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assessment_input_ids.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assessment_input_preview.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assessment_input_safety.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/heading_scope_eligibility.py",
    "evidence_source_preparation/schema.py",
    "evidence_source_preparation/clinical_trial_doc/__init__.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/__init__.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/__init__.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/schema.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/scope_assessment_review.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/scope_assessments.py",
    "routing/__init__.py",
    "routing/route_bundles.py",
    "routing/schema.py",
    "routing/types.py",
    "routing/unit_integrity.py",
    "evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/aggregate_prepare_integrity.py",
)

FORBIDDEN_OLD_PACKAGE_IMPORT_PREFIXES = (
    "pipeline.artifacts",
    "pipeline.artifacts.",
    "artifacts.process",
    "artifacts.process.",
)

OLD_PROCESS_ARTIFACTS_ROOT = ARTIFACTS_ROOT / "process"

PRODUCTION_SCAN_ROOTS = (
    BACKEND_ROOT / "steps",
    BACKEND_ROOT / "core",
    BACKEND_ROOT / "runtime",
    BACKEND_ROOT / "plugins",
    BACKEND_ROOT / "scripts",
)


def _iter_py_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.py") if path.is_file())


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


def test_artifacts_package_exists_at_top_level() -> None:
    assert ARTIFACTS_ROOT.is_dir()
    assert (ARTIFACTS_ROOT / "__init__.py").is_file()


def test_old_pipeline_artifacts_package_absent() -> None:
    assert not OLD_ARTIFACTS_ROOT.exists()


def test_old_process_artifacts_package_absent() -> None:
    assert not OLD_PROCESS_ARTIFACTS_ROOT.exists()


def test_all_tracked_artifact_modules_migrated() -> None:
    missing: list[str] = []
    for rel in EXPECTED_TRACKED_ARTIFACT_MODULES:
        path = ARTIFACTS_ROOT / rel
        if not path.is_file():
            missing.append(rel)
    assert not missing, f"missing artifact modules: {missing}"


def test_artifacts_package_importable() -> None:
    import artifacts
    import artifacts.evidence_source_preparation.schema
    import artifacts.routing

    assert artifacts.__file__ is not None


def test_process_schema_import_isolated_from_assessment_and_plugin_modules() -> None:
    script = """
import sys

from artifacts.evidence_source_preparation.schema import EVIDENCE_SOURCE_PREPARATION_STAGE
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    validate_assessment_input,
)

assert EVIDENCE_SOURCE_PREPARATION_STAGE == "evidence_source_preparation"
assert callable(validate_assessment_input)

expected = {
    "artifacts.evidence_source_preparation",
    "artifacts.evidence_source_preparation.schema",
}
missing = sorted(expected.difference(sys.modules))
assert not missing, f"expected modules not loaded: {missing}"

unexpected = [
    name
    for name in (
        "artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input",
        "artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact",
        "artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_safety",
        "plugins.clinical_trial_doc.evidence_source_preparation",
        "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.registry",
        "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh",
    )
    if name in sys.modules
]
assert not unexpected, f"unexpected modules loaded: {unexpected}"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_old_process_artifacts_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        import artifacts.process  # noqa: F401


def test_old_pipeline_artifacts_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        import pipeline.artifacts  # noqa: F401


def test_no_live_imports_of_old_process_artifacts_package() -> None:
    violations: list[str] = []
    scan_roots = (
        BACKEND_ROOT / "tests",
        *PRODUCTION_SCAN_ROOTS,
        BACKEND_ROOT / "artifacts",
    )
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel:
                continue
            if rel == "tests/test_artifacts_package_ownership.py":
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                if imported == "artifacts.process" or imported.startswith(
                    "artifacts.process."
                ):
                    violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_production_code_does_not_import_old_pipeline_artifacts() -> None:
    violations: list[str] = []
    for scan_root in PRODUCTION_SCAN_ROOTS:
        if not scan_root.exists():
            continue
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel:
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                for forbidden in FORBIDDEN_OLD_PACKAGE_IMPORT_PREFIXES:
                    if imported == forbidden.rstrip(".") or imported.startswith(forbidden):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_no_old_process_artifacts_package_forwarding_wrapper() -> None:
    if OLD_PROCESS_ARTIFACTS_ROOT.exists():
        for path in _iter_py_files(OLD_PROCESS_ARTIFACTS_ROOT):
            source = path.read_text(encoding="utf-8")
            assert "from artifacts" not in source, f"forwarding wrapper in {path}"
            assert "import artifacts" not in source, f"forwarding wrapper in {path}"
            assert "sys.modules" not in source, f"sys.modules alias in {path}"


def test_no_old_package_forwarding_wrapper() -> None:
    if OLD_ARTIFACTS_ROOT.exists():
        for path in _iter_py_files(OLD_ARTIFACTS_ROOT):
            source = path.read_text(encoding="utf-8")
            assert "from artifacts" not in source, f"forwarding wrapper in {path}"
            assert "import artifacts" not in source, f"forwarding wrapper in {path}"
            assert "sys.modules" not in source, f"sys.modules alias in {path}"


EVIDENCE_FORM_IDENTITY_PATH = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "clinical_safety"
    / "aggregate_evidence"
    / "evidence_form_identity.py"
)
OLD_PROCESSOR_IDENTITY_PATH = EVIDENCE_FORM_IDENTITY_PATH.parent / "processor_identity.py"
PRESERVED_RUN_DIR_LAYOUT_PROCESSOR_TYPE_TOKEN = (
    "stage/phase/run_id/doc_dir/task_key/processor_type"
)


def test_processor_identity_module_replaced_by_evidence_form_identity() -> None:
    assert EVIDENCE_FORM_IDENTITY_PATH.is_file()
    assert not OLD_PROCESSOR_IDENTITY_PATH.is_file()


def test_aggregate_evidence_form_id_value_unchanged() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
        AGGREGATE_EVIDENCE_FORM_ID,
    )

    assert AGGREGATE_EVIDENCE_FORM_ID == "aggregate_evidence"


def test_generic_esp_schema_exports_only_canonical_stage_vocabulary() -> None:
    import artifacts.evidence_source_preparation.schema as generic_schema

    assert generic_schema.__all__ == ["EVIDENCE_SOURCE_PREPARATION_STAGE"]
    assert not hasattr(generic_schema, "EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE")
    assert not hasattr(generic_schema, "validate_assessment_input")


def test_generic_esp_package_root_has_no_concrete_artifact_modules() -> None:
    root = ARTIFACTS_ROOT / "evidence_source_preparation"
    root_py_files = sorted(
        path.name
        for path in root.iterdir()
        if path.is_file() and path.suffix == ".py"
    )
    assert root_py_files == ["__init__.py", "schema.py"]


def test_no_live_processor_type_symbol_in_production() -> None:
    violations: list[str] = []
    for scan_root in PRODUCTION_SCAN_ROOTS:
        if not scan_root.exists():
            continue
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel:
                continue
            source = path.read_text(encoding="utf-8")
            if "PROCESSOR_TYPE" in source:
                violations.append(f"{rel} contains PROCESSOR_TYPE")
            if "processor_identity" in source:
                violations.append(f"{rel} references processor_identity")
    assert not violations, "\n".join(violations)


def test_processor_type_retained_only_in_persisted_run_dir_layout_descriptor() -> None:
    violations: list[str] = []
    for scan_root in (*PRODUCTION_SCAN_ROOTS, BACKEND_ROOT / "tests"):
        if not scan_root.exists():
            continue
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel:
                continue
            if rel == "tests/test_artifacts_package_ownership.py":
                continue
            source = path.read_text(encoding="utf-8")
            if "processor_type" not in source:
                continue
            if rel == "runtime/run_layout.py":
                assert (
                    PRESERVED_RUN_DIR_LAYOUT_PROCESSOR_TYPE_TOKEN in source
                ), "run_layout must preserve persisted processor_type layout token"
                if source.count("processor_type") != 1:
                    violations.append(
                        f"{rel} must only retain processor_type in run_dir_layout descriptor"
                    )
                continue
            violations.append(f"{rel} contains live processor_type reference")
    assert not violations, "\n".join(violations)
