"""S4 caller-migration and legacy-retirement architecture guards."""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from steps.prepare_analysis import prepare_analysis_bundle
from runtime.prepare_analysis import run_prepare_analysis_operation
from runtime.prepare_analysis.operations import (
    run_prepare_analysis_operation as canonical_operation,
)


def _tree(relative: str) -> ast.AST:
    path = BACKEND_ROOT / relative
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_runtime_compatibility_ingress_is_deleted_and_facade_is_canonical() -> None:
    assert not (BACKEND_ROOT / "runtime/prepare_analysis/compatibility.py").exists()
    assert run_prepare_analysis_operation is canonical_operation


def test_retired_prepare_runtime_helpers_are_absent() -> None:
    for relative in (
        "runtime/privacy_run_config.py",
        "runtime/privacy_registry.py",
    ):
        assert not (BACKEND_ROOT / relative).exists()


def test_production_and_dev_code_has_no_legacy_runtime_reference() -> None:
    violations: list[str] = []
    for root_name in ("scripts", "runtime", "pipeline", "plugins"):
        root = BACKEND_ROOT / root_name
        paths = [root] if root.is_file() else root.rglob("*.py")
        for path in paths:
            source = path.read_text(encoding="utf-8")
            if "run_prepare_analysis_operation_legacy" in source:
                violations.append(str(path.relative_to(BACKEND_ROOT)))
            if "runtime.prepare_analysis.compatibility" in source:
                violations.append(str(path.relative_to(BACKEND_ROOT)))
            if "build_privacy_run_config" in source:
                violations.append(str(path.relative_to(BACKEND_ROOT)))
            if "resolve_privacy_profile_for_run" in source:
                violations.append(str(path.relative_to(BACKEND_ROOT)))
    assert not violations, violations


def test_all_standalone_callers_use_shared_composition_and_canonical_runtime() -> None:
    for relative in (
        "scripts/stage_runners/prepare_analysis_runner.py",
    ):
        tree = _tree(relative)
        imported = _imports(tree)
        assert "plugins.clinical_trial_doc.prepare_analysis" in imported
        assert "runtime.prepare_analysis" in imported


def test_standalone_adapter_does_not_resolve_clinical_semantics() -> None:
    tree = _tree("plugins/clinical_trial_doc/prepare_analysis/standalone.py")
    imported = _imports(tree)
    assert not any("privacy.registry" in name for name in imported)
    assert not any("regex_rules" in name or "uie_schema" in name for name in imported)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not called_names.intersection(
        {
            "get_clinical_program",
            "export_clinical_registry_entries",
            "export_clinical_registry_entries_for_program",
            "resolve_prepare_analysis_date_shift_offset",
            "apply_prepare_analysis_privacy",
        }
    )


def test_old_clinical_prepare_privacy_facade_is_retired() -> None:
    tree = _tree("plugins/clinical_trial_doc/privacy/__init__.py")
    function_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    assert "apply_prepare_analysis_privacy" not in function_names
    assert "resolve_prepare_analysis_date_shift_offset" not in function_names


def test_prepare_cli_after_filter_surface_is_absent() -> None:
    source = (
        BACKEND_ROOT / "scripts/stage_runners/prepare_analysis_runner.py"
    ).read_text(encoding="utf-8")
    assert "privacy-after-filter-detectors" not in source
    assert "privacy_after_filter_detectors" not in source


def test_canonical_signatures_have_no_legacy_debug_flags() -> None:
    forbidden = {
        "privacy_profile",
        "privacy_profile_config",
        "privacy_detectors",
        "after_extract_detectors",
        "after_filter_detectors",
        "date_shift_explicit",
        "source_path",
    }
    assert not forbidden.intersection(inspect.signature(canonical_operation).parameters)
    assert not forbidden.intersection(
        inspect.signature(prepare_analysis_bundle).parameters
    )


def test_slice2_legacy_standalone_composition_symbols_are_retired() -> None:
    forbidden_fragments = (
        "for_legacy_profile",
        "privacy_profile_spec",
        "privacy_profile_name",
        "_DEBUG_CONFIG_ID",
        "standalone_custom_profile",
        "_load_debug_profile",
        "PrepareAnalysisRunContext",
        "resolve_prepare_analysis_run_context",
    )
    for relative in (
        "plugins/clinical_trial_doc/prepare_analysis/standalone.py",
        "plugins/clinical_trial_doc/prepare_analysis/resolver.py",
        "scripts/stage_runners/prepare_analysis_runner.py",
        "runtime/prepare_analysis/context.py",
    ):
        source = (BACKEND_ROOT / relative).read_text(encoding="utf-8")
        hits = [frag for frag in forbidden_fragments if frag in source]
        assert not hits, (relative, hits)


def test_standalone_invocation_rejects_legacy_profile_kwargs() -> None:
    from plugins.clinical_trial_doc.prepare_analysis import (
        build_clinical_prepare_analysis_standalone_invocation,
    )

    with pytest.raises(TypeError):
        build_clinical_prepare_analysis_standalone_invocation(
            clinical_program_id="clinical_program_001",
            bundle={"document_meta": {"language": "zh"}},
            privacy_profile_name="clinical_trial_doc",
        )
