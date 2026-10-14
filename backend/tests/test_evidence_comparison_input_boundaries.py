"""Import boundary and ownership verification for evidence comparison."""

# ruff: noqa: SIM102
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

CORE_EVIDENCE_COMPARISON = BACKEND_ROOT / "core" / "evidence_comparison"
ARTIFACTS_EVIDENCE_COMPARISON = BACKEND_ROOT / "artifacts" / "evidence_comparison"
LEGACY_PLUGIN_EVIDENCE_COMPARISON = BACKEND_ROOT / "plugins" / "evidence_comparison"
AGGREGATE_RUNTIME_EVIDENCE_COMPARISON_FILES = (
    BACKEND_ROOT
    / "runtime"
    / "evidence_comparison"
    / "clinical_trial_doc"
    / "clinical_safety"
    / "aggregate_evidence"
    / "stage.py",
    BACKEND_ROOT
    / "runtime"
    / "evidence_comparison"
    / "clinical_trial_doc"
    / "clinical_safety"
    / "aggregate_evidence"
    / "materialization.py",
    BACKEND_ROOT
    / "runtime"
    / "evidence_comparison"
    / "clinical_trial_doc"
    / "clinical_safety"
    / "aggregate_evidence"
    / "persistence.py",
)
AGGREGATE_RUNTIME_EVIDENCE_COMPARISON_PRODUCER_GUARD_FILES = (
    BACKEND_ROOT
    / "runtime"
    / "evidence_comparison"
    / "clinical_trial_doc"
    / "clinical_safety"
    / "aggregate_evidence"
    / "materialization.py",
)
OPERATIONS_EVIDENCE_COMPARISON = BACKEND_ROOT / "operations" / "evidence_comparison"
CLINICAL_AGGREGATE_PLUGIN_EVIDENCE_COMPARISON = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
)
REQUIRED_CLINICAL_AGGREGATE_PLUGIN_ROOT_MODULES = frozenset(
    {
        "__init__.py",
        "comparison_evidence.py",
        "comparison_mode.py",
        "dependencies.py",
        "execution.py",
        "execution_types.py",
        "executor.py",
        "input_adapter.py",
        "input_types.py",
        "source_adapter.py",
    }
)
CLINICAL_AGGREGATE_ARTIFACT_EVIDENCE_COMPARISON = (
    BACKEND_ROOT
    / "artifacts"
    / "evidence_comparison"
    / "clinical_trial_doc"
    / "clinical_safety"
    / "aggregate_evidence"
)
PIPELINE_EVIDENCE_COMPARISON = (
    BACKEND_ROOT / "steps" / "evidence_comparison.py"
)
RUNTIME_EVIDENCE_COMPARISON = (
    BACKEND_ROOT / "runtime" / "evidence_comparison_stage.py"
)

# -- Forbidden imports -----------------------------------------------------------

FORBIDDEN_CORE_IMPORTS = (
    "plugins.clinical_trial_doc",
    "artifacts.evidence_comparison",
    "runtime",
    "scripts.stage_runners",
)

FORBIDDEN_ARTIFACT_IMPORTS = (
    "plugins.evidence_comparison",
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence",
    "runtime",
    "scripts.stage_runners",
)


def _iter_py_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _neutral_comparison_files() -> list[Path]:
    files = sorted(OPERATIONS_EVIDENCE_COMPARISON.glob("*.py"))
    files.extend(
        path
        for path in (PIPELINE_EVIDENCE_COMPARISON, RUNTIME_EVIDENCE_COMPARISON)
        if path.is_file()
    )
    return sorted(files)


def _source_without_forbidden_defs(source: str) -> str:
    """Remove _FORBIDDEN_* / _ALLOWED_* = frozenset(...) blocks so they don't trigger false positives."""
    return re.sub(
        r"_(?:FORBIDDEN|ALLOWED)_[A-Z_]+ = frozenset\(\s*\{(.*?)\}\s*\)",
        "",
        source,
        flags=re.DOTALL,
    )


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


# -- Materialized neutral skeleton ----------------------------------------------


def test_neutral_comparison_skeleton_is_materialized() -> None:
    files = _neutral_comparison_files()

    assert OPERATIONS_EVIDENCE_COMPARISON.is_dir()
    assert PIPELINE_EVIDENCE_COMPARISON.is_file()
    assert RUNTIME_EVIDENCE_COMPARISON.is_file()
    assert files


