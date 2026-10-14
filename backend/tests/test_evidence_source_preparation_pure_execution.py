"""Pure execution and import-boundary tests for evidence source preparation."""

# ruff: noqa: SIM102
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_phase_harness_installation import (
    HARNESS_AGGREGATE_EVIDENCE_PREPARE_PHASE,
    resolve_installed_aggregate_evidence_phase_harness_dependencies,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from steps.evidence_source_preparation import (
    run_evidence_source_preparation,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceRouteArtifactsInput,
    EvidenceSourcePreparationUpstreamInput,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.phase_facade import (
    run_aggregate_evidence_prepare,
)
from tests.evidence_source_preparation_phase_test_helpers import installed_prepare_phase_kwargs
from tests.route_runtime_test_helpers import (
    persist_route_artifacts_from_coverage,
    write_upstream_route_fixtures,
)

EVIDENCE_SOURCE_PREPARATION_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_source_preparation"
)
PLUGIN_EVIDENCE_SOURCE_PREPARATION_ROOT = EVIDENCE_SOURCE_PREPARATION_ROOT
CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT = (
    EVIDENCE_SOURCE_PREPARATION_ROOT / "clinical_safety" / "aggregate_evidence"
)
ADAPTER_PATH = CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT / "phase_facade.py"
EXECUTION_TYPES_PATH = CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT / "execution_types.py"
INPUT_TYPES_PATH = CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT / "input_types.py"
EXECUTOR_PATH = CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT / "executor.py"
SCOPE_ASSESS_PATH = CLINICAL_SAFETY_AGGREGATE_EVIDENCE_ROOT / "scope_assess.py"
CANONICAL_STEP_PATH = BACKEND_ROOT / "steps" / "evidence_source_preparation.py"

FORBIDDEN_PIPELINE_RUNTIME_PREFIXES = (
    "runtime",
    "runtime.",
    "scripts",
    "scripts.",
)


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


def _forbidden_import_violations(
    path: Path,
    *,
    forbidden_prefixes: tuple[str, ...],
) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for imported in _imported_module_names(tree):
        if any(
            imported == prefix.rstrip(".") or imported.startswith(prefix)
            for prefix in forbidden_prefixes
        ):
            violations.append(f"{path.relative_to(BACKEND_ROOT)} imports {imported}")
    source = path.read_text(encoding="utf-8")
    if "from pathlib import Path" in source or "import Path" in source:
        violations.append(f"{path.relative_to(BACKEND_ROOT)} imports Path")
    return violations


def _route_manifest(doc_id: str, zone_key: str) -> dict:
    return {
        "routing_manifest_id": "routing_manifest_test",
        "doc_id": doc_id,
        "zone_key": zone_key,
        "route_artifact_files": {
            "aggregate": {
                "path": "routed_units_aggregate.json",
                "routed_unit_bundle_id": "routed_aggregate_test",
            },
            "table": {
                "path": "routed_units_table.json",
                "routed_unit_bundle_id": "routed_table_test",
            },
            "case": {
                "path": "routed_units_case.json",
                "routed_unit_bundle_id": "routed_case_test",
            },
            "unknown": {
                "path": "routed_units_unknown.json",
                "routed_unit_bundle_id": "routed_unknown_test",
            },
        },
    }

@pytest.mark.parametrize(
    "rel_path",
    [
        ADAPTER_PATH,
        EXECUTION_TYPES_PATH,
        INPUT_TYPES_PATH,
        EXECUTOR_PATH,
        SCOPE_ASSESS_PATH,
        CANONICAL_STEP_PATH,
    ],
)
def test_evidence_source_preparation_package_has_no_runtime_imports(rel_path: Path) -> None:
    violations = _forbidden_import_violations(
        rel_path,
        forbidden_prefixes=FORBIDDEN_PIPELINE_RUNTIME_PREFIXES,
    )
    assert not violations, "\n".join(violations)


def test_input_types_has_no_runtime_result_types() -> None:
    source = INPUT_TYPES_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "PrepareResult",
        "AssessResult",
        "runtime.",
    ):
        assert forbidden not in source, f"types.py must not reference {forbidden!r}"


def test_pure_prepare_does_not_write_files(tmp_path: Path) -> None:
    paths = write_upstream_route_fixtures(tmp_path)
    from runtime.io import load_json
    from tests.route_runtime_test_helpers import persist_route_artifacts_from_coverage

    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=tmp_path / "route_out",
        run_id="pure_prepare_route",
    )
    aggregate_bundle = load_json(route_result.routed_bundle_paths["aggregate"])
    routing_manifest = load_json(route_result.routing_manifest_path)
    upstream = EvidenceSourcePreparationUpstreamInput(
        coverage_bundle=load_json(paths["coverage"]),
        block_manifest=load_json(paths["block_manifest"]),
        doc_meta_bundle=load_json(paths["doc_meta_bundle"]),
        analysis_bundle=load_json(paths["analysis"]),
    )
    route_artifacts = AggregateEvidenceRouteArtifactsInput(
        route_counts=dict(route_result.route_counts),
        aggregate_bundle=aggregate_bundle,
        routing_manifest=routing_manifest,
        source_routed_unit_bundle_filename="routed_units_aggregate.json",
        routing_manifest_filename="routing_manifest.json",
    )
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies()
    out_before = set(tmp_path.rglob("*"))
    execution = HARNESS_AGGREGATE_EVIDENCE_PREPARE_PHASE(
        upstream=upstream,
        route_artifacts=route_artifacts,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        prepare_semantic=phase_dependencies.semantic_binding.prepare,
    )
    out_after = set(tmp_path.rglob("*"))
    assert out_before == out_after
    assert execution.assessment_input.get("stage") == "evidence_source_preparation"
    assert execution.assessment_input.get("phase") == "prepare"
    assert execution.assessment_runtime_context


def test_runtime_prepare_stage_calls_injected_prepare_phase(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import run_prepare

    calls: list[str] = []

    def _fake_prepare_phase(**kwargs: object):
        calls.append("prepare_phase")
        return run_aggregate_evidence_prepare(
            upstream=kwargs["upstream"],  # type: ignore[arg-type]
            route_artifacts=kwargs["route_artifacts"],  # type: ignore[arg-type]
            evidence_form_id=kwargs["evidence_form_id"],  # type: ignore[arg-type]
            prepare_semantic=kwargs["prepare_semantic"],  # type: ignore[arg-type]
        )

    paths = write_upstream_route_fixtures(tmp_path)
    from tests.route_runtime_test_helpers import persist_route_artifacts_from_coverage

    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=tmp_path / "route_out",
        run_id="wrapper_prepare",
    )
    run_prepare(
        run_prepare_phase=_fake_prepare_phase,
        prepare_semantic=resolve_installed_aggregate_evidence_phase_harness_dependencies().semantic_binding.prepare,
        routed_aggregate_bundle_path=route_result.routed_bundle_paths["aggregate"],
        routing_manifest_path=route_result.routing_manifest_path,
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=tmp_path / "prepare_out",
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        run_id="prep_run",
    )
    assert calls == ["prepare_phase"]
