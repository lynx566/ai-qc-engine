"""Contract tests for evidence source preparation input DTO ownership (PR D3d)."""

from __future__ import annotations

import ast
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

INPUT_TYPES_PATH = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "clinical_safety"
    / "aggregate_evidence"
    / "input_types.py"
)
OLD_PACKAGE_ROOT = BACKEND_ROOT / "pipeline" / "evidence_source_preparation"
CANONICAL_STEP_PATH = BACKEND_ROOT / "steps" / "evidence_source_preparation.py"
PROCESSOR_PATH = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "processor.py"
)
ADAPTER_PATH = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
    / "clinical_safety"
    / "aggregate_evidence"
    / "phase_facade.py"
)

EXPECTED_UPSTREAM_FIELDS = (
    "block_manifest",
    "doc_meta_bundle",
    "analysis_bundle",
    "coverage_bundle",
    "private_audit_bundle",
    "date_shift_offset_days",
    "date_shift_offset_source",
    "projected_coverage_by_filter_job",
    "projection_input_refs",
    "semantic_module_id",
)

EXPECTED_ROUTE_FIELDS = (
    "route_counts",
    "aggregate_bundle",
    "routing_manifest",
    "source_routed_unit_bundle_filename",
    "routing_manifest_filename",
)

FORBIDDEN_OLD_PACKAGE_IMPORT = "pipeline.evidence_source_preparation"
CANONICAL_INPUT_IMPORT = (
    "plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types"
)
CANONICAL_NEUTRAL_CONTRACTS_IMPORT = "operations.evidence_source_preparation.contracts"

PRODUCTION_SCAN_ROOTS = (
    BACKEND_ROOT / "steps",
    BACKEND_ROOT / "runtime",
    BACKEND_ROOT / "plugins",
    BACKEND_ROOT / "scripts",
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


def _iter_py_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def test_input_types_module_exists() -> None:
    assert INPUT_TYPES_PATH.is_file()


def test_old_pipeline_evidence_source_preparation_package_removed() -> None:
    assert not OLD_PACKAGE_ROOT.exists(), (
        f"legacy package must be removed: {OLD_PACKAGE_ROOT}"
    )


def test_input_types_export_both_dtos() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
        AggregateEvidenceRouteArtifactsInput,
        EvidenceSourcePreparationUpstreamInput,
    )

    assert is_dataclass(EvidenceSourcePreparationUpstreamInput)
    assert is_dataclass(AggregateEvidenceRouteArtifactsInput)
    assert EvidenceSourcePreparationUpstreamInput.__dataclass_params__.frozen is True
    assert AggregateEvidenceRouteArtifactsInput.__dataclass_params__.frozen is True


def test_upstream_input_field_contract() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
        EvidenceSourcePreparationUpstreamInput,
    )

    field_names = tuple(field.name for field in fields(EvidenceSourcePreparationUpstreamInput))
    assert field_names == EXPECTED_UPSTREAM_FIELDS

    upstream = EvidenceSourcePreparationUpstreamInput(
        coverage_bundle={"doc_id": "doc_1"},
        block_manifest={"blocks": []},
        doc_meta_bundle={"doc_id": "doc_1"},
        analysis_bundle={"doc_id": "doc_1"},
    )
    assert upstream.private_audit_bundle is None
    assert upstream.date_shift_offset_days is None
    assert upstream.date_shift_offset_source is None
    assert upstream.projected_coverage_by_filter_job is None
    assert upstream.projection_input_refs == ()
    assert upstream.semantic_module_id is None


def test_route_artifacts_input_field_contract() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
        AggregateEvidenceRouteArtifactsInput,
    )

    field_names = tuple(field.name for field in fields(AggregateEvidenceRouteArtifactsInput))
    assert field_names == EXPECTED_ROUTE_FIELDS

    route_artifacts = AggregateEvidenceRouteArtifactsInput(
        route_counts={"aggregate": 1},
        aggregate_bundle={"route": "aggregate"},
        routing_manifest={"routes": ["aggregate"]},
        source_routed_unit_bundle_filename="routed_units_aggregate.json",
        routing_manifest_filename="routing_manifest.json",
    )
    assert route_artifacts.source_routed_unit_bundle_filename == "routed_units_aggregate.json"


def test_input_types_has_minimal_dependencies() -> None:
    tree = _parse(INPUT_TYPES_PATH)
    imported = _imported_module_names(tree)
    assert imported <= {
        "dataclasses",
        "typing",
        "__future__",
        "llm.providers.base",
        "operations.evidence_source_preparation.contracts",
        "operations.evidence_source_preparation.stage",
    }


def test_aggregate_execution_input_inherits_neutral_invocation_marker() -> None:
    from operations.evidence_source_preparation.contracts import (
        EvidenceSourcePreparationInvocation,
    )
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
        AggregateEvidenceExecutionInput,
    )

    assert issubclass(AggregateEvidenceExecutionInput, EvidenceSourcePreparationInvocation)


def test_canonical_step_uses_neutral_contracts_only() -> None:
    tree = _parse(CANONICAL_STEP_PATH)
    imported = _imported_module_names(tree)
    assert CANONICAL_NEUTRAL_CONTRACTS_IMPORT in imported
    assert CANONICAL_INPUT_IMPORT not in imported
    assert FORBIDDEN_OLD_PACKAGE_IMPORT not in imported


def test_adapter_imports_input_types_from_plugin() -> None:
    tree = _parse(ADAPTER_PATH)
    imported = _imported_module_names(tree)
    assert CANONICAL_INPUT_IMPORT in imported, "phase_facade must import plugin input_types"
    assert FORBIDDEN_OLD_PACKAGE_IMPORT not in imported


def test_processor_module_removed() -> None:
    assert not PROCESSOR_PATH.is_file(), "legacy processor.py must stay removed"


def test_production_code_does_not_import_old_pipeline_package() -> None:
    violations: list[str] = []
    for scan_root in PRODUCTION_SCAN_ROOTS:
        for path in _iter_py_files(scan_root):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            if "/__pycache__/" in rel or "/runs/" in rel:
                continue
            tree = _parse(path)
            for imported in _imported_module_names(tree):
                if imported == FORBIDDEN_OLD_PACKAGE_IMPORT or imported.startswith(
                    f"{FORBIDDEN_OLD_PACKAGE_IMPORT}."
                ):
                    violations.append(f"{rel} imports {imported}")
    assert not violations, "\n".join(violations)
