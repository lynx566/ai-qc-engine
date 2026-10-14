"""Import boundary guards for execution flow."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

EXECUTION_FLOW_ROOT = BACKEND_ROOT / "execution_flow"
DOCUMENT_PROCESSING_SEQUENCE_PATH = (
    EXECUTION_FLOW_ROOT / "document_processing_sequence.py"
)

FORBIDDEN_DOCUMENT_PROCESSING_SEQUENCE_IMPORTS = (
    "execution_flow.document_consistency_qc.execution_provenance",
    "execution_flow.document_consistency_qc.flow",
)

FORBIDDEN_DOCUMENT_PROCESSING_SEQUENCE_TOKENS = (
    "FlowRunSlotProvenance",
    "FlowRunExecution",
    "slot_provenance",
    "provenance_dict",
)

ON_INTAKE_LAUNCHED_CALLABLE_CONTRACT = (
    "Callable[[RequestFileIntakeOperationReport, ExtractDocumentInput], None]"
)

FORBIDDEN_EXECUTION_FLOW_IMPORTS = (
    "steps",
    "runtime.document_processing_bootstrap",
    "scripts.stage_runners",
    "scripts.stage_runners.extract_reports",
    "capability",
    "core.document.docx",
    "core.document.extract",
)


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


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


def test_execution_flow_modules_do_not_import_forbidden_modules() -> None:
    violations: list[str] = []
    for path in sorted(EXECUTION_FLOW_ROOT.rglob("*.py")):
        imported = _imported_module_names(_parse(path))
        for module in imported:
            for forbidden in FORBIDDEN_EXECUTION_FLOW_IMPORTS:
                if module == forbidden or module.startswith(f"{forbidden}."):
                    violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {module}")
    assert not violations, "forbidden imports in execution flow:\n" + "\n".join(violations)


def test_flow_module_has_no_flow_persistence_helpers() -> None:
    flow_path = EXECUTION_FLOW_ROOT / "document_consistency_qc" / "flow.py"
    source = flow_path.read_text(encoding="utf-8")
    for token in (
        "runs/execution_flow",
        "runs/consistency_qc",
        "execution_flow_result.json",
        "consistency_qc_request.json",
        "write_run_index",
        "save_json",
    ):
        assert token not in source


def test_processing_blocks_package_removed() -> None:
    assert not (BACKEND_ROOT / "processing_blocks").is_dir()


def test_document_branch_module_removed() -> None:
    assert not (EXECUTION_FLOW_ROOT / "document_branch.py").is_file()


def test_document_consistency_qc_product_namespace() -> None:
    """QC orchestration lives under the explicit product subpackage."""
    from execution_flow.document_consistency_qc import run_document_consistency_qc_flow

    assert callable(run_document_consistency_qc_flow)
    assert not (EXECUTION_FLOW_ROOT / "flow.py").is_file()
    assert not (EXECUTION_FLOW_ROOT / "contracts.py").is_file()
    assert not (EXECUTION_FLOW_ROOT / "execution_provenance.py").is_file()
    assert (EXECUTION_FLOW_ROOT / "document_consistency_qc" / "flow.py").is_file()
    assert (EXECUTION_FLOW_ROOT / "processing_launch.py").is_file()


def test_document_processing_sequence_has_no_qc_consumer_coupling() -> None:
    assert DOCUMENT_PROCESSING_SEQUENCE_PATH.is_file()
    imported = _imported_module_names(_parse(DOCUMENT_PROCESSING_SEQUENCE_PATH))
    violations: list[str] = []
    for module in imported:
        for forbidden in FORBIDDEN_DOCUMENT_PROCESSING_SEQUENCE_IMPORTS:
            if module == forbidden or module.startswith(f"{forbidden}."):
                violations.append(
                    f"document_processing_sequence imports {module}"
                )
    assert not violations, "\n".join(violations)

    source = DOCUMENT_PROCESSING_SEQUENCE_PATH.read_text(encoding="utf-8")
    token_violations = [
        token
        for token in FORBIDDEN_DOCUMENT_PROCESSING_SEQUENCE_TOKENS
        if token in source
    ]
    assert not token_violations, (
        "document_processing_sequence must not reference QC consumer types: "
        + ", ".join(token_violations)
    )


def test_document_processing_sequence_on_intake_launched_lifecycle_contract() -> None:
    source = DOCUMENT_PROCESSING_SEQUENCE_PATH.read_text(encoding="utf-8")
    assert ON_INTAKE_LAUNCHED_CALLABLE_CONTRACT in source
    assert "on_intake_launched(intake_report, launched_document)" in source


def test_comparison_profiles_package_removed() -> None:
    profiles_root = (
        BACKEND_ROOT
        / "plugins"
        / "clinical_trial_doc"
        / "consistency_qc"
        / "comparison_profiles"
    )
    assert not profiles_root.is_dir()