def test_generic_evidence_comparison_does_not_own_clinical_aggregate_working_representation() -> (
    None
):
    assert not (OPERATIONS_EVIDENCE_COMPARISON / "aggregate_evidence").exists()
    assert not LEGACY_PLUGIN_EVIDENCE_COMPARISON.exists()


def test_clinical_safety_aggregate_implementation_owns_working_representation() -> None:
    assert CLINICAL_AGGREGATE_PLUGIN_EVIDENCE_COMPARISON.is_dir()
    actual_root_files = {
        path.name
        for path in CLINICAL_AGGREGATE_PLUGIN_EVIDENCE_COMPARISON.iterdir()
        if path.is_file()
    }
    missing = REQUIRED_CLINICAL_AGGREGATE_PLUGIN_ROOT_MODULES - actual_root_files
    assert not missing, f"missing required plugin root modules: {sorted(missing)}"


def test_clinical_aggregate_artifact_namespace_reflects_concrete_scope() -> None:
    assert CLINICAL_AGGREGATE_ARTIFACT_EVIDENCE_COMPARISON.is_dir()
    assert {
        "__init__.py",
        "aggregate_comparison_evidence.py",
        "comparison_aliases.py",
        "final_findings.py",
        "findings.py",
    } == {
        path.name
        for path in CLINICAL_AGGREGATE_ARTIFACT_EVIDENCE_COMPARISON.iterdir()
        if path.is_file()
    }
    assert not (ARTIFACTS_EVIDENCE_COMPARISON / "aggregate_evidence").exists()


def test_only_source_adapter_imports_clinical_producer_not_working_representation() -> (
    None
):
    forbidden_import_prefixes = (
        "artifacts.evidence_source_preparation.clinical_trial_doc",
        "plugins.clinical_trial_doc.evidence_source_preparation",
    )
    forbidden_source_tokens = (
        "heading_scopes",
        "validate_aggregate_evidence_source_bundle",
    )
    working_representation_files = (
        CLINICAL_AGGREGATE_PLUGIN_EVIDENCE_COMPARISON / "input_types.py",
        CLINICAL_AGGREGATE_PLUGIN_EVIDENCE_COMPARISON / "input_adapter.py",
        CLINICAL_AGGREGATE_PLUGIN_EVIDENCE_COMPARISON / "comparison_evidence.py",
    )
    violations: list[str] = []

    for path in working_representation_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for imported in _imported_module_names(tree):
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden_import_prefixes
            ):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} imports {imported}"
                )
        for token in forbidden_source_tokens:
            if token in source:
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} contains {token!r}"
                )

    assert not violations, "\n".join(violations)


def test_neutral_comparison_skeleton_has_no_domain_semantic_leakage() -> None:
    forbidden_source_patterns = (
        r"clinical_safety",
        r"\bdsur\b",
        r"\bib\b",
        r"aggregate",
        r"comparison_strategy_id",
        r"comparison_session_id",
        r"evidence_form_id",
        r"artifact_type",
        r"content_id",
    )
    forbidden_import_prefixes = (
        "application",
        "artifacts",
        "plugins",
    )
    violations: list[str] = []

    for path in _neutral_comparison_files():
        source = path.read_text(encoding="utf-8")
        for pattern in forbidden_source_patterns:
            if re.search(pattern, source, flags=re.IGNORECASE):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} contains /{pattern}/"
                )
        tree = ast.parse(source, filename=str(path))
        for imported in _imported_module_names(tree):
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden_import_prefixes
            ):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} imports {imported}"
                )

    assert not violations, "\n".join(violations)


# -- Core boundary tests ---------------------------------------------------------


def test_core_scope_has_no_plugin_imports() -> None:
    violations: list[str] = []
    for path in _iter_py_files(CORE_EVIDENCE_COMPARISON):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_module_names(tree):
            for forbidden_prefix in FORBIDDEN_CORE_IMPORTS:
                if imported == forbidden_prefix or imported.startswith(
                    forbidden_prefix + "."
                ):
                    violations.append(
                        f"{path.relative_to(BACKEND_ROOT)} imports {imported}"
                    )
    assert not violations, "\n".join(violations)


def test_core_scope_has_no_artifact_imports() -> None:
    violations: list[str] = []
    for path in _iter_py_files(CORE_EVIDENCE_COMPARISON):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_module_names(tree):
            if imported.startswith("artifacts."):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} imports {imported}"
                )
    assert not violations, "\n".join(violations)


