"""Import boundary guards for Evidence Source Preparation namespace (PR2)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

FORBIDDEN_OLD_GENERIC_IMPORTS = (
    "pipeline.evidence_processing",
    "plugins.clinical_trial_doc.evidence_processing",
    "steps.evidence_processing",
    "runtime.evidence_processing_stage",
    "pipeline.evidence_source_preparation",
)

LEGACY_PIPELINE_PACKAGE_ROOT = BACKEND_ROOT / "pipeline" / "evidence_source_preparation"
PLUGIN_PACKAGE_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
)
FORBIDDEN_GENERIC_IMPORT_PREFIXES = (
    "plugins.clinical_trial_doc.evidence_content_classification",
    "plugins.clinical_trial_doc.evidence_item_modeling",
    "plugins.evidence_comparison",
    "plugins.clinical_trial_doc.evidence_reconciliation",
)

FORBIDDEN_PLUGIN_TOKENS = (
    "statement_classification",
    "aggregate_statement_classifications",
    "clinical_safety_aggregate_statement_classification_zh",
)

AGGREGATE_EVIDENCE_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "clinical_safety"
    / "aggregate_evidence"
)

FORBIDDEN_AGGREGATE_IMPORT_PREFIXES = (
    "plugins.clinical_trial_doc.comparisons.aggregate_evidence",
    "plugins.clinical_trial_doc.tagging.registry",
    "plugins.clinical_trial_doc.tagging.profile",
    "plugins.clinical_trial_doc.tagging.prompts._legacy",
    "plugins.clinical_trial_doc.evidence_content_classification",
    "plugins.clinical_trial_doc.evidence_item_modeling",
    "plugins.evidence_comparison",
    "plugins.clinical_trial_doc.evidence_reconciliation",
)

FORBIDDEN_OLD_OWNERSHIP_IMPORTS = (
    "plugins.clinical_trial_doc.comparisons.aggregate_evidence",
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


ACTIVE_SCAN_ROOTS = (
    BACKEND_ROOT / "steps",
    BACKEND_ROOT / "runtime",
    BACKEND_ROOT / "plugins" / "clinical_trial_doc",
    BACKEND_ROOT / "scripts",
)


def test_active_code_has_no_old_comparisons_aggregate_evidence_imports() -> None:
    violations: list[str] = []
    for scan_root in ACTIVE_SCAN_ROOTS:
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel:
                continue
            if rel.startswith("plugins/clinical_trial_doc/tagging/"):
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                for forbidden in FORBIDDEN_OLD_OWNERSHIP_IMPORTS:
                    if imported == forbidden or imported.startswith(f"{forbidden}."):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_aggregate_evidence_active_modules_do_not_import_retired_tagging_or_comparisons() -> None:
    violations: list[str] = []
    for path in _iter_py_files(AGGREGATE_EVIDENCE_ROOT):
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        tree = _parse(path)
        for imported in _imported_module_names(tree):
            for prefix in FORBIDDEN_AGGREGATE_IMPORT_PREFIXES:
                if imported == prefix.rstrip(".") or imported.startswith(prefix):
                    violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)


def test_active_code_has_no_old_generic_import_paths() -> None:
    violations: list[str] = []
    for scan_root in ACTIVE_SCAN_ROOTS:
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/runs/" in rel or "/__pycache__/" in rel:
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                for forbidden in FORBIDDEN_OLD_GENERIC_IMPORTS:
                    if imported == forbidden or imported.startswith(f"{forbidden}."):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)

def test_legacy_pipeline_evidence_source_preparation_package_removed() -> None:
    assert not LEGACY_PIPELINE_PACKAGE_ROOT.exists(), (
        f"legacy pipeline package must be removed: {LEGACY_PIPELINE_PACKAGE_ROOT}"
    )


def test_plugin_package_has_no_classification_symbols() -> None:
    violations: list[str] = []
    for path in _iter_py_files(PLUGIN_PACKAGE_ROOT):
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_PLUGIN_TOKENS:
            if token in source:
                violations.append(f"{rel} contains {token!r}")
    assert not violations, "\n".join(violations)


PR4_ACTIVE_TERMINOLOGY_SCAN_ROOTS = (
    BACKEND_ROOT / "plugins" / "clinical_trial_doc" / "evidence_source_preparation",
    BACKEND_ROOT / "artifacts" / "process" / "assessment_input.py",
    BACKEND_ROOT / "artifacts" / "process" / "assessment_input_compact.py",
    BACKEND_ROOT / "artifacts" / "process" / "schema.py",
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/prepare.py",
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assess.py",
)

FORBIDDEN_PR4_ACTIVE_IMPORT_PREFIXES = (
    "plugins.clinical_trial_doc.tagging.profile",
    "plugins.clinical_trial_doc.tagging.registry",
    "plugins.clinical_trial_doc.tagging.prompts._legacy",
)



def test_active_heading_scope_paths_do_not_use_legacy_tag_profile_terminology() -> None:
    violations: list[str] = []
    for scan_root in PR4_ACTIVE_TERMINOLOGY_SCAN_ROOTS:
        paths = _iter_py_files(scan_root)
        for path in paths:
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            source = path.read_text(encoding="utf-8")
            if "ClinicalTrialDocTagProfile" in source:
                violations.append(f"{rel} contains forbidden token 'ClinicalTrialDocTagProfile'")
            if "DEFAULT_AGGREGATE_TAG_PROFILE_REF" in source:
                violations.append(f"{rel} contains forbidden token 'DEFAULT_AGGREGATE_TAG_PROFILE_REF'")
            if rel not in {
                "artifacts/evidence_source_preparation/schema.py",
                "artifacts/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/assessment_input_compact.py",
            }:
                for pattern in ('"tag_profile_ref":', '.get("tag_profile_ref")', '["tag_profile_ref"]'):
                    if pattern in source:
                        violations.append(f"{rel} contains forbidden legacy key usage {pattern!r}")
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                for prefix in FORBIDDEN_PR4_ACTIVE_IMPORT_PREFIXES:
                    if imported == prefix or imported.startswith(f"{prefix}."):
                        violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)
