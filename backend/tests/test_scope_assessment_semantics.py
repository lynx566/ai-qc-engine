"""Tests for plugin-owned scope assessment semantic normalization."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.scope_assessment_semantics import (
    DEFAULT_ROUTE_QC,
    resolve_annotation_qc_fields,
    resolve_product_context_role,
    resolve_route_qc,
    resolve_safety_role,
    resolve_unit_form,
)

CANONICAL_ESP_PLUGIN_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "clinical_safety"
    / "aggregate_evidence"
)

FORBIDDEN_CORE_TAGGING_IMPORTS = (
    "core.tagging",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_resolve_product_context_role_accepts_known_enum() -> None:
    role, flags = resolve_product_context_role("target_study_drug")
    assert role == "target_study_drug"
    assert flags == []


def test_resolve_product_context_role_falls_back_to_unknown() -> None:
    role, flags = resolve_product_context_role("not_a_real_role")
    assert role == "unknown"
    assert flags == ["invalid_product_context_role"]


def test_resolve_product_context_role_none_falls_back_to_unknown() -> None:
    role, flags = resolve_product_context_role(None)
    assert role == "unknown"
    assert flags == ["invalid_product_context_role"]


def test_resolve_unit_form_invalid_falls_back_to_unknown() -> None:
    unit_form, flags = resolve_unit_form("bad_form")
    assert unit_form == "unknown"
    assert flags == ["invalid_unit_form"]


@pytest.mark.parametrize(
    ("legacy_token", "canonical", "flag"),
    [
        ("exclude", "not_applicable", "safety_role_legacy_exclude_to_not_applicable"),
        ("route_qc_only", "unknown", "safety_role_legacy_route_qc_only_to_unknown"),
        (
            "safety_context_exposure",
            "safety_context",
            "safety_role_legacy_context_variant_to_safety_context",
        ),
    ],
)
def test_resolve_safety_role_legacy_alias_mapping(
    legacy_token: str,
    canonical: str,
    flag: str,
) -> None:
    safety_role, flags = resolve_safety_role(legacy_token)
    assert safety_role == canonical
    assert flags == [flag]


def test_resolve_safety_role_invalid_falls_back_to_unknown() -> None:
    safety_role, flags = resolve_safety_role("not_a_role")
    assert safety_role == "unknown"
    assert flags == ["invalid_safety_role"]


def test_resolve_route_qc_missing_returns_default() -> None:
    route_qc, flags = resolve_route_qc(None)
    assert route_qc == DEFAULT_ROUTE_QC
    assert flags == ["missing_route_qc"]


def test_resolve_route_qc_invalid_suggested_route_coerces_unknown() -> None:
    route_qc, flags = resolve_route_qc(
        {"route_mismatch": True, "suggested_route": "bad_route", "reason": "x"}
    )
    assert route_qc["suggested_route"] == "unknown"
    assert "invalid_suggested_route" in flags


def test_resolve_annotation_qc_fields_composes_qc_resolvers() -> None:
    llm_item = {
        "unit_form": "aggregate",
        "safety_role": "exclude",
        "route_qc": {"route_mismatch": True, "suggested_route": "case", "reason": "x"},
    }
    result = resolve_annotation_qc_fields(llm_item)
    assert result.unit_form == "aggregate"
    assert result.safety_role == "not_applicable"
    assert result.route_qc == {
        "route_mismatch": True,
        "suggested_route": "case",
        "reason": "x",
    }
    assert result.validation_flags == (
        "safety_role_legacy_exclude_to_not_applicable",
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "scope_assess.py",
        "scope_assessment_adapter.py",
        "scope_assessment_semantics.py",
    ],
)
def test_canonical_esp_plugin_modules_do_not_import_core_tagging_semantics(
    relative_path: str,
) -> None:
    imported = _imported_modules(CANONICAL_ESP_PLUGIN_ROOT / relative_path)
    for forbidden in FORBIDDEN_CORE_TAGGING_IMPORTS:
        assert not any(
            name == forbidden or name.startswith(f"{forbidden}.")
            for name in imported
        ), f"{relative_path} imports {forbidden}"


def test_canonical_production_paths_have_zero_core_tagging_semantic_imports() -> None:
    scan_roots = [
        CANONICAL_ESP_PLUGIN_ROOT,
        BACKEND_ROOT
        / "runtime"
        / "evidence_source_preparation"
        / "clinical_trial_doc"
        / "clinical_safety"
        / "aggregate_evidence",
        BACKEND_ROOT
        / "artifacts"
        / "evidence_source_preparation"
        / "clinical_trial_doc"
        / "clinical_safety"
        / "aggregate_evidence",
    ]
    violations: list[str] = []
    for root in scan_roots:
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            imported = _imported_modules(path)
            for forbidden in FORBIDDEN_CORE_TAGGING_IMPORTS:
                if any(
                    name == forbidden or name.startswith(f"{forbidden}.")
                    for name in imported
                ):
                    violations.append(f"{rel} imports {forbidden}")
    assert not violations, "\n".join(violations)