def test_core_scope_has_no_clinical_trial_symbols() -> None:
    forbidden = (
        "heading_scope",
        "zone_key",
        "aggregate_evidence",
        "statement_class_ids",
        "source_span",
        "clinical_trial_doc",
    )
    violations: list[str] = []
    for path in _iter_py_files(CORE_EVIDENCE_COMPARISON):
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in source:
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} contains {token!r}"
                )
    assert not violations, "\n".join(violations)


# -- Artifact boundary tests -----------------------------------------------------


def test_artifact_has_no_plugin_imports() -> None:
    violations: list[str] = []
    for path in _iter_py_files(ARTIFACTS_EVIDENCE_COMPARISON):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_module_names(tree):
            for forbidden_prefix in FORBIDDEN_ARTIFACT_IMPORTS:
                if imported == forbidden_prefix or imported.startswith(
                    forbidden_prefix + "."
                ):
                    violations.append(
                        f"{path.relative_to(BACKEND_ROOT)} imports {imported}"
                    )
    assert not violations, "\n".join(violations)


def test_artifact_has_no_runtime_imports() -> None:
    violations: list[str] = []
    for path in _iter_py_files(ARTIFACTS_EVIDENCE_COMPARISON):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_module_names(tree):
            if imported == "runtime" or imported.startswith("runtime."):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} imports {imported}"
                )
    assert not violations, "\n".join(violations)


def test_clinical_aggregate_runtime_does_not_import_clinical_producer() -> None:
    forbidden_import_prefixes = (
        "artifacts.evidence_source_preparation.clinical_trial_doc",
        "plugins.clinical_trial_doc.evidence_source_preparation",
        (
            "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
            "aggregate_evidence.source_adapter"
        ),
    )
    forbidden_source_tokens = (
        "heading_scopes",
        "validate_aggregate_evidence_source_bundle",
        "adapt_clinical_safety_aggregate_source_bundle",
    )
    files = [
        path
        for path in AGGREGATE_RUNTIME_EVIDENCE_COMPARISON_PRODUCER_GUARD_FILES
        if path.is_file()
    ]
    violations: list[str] = []

    for path in files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for imported in _imported_module_names(tree):
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden_import_prefixes
            ):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} imports {imported}"
                )
        for token in forbidden_source_tokens:
            if token in source:
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} contains {token!r}"
                )

    assert not violations, "\n".join(violations)


def test_generic_comparison_does_not_import_clinical_aggregate_specialization() -> None:
    forbidden = (
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence"
    )
    violations: list[str] = []
    for path in _neutral_comparison_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_module_names(tree):
            if imported == forbidden or imported.startswith(forbidden + "."):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} imports {imported}"
                )
    assert not violations, "\n".join(violations)


def test_aggregate_runtime_does_not_implement_alias_generation() -> None:
    forbidden_tokens = (
        "scope_counter",
        "unit_counter",
        "sentence_counter",
        '"scope_alias"',
        '"unit_alias"',
        '"sentence_alias"',
    )
    violations: list[str] = []
    for path in AGGREGATE_RUNTIME_EVIDENCE_COMPARISON_FILES:
        source = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in source:
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} contains {token!r}"
                )
    assert not violations, "\n".join(violations)


# -- No comparison semantics -----------------------------------------------------


def test_artifact_has_no_comparison_semantics() -> None:
    forbidden_fields = (
        "comparison_topic",
        "comparison_group",
        "comparable",
        "comparison_dimensions",
        "comparison_rules",
        "finding",
        "outcome",
        "construction_profile_id",
        "evidence_items",
    )
    violations: list[str] = []
    for path in _iter_py_files(ARTIFACTS_EVIDENCE_COMPARISON):
        if CLINICAL_AGGREGATE_ARTIFACT_EVIDENCE_COMPARISON in path.parents:
            continue
        raw = path.read_text(encoding="utf-8")
        source = _source_without_forbidden_defs(raw)
        for token in forbidden_fields:
            if token in source:
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} contains {token!r}"
                )
    assert not violations, "\n".join(violations)


# -- No path/run fields in artifact ----------------------------------------------


def test_artifact_has_no_path_or_run_fields() -> None:
    forbidden = ("source_bundle_path", "classifications_path", "run_id", "run_dir")
    violations: list[str] = []
    for path in _iter_py_files(ARTIFACTS_EVIDENCE_COMPARISON):
        raw = path.read_text(encoding="utf-8")
        source = _source_without_forbidden_defs(raw)
        for token in forbidden:
            if token in source:
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} contains {token!r}"
                )
    assert not violations, "\n".join(violations)
