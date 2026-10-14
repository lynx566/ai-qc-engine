"""Import boundary guards for aggregate prepare processor ownership migration."""

# ruff: noqa: SIM102
from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

ARTIFACTS_ROOT = BACKEND_ROOT / "artifacts"
PLUGIN_PREPARE_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "clinical_safety"
    / "aggregate_evidence"
)

FORBIDDEN_ARTIFACT_IMPORT_PREFIXES = (
    "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation",
    "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.prepare",
)

FORBIDDEN_PLUGIN_PREPARE_IMPORT_PREFIXES = (
    "runtime",
    "runtime.",
    "scripts.stage_runners",
    "scripts.stage_runners.",
    "scripts.dev",
    "scripts.dev.",
    "artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input",
    "artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact",
)

FORBIDDEN_PLUGIN_PREPARE_SOURCE_TOKENS = (
    "clinical_safety_aggregate_heading_scope_assessment_zh",
    "DEFAULT_AGGREGATE_ASSESSMENT_PROFILE_REF",
    "DEFAULT_INSTRUCTIONS",
)

FORBIDDEN_ARTIFACT_AGGREGATE_SEMANTIC_SYMBOLS = frozenset(
    {
        "_canonicalize_aggregate_route_units",
        "build_heading_scopes_from_aggregate_units",
        "compact_sentences_from_aggregate_unit",
        "attach_assessment_evidence_to_heading_scopes",
        "build_scope_candidate_text",
        "unit_provenance_from_aggregate_unit",
    }
)

FORBIDDEN_PLUGIN_IO_SYMBOLS = frozenset(
    {
        "load_json",
        "save_json",
        "mkdir",
        "write_text",
        "read_text",
    }
)


def _iter_py_files(root: Path) -> list[Path]:
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


def _defined_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def test_artifact_modules_do_not_import_aggregate_prepare_plugin() -> None:
    violations: list[str] = []
    for path in _iter_py_files(ARTIFACTS_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_module_names(tree):
            if any(
                imported == prefix.rstrip(".") or imported.startswith(prefix)
                for prefix in FORBIDDEN_ARTIFACT_IMPORT_PREFIXES
            ):
                violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_artifact_modules_do_not_define_aggregate_semantic_symbols() -> None:
    violations: list[str] = []
    for path in _iter_py_files(ARTIFACTS_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        overlap = sorted(_defined_names(tree) & FORBIDDEN_ARTIFACT_AGGREGATE_SEMANTIC_SYMBOLS)
        if overlap:
            violations.append(
                f"{path.relative_to(BACKEND_ROOT)} defines forbidden symbols: {overlap}"
            )
    assert not violations, "\n".join(violations)


def test_plugin_prepare_modules_do_not_import_runtime_or_artifact_builders() -> None:
    violations: list[str] = []
    for filename in ("prepare.py", "preparation.py"):
        path = PLUGIN_PREPARE_ROOT / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_module_names(tree):
            if any(
                imported == prefix.rstrip(".") or imported.startswith(prefix)
                for prefix in FORBIDDEN_PLUGIN_PREPARE_IMPORT_PREFIXES
            ):
                violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_plugin_prepare_modules_do_not_import_legacy_per_unit_prompt() -> None:
    forbidden_tokens = (
        "tagging.prompts._legacy",
        "clinical_safety_aggregate_finding_zh_tagging",
        "DEFAULT_TAG_INSTRUCTIONS",
    )
    violations: list[str] = []
    for filename in ("prepare.py", "preparation.py"):
        source = (PLUGIN_PREPARE_ROOT / filename).read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in source:
                violations.append(f"{filename} contains {token!r}")
    assert not violations, "\n".join(violations)


def test_plugin_prepare_modules_do_not_import_clinical_safety_prompt_defaults() -> None:
    violations: list[str] = []
    for filename in ("prepare.py", "preparation.py"):
        source = (PLUGIN_PREPARE_ROOT / filename).read_text(encoding="utf-8")
        for token in FORBIDDEN_PLUGIN_PREPARE_SOURCE_TOKENS:
            if token in source:
                violations.append(f"{filename} contains forbidden token {token!r}")
    assert not violations, "\n".join(violations)


def test_clinical_safety_semantic_binding_owns_prepare_defaults() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
        DEFAULT_AGGREGATE_HEADING_SCOPE_ASSESSMENT_INSTRUCTIONS,
    )
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
        CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING,
    )

    assert (
        CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.instructions
        == DEFAULT_AGGREGATE_HEADING_SCOPE_ASSESSMENT_INSTRUCTIONS
    )
    assert (
        CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.assessment_profile_ref
        == "clinical_safety_aggregate_heading_scope_assessment_zh"
    )


def test_plugin_prepare_modules_have_no_file_io_symbols() -> None:
    violations: list[str] = []
    for filename in ("prepare.py", "preparation.py"):
        path = PLUGIN_PREPARE_ROOT / filename
        source = path.read_text(encoding="utf-8")
        if "open(" in source:
            violations.append(f"{path.relative_to(BACKEND_ROOT)} uses open(")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in FORBIDDEN_PLUGIN_IO_SYMBOLS:
                    violations.append(
                        f"{path.relative_to(BACKEND_ROOT)} calls {func.id}()"
                    )
                if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_PLUGIN_IO_SYMBOLS:
                    violations.append(
                        f"{path.relative_to(BACKEND_ROOT)} calls .{func.attr}()"
                    )
    assert not violations, "\n".join(violations)
