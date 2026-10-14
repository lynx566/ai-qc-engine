"""ESP Route→compact→provenance→assessment_evidence handoff regressions."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_prepare_integrity import (
    validate_aggregate_prepare_handoff,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    collect_scoped_assessment_handoff_issues,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import run_prepare
from runtime.io import load_json
from tests.evidence_source_preparation_phase_test_helpers import installed_prepare_phase_kwargs
from tests.route_runtime_test_helpers import (
    persist_route_artifacts_from_coverage,
    write_upstream_route_fixtures,
)
from tests.test_assessment_input_compact import (
    _aggregate_unit,
    _compact_assessment_input_from_units,
)


def _run_route_to_prepare(tmp_path: Path) -> dict[str, Path]:
    paths = write_upstream_route_fixtures(tmp_path)
    route_out = tmp_path / "route_out"
    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=route_out,
        run_id="handoff_route",
    )
    prepare_out = tmp_path / "prepare_out"
    run_prepare(
        **installed_prepare_phase_kwargs(),
        routed_aggregate_bundle_path=route_result.routed_bundle_paths["aggregate"],
        routing_manifest_path=route_result.routing_manifest_path,
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=prepare_out,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        run_id="handoff_prepare",
    )
    return {
        "paths": paths,
        "prepare_out": prepare_out,
        "aggregate_bundle": route_result.routed_bundle_paths["aggregate"],
    }


def test_canonical_route_to_prepare_handoff_passes_without_policy(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    report = load_json(refs["prepare_out"] / "unit_integrity_report.json")
    assert report["validation_scope"] == "aggregate_prepare_handoff"
    assert report["status"] == "pass"
    assert report["summary"]["error_count"] == 0
    assert "policy" not in report


def test_handoff_flags_sentence_id_mismatch() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section A"],
            context_block_ids=["C0010"],
            sentences=[
                {"sentence_id": "S0001", "text": "alpha", "source_block_id": "C0001"},
            ],
        )
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    bad_input = copy.deepcopy(assessment_input)
    bad_input["heading_scopes"][0]["units"][0]["sentences"][0]["sentence_id"] = "S9999"
    issues = collect_scoped_assessment_handoff_issues(
        bad_input,
        runtime_context,
        aggregate_units=units,
    )
    assert any(issue["code"] == "route_compact_sentence_id_mismatch" for issue in issues)


def test_handoff_flags_sentence_text_mismatch() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section A"],
            context_block_ids=["C0010"],
        )
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    bad_input = copy.deepcopy(assessment_input)
    bad_input["heading_scopes"][0]["units"][0]["sentences"][0]["text"] = "mutated text"
    issues = collect_scoped_assessment_handoff_issues(
        bad_input,
        runtime_context,
        aggregate_units=units,
    )
    assert any(issue["code"] == "route_compact_sentence_text_mismatch" for issue in issues)


def test_handoff_flags_runtime_sentence_provenance_mismatch() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section A"],
            context_block_ids=["C0010"],
        )
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    bad_runtime = copy.deepcopy(runtime_context)
    bad_runtime["unit_provenance"]["TU0001"]["source_sentence_ids"] = ["S9999"]
    issues = collect_scoped_assessment_handoff_issues(
        assessment_input,
        bad_runtime,
        aggregate_units=units,
    )
    assert any(issue["code"] == "runtime_source_sentence_id_mismatch" for issue in issues)


def test_handoff_flags_runtime_sentence_block_provenance_mismatch() -> None:
    units = [
        _aggregate_unit(
            unit_id="TU0001",
            heading_path=["Section A"],
            context_block_ids=["C0010"],
        )
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    bad_runtime = copy.deepcopy(runtime_context)
    bad_runtime["unit_provenance"]["TU0001"]["sentence_source_block_ids"] = ["C9999"]
    issues = collect_scoped_assessment_handoff_issues(
        assessment_input,
        bad_runtime,
        aggregate_units=units,
    )
    assert any(issue["code"] == "runtime_sentence_source_block_mismatch" for issue in issues)


def test_handoff_flags_missing_unit() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"]),
        _aggregate_unit(unit_id="TU0002", heading_path=["A"], context_block_ids=["C0010"]),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    bad_input = copy.deepcopy(assessment_input)
    bad_input["heading_scopes"][0]["units"] = bad_input["heading_scopes"][0]["units"][:1]
    report = validate_aggregate_prepare_handoff(
        assessment_input=bad_input,
        runtime_context=runtime_context,
        aggregate_units=units,
    )
    assert report["status"] == "fail"
    assert any(
        issue["code"] == "aggregate_route_unit_missing_from_assessment_input"
        for issue in report["issues"]
    )


def test_handoff_flags_extra_unit() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"]),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    bad_input = copy.deepcopy(assessment_input)
    bad_input["heading_scopes"][0]["units"].append(
        {
            "unit_id": "TU9999",
            "sentences": [{"sentence_id": "S9999", "text": "extra"}],
        }
    )
    report = validate_aggregate_prepare_handoff(
        assessment_input=bad_input,
        runtime_context=runtime_context,
        aggregate_units=units,
    )
    assert report["status"] == "fail"
    assert any(
        issue["code"] == "assessment_input_unit_not_in_aggregate_route"
        for issue in report["issues"]
    )


def test_handoff_flags_reordered_units() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"]),
        _aggregate_unit(unit_id="TU0002", heading_path=["A"], context_block_ids=["C0010"]),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    bad_input = copy.deepcopy(assessment_input)
    bad_input["heading_scopes"][0]["units"] = list(
        reversed(bad_input["heading_scopes"][0]["units"])
    )
    report = validate_aggregate_prepare_handoff(
        assessment_input=bad_input,
        runtime_context=runtime_context,
        aggregate_units=units,
    )
    assert report["status"] == "fail"
    assert any(
        issue["code"] == "aggregate_route_unit_order_mismatch"
        for issue in report["issues"]
    )


def test_handoff_flags_assessment_evidence_mismatch() -> None:
    units = [
        _aggregate_unit(unit_id="TU0001", heading_path=["A"], context_block_ids=["C0010"]),
    ]
    assessment_input, runtime_context = _compact_assessment_input_from_units(units)
    bad_input = copy.deepcopy(assessment_input)
    bad_input["heading_scopes"][0]["assessment_evidence"]["candidate_text"] = "wrong evidence"
    report = validate_aggregate_prepare_handoff(
        assessment_input=bad_input,
        runtime_context=runtime_context,
        aggregate_units=units,
    )
    assert report["status"] == "fail"
    assert report["summary"]["scope_assessment_evidence_mismatch_count"] >= 1


def test_prepare_phase_fail_closed_on_handoff_violation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence import (
        phase_facade,
    )

    original = phase_facade.plugin_run_aggregate_evidence_prepare

    def _mutating_prepare(**kwargs):
        semantic_result = dict(original(**kwargs))
        canonical = [dict(unit) for unit in semantic_result["canonical_aggregate_units"]]
        canonical[0]["sentences"] = [
            {
                **dict(canonical[0]["sentences"][0]),
                "text": "route text drift",
            }
        ]
        semantic_result["canonical_aggregate_units"] = canonical
        return semantic_result

    monkeypatch.setattr(phase_facade, "plugin_run_aggregate_evidence_prepare", _mutating_prepare)

    paths = write_upstream_route_fixtures(tmp_path)
    route_out = tmp_path / "route_out_fail"
    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=route_out,
        run_id="handoff_route_fail",
    )
    with pytest.raises(ValueError, match="route_compact_sentence_text_mismatch"):
        run_prepare(
            **installed_prepare_phase_kwargs(),
            routed_aggregate_bundle_path=route_result.routed_bundle_paths["aggregate"],
            routing_manifest_path=route_result.routing_manifest_path,
            coverage_bundle_path=paths["coverage"],
            block_manifest_path=paths["block_manifest"],
            doc_meta_bundle_path=paths["doc_meta_bundle"],
            analysis_bundle_path=paths["analysis"],
            output_dir=tmp_path / "prepare_fail_out",
            evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        )
