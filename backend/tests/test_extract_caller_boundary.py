"""Import boundary guards for Extract caller direction (PR A.1).

Production/dev executable code must reach Extract through Runtime, never by
importing the canonical Pipeline Step directly. Only
``runtime/extract/operations.py`` is the canonical executable caller of the
Extract Step.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

EXTRACT_STEP = "steps.extract"
EXECUTION_FLOW_ROOT = BACKEND_ROOT / "execution_flow"
PROCESSING_LAUNCH_PATH = EXECUTION_FLOW_ROOT / "processing_launch.py"
DOCUMENT_PROCESSING_SEQUENCE_PATH = (
    EXECUTION_FLOW_ROOT / "document_processing_sequence.py"
)

DEV_CALLER_PATHS = (
    BACKEND_ROOT / "scripts" / "stage_runners" / "extract_runner.py",
    BACKEND_ROOT / "scripts" / "stage_runners" / "extract_reports.py",
    BACKEND_ROOT / "scripts" / "stage_runners" / "prepare_analysis_runner.py",
)

FORBIDDEN_DEV_EXTRACT_TOKENS = (
    "bootstrap_processing_identity_from_path",
    'extract_config_id="docx"',
    "extract_config_id='docx'",
    "resolve_extract_strategy",
    "extract_docx_document",
    "run_extract_step",
    "launch_document_processing_from_source_file",
)

RUNTIME_OPS = BACKEND_ROOT / "runtime" / "extract" / "operations.py"


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


def test_dev_callers_do_not_import_extract_step() -> None:
    violations: list[str] = []
    for path in DEV_CALLER_PATHS:
        imported = _imported_module_names(_parse(path))
        if any(
            name == EXTRACT_STEP or name.startswith(f"{EXTRACT_STEP}.")
            for name in imported
        ):
            violations.append(
                f"{path.relative_to(BACKEND_ROOT)} imports {EXTRACT_STEP}"
            )
    assert not violations, "\n".join(violations)


def test_dev_callers_do_not_reference_run_extract_step() -> None:
    violations: list[str] = []
    for path in DEV_CALLER_PATHS:
        if "run_extract_step" in path.read_text(encoding="utf-8"):
            violations.append(
                f"{path.relative_to(BACKEND_ROOT)} references run_extract_step"
            )
    assert not violations, "\n".join(violations)


def test_dev_extract_callers_do_not_use_forbidden_shortcuts() -> None:
    extract_dev_paths = (
        BACKEND_ROOT / "scripts" / "stage_runners" / "extract_runner.py",
        BACKEND_ROOT / "scripts" / "stage_runners" / "extract_reports.py",
    )
    violations: list[str] = []
    for path in extract_dev_paths:
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_DEV_EXTRACT_TOKENS:
            if token in source:
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)} references {token!r}"
                )
    assert not violations, "\n".join(violations)


def test_dev_extract_callers_use_shared_intake_launch_extract_sequence() -> None:
    extract_dev_paths = (
        BACKEND_ROOT / "scripts" / "stage_runners" / "extract_runner.py",
        BACKEND_ROOT / "scripts" / "stage_runners" / "extract_reports.py",
    )
    for path in extract_dev_paths:
        source = path.read_text(encoding="utf-8")
        assert "resolve_installed_extract_config_id" in source, (
            f"{path.relative_to(BACKEND_ROOT)} must resolve installed extract_config_id"
        )
        assert "run_document_processing_intake_launch_extract" in source, (
            f"{path.relative_to(BACKEND_ROOT)} must use shared intake/launch/extract sequence"
        )
        assert "run_request_file_intake_operation" not in source, (
            f"{path.relative_to(BACKEND_ROOT)} must not orchestrate intake directly"
        )
        assert "launch_document_processing_from_intake" not in source, (
            f"{path.relative_to(BACKEND_ROOT)} must not launch directly"
        )
        assert "run_extract_operation" not in source, (
            f"{path.relative_to(BACKEND_ROOT)} must not call extract runtime directly"
        )


def test_launch_from_source_file_is_retired() -> None:
    scanned_roots = (
        EXECUTION_FLOW_ROOT,
        BACKEND_ROOT / "scripts",
        BACKEND_ROOT / "application",
        BACKEND_ROOT / "runtime",
    )
    repo_violations: list[str] = []
    for root in scanned_roots:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "launch_document_processing_from_source_file" in source:
                repo_violations.append(path.relative_to(BACKEND_ROOT).as_posix())
    assert not repo_violations, "\n".join(repo_violations)


def test_sequence_module_owns_intake_launch_extract_order() -> None:
    source = DOCUMENT_PROCESSING_SEQUENCE_PATH.read_text(encoding="utf-8")
    fn = source.split("def run_document_processing_intake_launch_extract", 1)[1]
    intake_pos = fn.index("run_request_file_intake_operation(")
    launch_pos = fn.index("launch_document_processing_from_intake(")
    extract_pos = fn.index("run_extract_operation(")
    assert intake_pos < launch_pos < extract_pos


def test_runtime_extract_operations_is_canonical_step_caller() -> None:
    imported = _imported_module_names(_parse(RUNTIME_OPS))
    assert EXTRACT_STEP in imported
