"""Neutral Route output contract and consumer selection tests."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.routing.schema import ROUTED_UNITS_ROUTE_FILENAMES
from artifacts.routing.types import ROUTES
from operations.evidence_source_preparation.stage import RouteStageReference
from operations.projected_source_route.consumer_selection import (
    select_produced_route_output,
)
from operations.projected_source_route.output_contract import (
    RouteOutputDescriptor,
    build_produced_route_outputs,
    resolve_route_unit_count,
    route_unit_count_key,
)

CONSUMER_SELECTION_PATH = (
    BACKEND_ROOT
    / "operations"
    / "projected_source_route"
    / "consumer_selection.py"
)
OUTPUT_CONTRACT_PATH = (
    BACKEND_ROOT
    / "operations"
    / "projected_source_route"
    / "output_contract.py"
)


def _route_counts(
    *,
    counts_by_kind: dict[str, int],
) -> dict[str, int]:
    route_counts = {route_unit_count_key(route): 0 for route in ROUTES}
    for route_output_kind, unit_count in counts_by_kind.items():
        route_counts[route_unit_count_key(route_output_kind)] = unit_count
    route_counts["total_routed_unit_count"] = sum(
        route_counts[route_unit_count_key(route)] for route in ROUTES
    )
    return route_counts


def _routed_bundle_paths(output_dir: Path) -> dict[str, Path]:
    return {
        route: output_dir / ROUTED_UNITS_ROUTE_FILENAMES[route] for route in ROUTES
    }


def test_route_unit_count_key_uses_canonical_suffix() -> None:
    assert route_unit_count_key("table") == "table_unit_count"


def test_resolve_route_unit_count_prefers_suffixed_key() -> None:
    route_counts = {
        "table_unit_count": 2,
        "table": 99,
    }
    assert resolve_route_unit_count(route_counts, "table") == 2


def test_resolve_route_unit_count_accepts_manifest_style_key() -> None:
    route_counts = {
        "case": 3,
    }
    assert resolve_route_unit_count(route_counts, "case") == 3


def test_resolve_route_unit_count_returns_zero_for_missing_kind() -> None:
    assert resolve_route_unit_count({}, "unknown") == 0


def test_build_produced_route_outputs_uses_counts_not_file_existence(
    tmp_path: Path,
) -> None:
    route_counts = _route_counts(counts_by_kind={"table": 2, "case": 1})
    routed_bundle_paths = _routed_bundle_paths(tmp_path)

    produced = build_produced_route_outputs(
        route_counts=route_counts,
        routed_bundle_paths=routed_bundle_paths,
    )

    assert [item.route_output_kind for item in produced] == ["table", "case"]
    assert produced[0].unit_count == 2
    assert produced[0].routed_bundle_path == routed_bundle_paths["table"]
    assert produced[1].unit_count == 1


def test_build_produced_route_outputs_omits_zero_count_kinds(tmp_path: Path) -> None:
    route_counts = _route_counts(counts_by_kind={"unknown": 1})
    produced = build_produced_route_outputs(
        route_counts=route_counts,
        routed_bundle_paths=_routed_bundle_paths(tmp_path),
    )

    assert len(produced) == 1
    assert produced[0].route_output_kind == "unknown"


def test_build_produced_route_outputs_requires_path_for_produced_kind(
    tmp_path: Path,
) -> None:
    route_counts = _route_counts(counts_by_kind={"table": 1})
    routed_bundle_paths = {
        route: tmp_path / ROUTED_UNITS_ROUTE_FILENAMES[route]
        for route in ROUTES
        if route != "table"
    }

    with pytest.raises(ValueError, match="routed_bundle_paths must include a path"):
        build_produced_route_outputs(
            route_counts=route_counts,
            routed_bundle_paths=routed_bundle_paths,
        )


def test_build_produced_route_outputs_from_route_stage_reference_fields(
    tmp_path: Path,
) -> None:
    route_counts = _route_counts(counts_by_kind={"table": 4})
    routed_bundle_paths = _routed_bundle_paths(tmp_path)
    route_stage = RouteStageReference(
        output_dir=tmp_path,
        run_id="route_run_test",
        doc_id="doc_test",
        semantic_module_id="module_alpha",
        route_counts=route_counts,
        routed_bundle_paths=routed_bundle_paths,
        routing_manifest_path=tmp_path / "routing_manifest.json",
    )

    produced = build_produced_route_outputs(
        route_counts=route_stage.route_counts,
        routed_bundle_paths=route_stage.routed_bundle_paths,
    )

    assert len(produced) == 1
    assert produced[0].route_output_kind == "table"
    assert produced[0].unit_count == 4


def test_select_produced_route_output_returns_matching_kind() -> None:
    produced = (
        RouteOutputDescriptor(
            route_output_kind="table",
            unit_count=2,
            routed_bundle_path=Path("runs/route/table.json"),
        ),
        RouteOutputDescriptor(
            route_output_kind="case",
            unit_count=1,
            routed_bundle_path=Path("runs/route/case.json"),
        ),
    )

    selection = select_produced_route_output(
        produced_route_outputs=produced,
        required_route_output_kind="case",
    )

    assert selection is not None
    assert selection.required_route_output_kind == "case"
    assert selection.selected_route_output.route_output_kind == "case"
    assert selection.selected_route_output.unit_count == 1


def test_select_produced_route_output_returns_none_when_kind_not_produced() -> None:
    produced = (
        RouteOutputDescriptor(
            route_output_kind="table",
            unit_count=1,
            routed_bundle_path=Path("runs/route/table.json"),
        ),
    )

    selection = select_produced_route_output(
        produced_route_outputs=produced,
        required_route_output_kind="unknown",
    )

    assert selection is None


def test_select_produced_route_output_rejects_duplicate_produced_kinds() -> None:
    produced = (
        RouteOutputDescriptor(
            route_output_kind="table",
            unit_count=1,
            routed_bundle_path=Path("runs/route/table_a.json"),
        ),
        RouteOutputDescriptor(
            route_output_kind="table",
            unit_count=2,
            routed_bundle_path=Path("runs/route/table_b.json"),
        ),
    )

    with pytest.raises(ValueError, match="duplicate"):
        select_produced_route_output(
            produced_route_outputs=produced,
            required_route_output_kind="table",
        )


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


@pytest.mark.parametrize(
    "module_path",
    [OUTPUT_CONTRACT_PATH, CONSUMER_SELECTION_PATH],
)
def test_route_output_modules_have_no_esp_or_application_imports(
    module_path: Path,
) -> None:
    imported = _imported_modules(module_path)
    forbidden_prefixes = (
        "application.",
        "plugins.",
        "runtime.",
        "operations.evidence_source_preparation",
    )
    for module in imported:
        for prefix in forbidden_prefixes:
            assert not module.startswith(prefix), (
                f"{module_path.name} must not import {module!r}"
            )


def test_consumer_selection_module_has_no_hardcoded_route_kind_literals() -> None:
    source = CONSUMER_SELECTION_PATH.read_text(encoding="utf-8")
    for route_kind in ROUTES:
        assert f'"{route_kind}"' not in source
        assert f"'{route_kind}'" not in source
