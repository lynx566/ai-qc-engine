"""Application installation guards for Route semantic-module sequence."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from application.clinical_trial_doc_consistency_qc.route_semantic_module_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE,
    validate_route_semantic_module_sequence,
)

INSTALLATION_PATH = (
    BACKEND_ROOT
    / "application"
    / "clinical_trial_doc_consistency_qc"
    / "route_semantic_module_installation.py"
)

UNINSTALLED_MODULES = (
    "efficacy",
    "pharmacokinetics",
    "nonclinical",
    "drug_information",
    "shared_context",
    "other",
)


def test_clinical_safety_is_the_only_installed_route_semantic_module() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    assert composition.route_semantic_module_sequence == (
        CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
    )
    assert composition.is_route_semantic_module_enabled(CLINICAL_SAFETY_SEMANTIC_MODULE_ID)
    assert len(composition.route_semantic_module_sequence) == 1


@pytest.mark.parametrize("semantic_module_id", UNINSTALLED_MODULES)
def test_uninstalled_semantic_modules_are_not_enabled_for_route(
    semantic_module_id: str,
) -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    assert not composition.is_route_semantic_module_enabled(semantic_module_id)


def test_duplicate_route_semantic_module_installation_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate installed Route semantic module"):
        validate_route_semantic_module_sequence(
            (
                CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
                CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
            )
        )


def test_route_semantic_module_installation_has_no_forbidden_imports() -> None:
    forbidden = ("runtime", "operations.flow", "openai", "bailian")
    tree = ast.parse(INSTALLATION_PATH.read_text(encoding="utf-8"), filename=str(INSTALLATION_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for token in forbidden:
                    assert token not in alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for token in forbidden:
                assert token not in node.module


def test_installed_sequence_matches_composition() -> None:
    assert INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE == (
        CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
    )
