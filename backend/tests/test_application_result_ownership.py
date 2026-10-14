"""Keep clinical Result interpretation out of the Flow application package."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

from application.document_consistency_qc.finding_review import (
    load_finding_review_state,
    persist_finding_review_entry,
    resolve_finding_review_state_path,
)


def test_flow_application_has_no_clinical_result_dependencies() -> None:
    flow_application = Path(__file__).resolve().parents[1] / "application" / "document_consistency_qc"
    forbidden_modules = {
        "result_read.py",
        "result_read_model.py",
        "result_readiness.py",
    }
    assert forbidden_modules.isdisjoint(path.name for path in flow_application.glob("*.py"))

    for path in flow_application.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        from_imports = (
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        direct_imports = (
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        for module in (*from_imports, *direct_imports):
            assert not module.startswith("application.clinical_trial_doc_consistency_qc"), path
            assert not module.startswith("plugins.clinical_trial_doc"), path
            assert not module.startswith("artifacts.evidence_comparison.clinical_trial_doc"), path
            assert not module.startswith("artifacts.evidence_source_preparation.clinical_trial_doc"), path
        literals = {
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert literals.isdisjoint({"internal_dsur", "internal_ib", "internal_csr"}), path


def test_flow_review_persistence_does_not_require_a_clinical_result(tmp_path: Path) -> None:
    with patch(
        "application.document_consistency_qc.finding_review.resolve_flow_run_output_dir",
        return_value=tmp_path,
    ):
        saved = persist_finding_review_entry(
            project_root=tmp_path,
            flow_run_id="document_consistency_qc_test",
            finding_id="L001",
            marked=True,
        )
        loaded = load_finding_review_state(
            project_root=tmp_path, flow_run_id="document_consistency_qc_test",
        )

    assert saved == loaded
    assert saved.findings[0].marked is True
    assert resolve_finding_review_state_path(flow_root=tmp_path).is_file()
