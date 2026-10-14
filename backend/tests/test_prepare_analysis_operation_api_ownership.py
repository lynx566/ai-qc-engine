"""Structural ownership guards for the neutral Prepare Analysis operation API."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.prepare_analysis import (
    DuplicatePrepareAnalysisConfigError,
    PrepareAnalysisConfig,
    PrepareAnalysisConfigId,
    PrepareAnalysisConfigRegistry,
    PrepareAnalysisDomainConfiguration,
    PrepareAnalysisDomainResolver,
    PrepareAnalysisPrivacyConfiguration,
    PrepareAnalysisRequestOptions,
    ResolvedPrepareAnalysisPlan,
    UnknownPrepareAnalysisConfigError,
)

OPERATION_API_ROOT = BACKEND_ROOT / "operations" / "prepare_analysis"
OLD_PACKAGE_ROOT = BACKEND_ROOT / "prepare_analysis"
FORBIDDEN_DEPENDENCY_PREFIXES = (
    "execution_flow",
    "plugins.clinical_trial_doc",
    "runtime",
    "scripts",
)


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_old_prepare_analysis_package_is_removed() -> None:
    assert not OLD_PACKAGE_ROOT.exists()


def test_prepare_analysis_public_api_is_importable_from_operations() -> None:
    public_symbols = (
        DuplicatePrepareAnalysisConfigError,
        PrepareAnalysisConfig,
        PrepareAnalysisConfigId,
        PrepareAnalysisConfigRegistry,
        PrepareAnalysisDomainConfiguration,
        PrepareAnalysisDomainResolver,
        PrepareAnalysisPrivacyConfiguration,
        PrepareAnalysisRequestOptions,
        ResolvedPrepareAnalysisPlan,
        UnknownPrepareAnalysisConfigError,
    )
    assert all(
        symbol.__module__.startswith("operations.prepare_analysis")
        for symbol in public_symbols
    )


def test_prepare_operation_api_has_no_execution_or_domain_dependency() -> None:
    violations: list[str] = []
    for path in sorted(OPERATION_API_ROOT.rglob("*.py")):
        for imported in _imported_module_names(path):
            for forbidden in FORBIDDEN_DEPENDENCY_PREFIXES:
                if imported == forbidden or imported.startswith(f"{forbidden}."):
                    relative = path.relative_to(BACKEND_ROOT).as_posix()
                    violations.append(f"{relative} imports {imported}")
    assert not violations, "forbidden operation API imports:\n" + "\n".join(violations)


def test_repository_python_imports_do_not_use_old_prepare_root() -> None:
    violations: list[str] = []
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        for imported in _imported_module_names(path):
            if imported == "prepare_analysis" or imported.startswith(
                "prepare_analysis."
            ):
                relative = path.relative_to(BACKEND_ROOT).as_posix()
                violations.append(f"{relative} imports {imported}")
    assert not violations, "stale Prepare API imports:\n" + "\n".join(violations)
