"""PR-D5 closure: deprecated tag runner wrappers removed."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

RUNNER_ROOT = BACKEND_ROOT / "scripts" / "stage_runners"

REMOVED_TAG_RUNNER_FILES = (
    "tag_prepare_runner.py",
    "tag_runner.py",
)

CANONICAL_RUNNER_FILES = (
    "evidence_source_preparation/aggregate_evidence/prepare_runner.py",
    "evidence_source_preparation/aggregate_evidence/assess_runner.py",
)

RETIRED_ROOT_AGGREGATE_RUNNER_FILES = (
    "process_prepare_runner.py",
    "process_assess_runner.py",
    "process_eligibility_runner.py",
    "process_assemble_runner.py",
)

FORBIDDEN_TAG_RUNNER_IMPORTS = (
    "scripts.stage_runners.tag_prepare_runner",
    "scripts.stage_runners.tag_runner",
)

RUNTIME_ROOT = BACKEND_ROOT / "runtime"
FORBIDDEN_RUNTIME_RUNNER_IMPORT_PREFIXES = (
    "scripts.stage_runners",
)

def _python_source_paths() -> list[Path]:
    roots = (
        BACKEND_ROOT / "steps",
        BACKEND_ROOT / "runtime",
        BACKEND_ROOT / "scripts",
        BACKEND_ROOT / "tests",
    )
    paths: list[Path] = []
    for root in roots:
        if root.is_file():
            paths.append(root)
            continue
        paths.extend(sorted(root.rglob("*.py")))
    return paths


def _imported_modules(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
    return modules


def _runtime_python_source_paths() -> list[Path]:
    return sorted(RUNTIME_ROOT.rglob("*.py"))


def _runtime_runner_import_offenders() -> list[str]:
    offenders: list[str] = []
    for source_path in _runtime_python_source_paths():
        for module_name in _imported_modules(source_path):
            if any(
                module_name == prefix or module_name.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_RUNTIME_RUNNER_IMPORT_PREFIXES
            ):
                rel = str(source_path.relative_to(BACKEND_ROOT))
                if rel not in offenders:
                    offenders.append(rel)
    return offenders


@pytest.mark.parametrize("filename", REMOVED_TAG_RUNNER_FILES)
def test_deprecated_tag_runner_files_are_removed(filename: str) -> None:
    assert not (RUNNER_ROOT / filename).exists(), f"{filename} must be deleted"


@pytest.mark.parametrize("filename", CANONICAL_RUNNER_FILES)
def test_canonical_runner_files_exist(filename: str) -> None:
    assert (RUNNER_ROOT / filename).is_file(), f"{filename} must remain"


@pytest.mark.parametrize("filename", RETIRED_ROOT_AGGREGATE_RUNNER_FILES)
def test_false_generic_root_aggregate_runner_files_are_removed(filename: str) -> None:
    assert not (RUNNER_ROOT / filename).exists(), f"{filename} must be deleted"


def test_runtime_modules_do_not_import_scripts_runner() -> None:
    offenders = _runtime_runner_import_offenders()
    assert not offenders, f"runtime must not import scripts.stage_runners: {offenders}"


@pytest.mark.parametrize("module_name", FORBIDDEN_TAG_RUNNER_IMPORTS)
def test_python_sources_do_not_import_removed_tag_runners(module_name: str) -> None:
    offenders: list[str] = []
    for source_path in _python_source_paths():
        if source_path.name == Path(__file__).name:
            continue
        if module_name in _imported_modules(source_path):
            offenders.append(str(source_path.relative_to(BACKEND_ROOT)))
        text = source_path.read_text(encoding="utf-8")
        if f"from scripts.stage_runners import" in text and module_name.split(".")[-1] in text:
            # Catch `from scripts.stage_runners import tag_runner` style imports.
            tree = ast.parse(text, filename=str(source_path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module != "scripts.stage_runners":
                    continue
                for alias in node.names:
                    if alias.name in {"tag_prepare_runner", "tag_runner"}:
                        rel = str(source_path.relative_to(BACKEND_ROOT))
                        if rel not in offenders:
                            offenders.append(rel)
    assert not offenders, f"{module_name} still imported from: {offenders}"
