"""Import boundary guards for Prepare Analysis executable caller direction."""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from runtime.prepare_analysis.operations import run_prepare_analysis_operation

PREPARE_ANALYSIS_RUNTIME_ROOT = BACKEND_ROOT / "runtime" / "prepare_analysis"
PREPARE_ANALYSIS_RUNNER = (
    BACKEND_ROOT / "scripts" / "stage_runners" / "prepare_analysis_runner.py"
)
PREPARE_ANALYSIS_OPERATIONS = PREPARE_ANALYSIS_RUNTIME_ROOT / "operations.py"

FORBIDDEN_RUNTIME_IMPORT_PREFIXES = (
    "runtime.extract",
    "runtime.document_processing_bootstrap",
    "steps.extract",
)

FORBIDDEN_RUNTIME_TOKENS = (
    "bootstrap_processing_identity_from_path",
    "run_extract_operation",
    "ExtractDocumentInput",
    'extract_config_id="docx"',
    "extract_config_id='docx'",
    "source_path",
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


def test_prepare_analysis_runtime_package_has_no_extract_dependencies() -> None:
    violations: list[str] = []
    for path in sorted(PREPARE_ANALYSIS_RUNTIME_ROOT.rglob("*.py")):
        imported = _imported_module_names(_parse(path))
        relative = path.relative_to(BACKEND_ROOT).as_posix()
        for module_name in imported:
            for forbidden in FORBIDDEN_RUNTIME_IMPORT_PREFIXES:
                if module_name == forbidden or module_name.startswith(
                    f"{forbidden}."
                ):
                    violations.append(f"{relative} imports {module_name}")
    assert not violations, "\n".join(violations)


def test_prepare_analysis_operations_has_no_extract_shortcut_tokens() -> None:
    source = PREPARE_ANALYSIS_OPERATIONS.read_text(encoding="utf-8")
    violations = [
        token
        for token in FORBIDDEN_RUNTIME_TOKENS
        if token in source
    ]
    assert not violations, violations


def test_prepare_analysis_runner_has_no_file_or_extract_shortcuts() -> None:
    source = PREPARE_ANALYSIS_RUNNER.read_text(encoding="utf-8")
    assert '--file' not in source
    assert "source_path" not in source
    for token in FORBIDDEN_RUNTIME_TOKENS:
        assert token not in source, token


def test_run_prepare_analysis_operation_accepts_only_bundle_inputs() -> None:
    params = inspect.signature(run_prepare_analysis_operation).parameters
    assert "source_path" not in params
    assert "bundle" in params
    assert "bundle_path" in params
    assert "bundle_dir" in params
