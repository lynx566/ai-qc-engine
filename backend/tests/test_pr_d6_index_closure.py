"""PR-D6 closure: canonical process run index coverage."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

RUN_INDEX_PATH = BACKEND_ROOT / "runtime" / "run_index.py"
AGGREGATE_EVIDENCE_OPERATIONS = (
    BACKEND_ROOT
    / "runtime"
    / "evidence_source_preparation"
    / "clinical_trial_doc"
    / "clinical_safety"
    / "aggregate_evidence"
    / "operations.py"
)

ACTIVE_INDEX_BUILDERS = (
    "build_aggregate_evidence_assess_index_document",
)

FORBIDDEN_TAG_INDEX_BUILDERS = (
    "build_tag_prepare_index_document",
    "build_tag_index_document",
    "build_match_candidate_select_index_document",
    "build_match_group_context_index_document",
    "build_match_link_context_groups_index_document",
)

FORBIDDEN_LEGACY_INDEX_FILENAMES = (
    "tag_output.json",
    "compare_candidates.json",
    "group_members.json",
)

BUILDER_CALLERS: dict[str, Path] = {
    "build_aggregate_evidence_assess_index_document": AGGREGATE_EVIDENCE_OPERATIONS,
}


def _defined_functions(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def _referenced_names(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


@pytest.mark.parametrize("builder_name", ACTIVE_INDEX_BUILDERS)
def test_active_index_builders_are_defined(builder_name: str) -> None:
    defined = _defined_functions(RUN_INDEX_PATH)
    assert builder_name in defined


@pytest.mark.parametrize("builder_name", FORBIDDEN_TAG_INDEX_BUILDERS)
def test_legacy_tag_index_builders_are_not_defined(builder_name: str) -> None:
    defined = _defined_functions(RUN_INDEX_PATH)
    assert builder_name not in defined


@pytest.mark.parametrize("builder_name", ACTIVE_INDEX_BUILDERS)
def test_active_index_builders_have_production_caller(builder_name: str) -> None:
    caller = BUILDER_CALLERS[builder_name]
    assert caller.is_file()
    referenced = _referenced_names(caller)
    assert builder_name in referenced, f"{builder_name} must be referenced from {caller.name}"


def test_aggregate_evidence_assess_operation_writes_run_index() -> None:
    text = AGGREGATE_EVIDENCE_OPERATIONS.read_text(encoding="utf-8")
    assert "write_run_index" in text
    assert "EVIDENCE_SOURCE_PREPARATION_ASSESS_STEP" in text


@pytest.mark.parametrize("legacy_filename", FORBIDDEN_LEGACY_INDEX_FILENAMES)
def test_run_index_module_has_no_legacy_artifact_filenames(legacy_filename: str) -> None:
    text = RUN_INDEX_PATH.read_text(encoding="utf-8")
    assert legacy_filename not in text
