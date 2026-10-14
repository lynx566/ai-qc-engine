"""Process.prepare runtime tests (temp dirs only)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    ASSESSMENT_RUNTIME_CONTEXT_FILENAME,
    iter_compact_assessment_units,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
)
from artifacts.evidence_source_preparation.schema import (
    EVIDENCE_SOURCE_PREPARATION_STAGE,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import (
    run_prepare,
)
from runtime.io import load_json
from tests.evidence_source_preparation_phase_test_helpers import (
    installed_prepare_phase_kwargs,
)
from tests.route_runtime_test_helpers import (
    persist_route_artifacts_from_coverage,
    write_upstream_route_fixtures,
)


def _run_route_to_prepare(
    tmp_path: Path,
) -> dict[str, Path]:
    paths = write_upstream_route_fixtures(tmp_path)
    route_out = tmp_path / "route_out"
    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=route_out,
        run_id="equiv_route",
    )
    prepare_out = tmp_path / "prepare_out"
    prepare_result = run_prepare(
        **installed_prepare_phase_kwargs(),
        routed_aggregate_bundle_path=route_result.routed_bundle_paths["aggregate"],
        routing_manifest_path=route_result.routing_manifest_path,
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=prepare_out,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        run_id="equiv_prepare",
    )
    return {
        "paths": paths,
        "route_out": route_out,
        "prepare_out": prepare_out,
        "route_result": route_result,
        "aggregate_bundle": route_result.routed_bundle_paths["aggregate"],
        "assessment_input": prepare_result.assessment_input_path,
    }


def test_route_to_assessment_input_metadata(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    assessment_input = load_json(refs["assessment_input"])
    runtime_context = load_json(
        refs["prepare_out"] / ASSESSMENT_RUNTIME_CONTEXT_FILENAME
    )
    assert assessment_input["stage"] == EVIDENCE_SOURCE_PREPARATION_STAGE
    assert assessment_input["phase"] == EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE
    assert "comparison_type" not in assessment_input
    assert assessment_input["source_stage"] == "route"
    assert "heading_scopes" in assessment_input
    assert "units" not in assessment_input
    assert "runtime_context_ref" in assessment_input
    assert not (refs["prepare_out"] / "pre_llm_review_bundle.json").exists()
    assert not (refs["prepare_out"] / "pre_llm_audit_bundle_private.json").exists()
    assert not (refs["prepare_out"] / "pre_llm_review_state.json").exists()
    assert runtime_context["runtime_context_id"] == assessment_input["runtime_context_ref"][
        "runtime_context_id"
    ]
    assert (refs["prepare_out"] / ASSESSMENT_RUNTIME_CONTEXT_FILENAME).is_file()
    assert (refs["prepare_out"] / "assessment_input_preview.json").is_file()
    assert not (refs["prepare_out"] / "routing_manifest.json").exists()
    assert not (refs["prepare_out"] / "llm_input_aggregate.json").exists()
    assert not (refs["prepare_out"] / "llm_input_case.json").exists()


def test_no_reroute_on_prepare_path(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)

    def _fail(*_args, **_kwargs):
        raise AssertionError("must not re-run routing during Aggregate Evidence prepare")

    with patch(
        "plugins.clinical_trial_doc.routing.projected_sources.route_prepare_units_from_projected_sources",
        side_effect=_fail,
    ):
        run_prepare(
            **installed_prepare_phase_kwargs(),
            routed_aggregate_bundle_path=refs["aggregate_bundle"],
            routing_manifest_path=refs["route_result"].routing_manifest_path,
            coverage_bundle_path=refs["paths"]["coverage"],
            block_manifest_path=refs["paths"]["block_manifest"],
            doc_meta_bundle_path=refs["paths"]["doc_meta_bundle"],
            analysis_bundle_path=refs["paths"]["analysis"],
            output_dir=tmp_path / "prepare_rerun_guard",
            evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        )


def test_prepare_aggregate_units_match_route_and_runtime_provenance(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    aggregate_bundle = load_json(refs["aggregate_bundle"])
    assessment_input = load_json(refs["assessment_input"])
    runtime_context = load_json(
        refs["prepare_out"] / ASSESSMENT_RUNTIME_CONTEXT_FILENAME
    )

    compact_unit_ids = [unit_id for unit_id, _unit in iter_compact_assessment_units(assessment_input)]
    route_unit_ids = [unit["unit_id"] for unit in aggregate_bundle["units"]]
    assert compact_unit_ids == route_unit_ids

    provenance_map = runtime_context["unit_provenance"]
    for route_unit in aggregate_bundle["units"]:
        unit_id = route_unit["unit_id"]
        compact_unit = next(
            unit
            for scope in assessment_input["heading_scopes"]
            for unit in scope["units"]
            if unit["unit_id"] == unit_id
        )
        assert [
            {"sentence_id": sentence["sentence_id"], "text": sentence["text"]}
            for sentence in compact_unit["sentences"]
        ] == [
            {"sentence_id": sentence["sentence_id"], "text": sentence["text"]}
            for sentence in route_unit["sentences"]
        ]
        provenance = provenance_map[unit_id]
        assert provenance["source_sentence_ids"] == [
            sentence["sentence_id"] for sentence in route_unit["sentences"]
        ]
        assert provenance["sentence_source_block_ids"] == [
            sentence["source_block_id"] for sentence in route_unit["sentences"]
        ]


def test_route_to_esp_preserves_canonical_sentence_ids(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    aggregate_bundle = load_json(refs["aggregate_bundle"])
    assessment_input = load_json(refs["assessment_input"])

    routed_sentences = aggregate_bundle["units"][0]["sentences"]
    assert routed_sentences
    assert all(":" in sentence["sentence_id"] for sentence in routed_sentences)
    assert not any(str(sentence["sentence_id"]).startswith("S0") for sentence in routed_sentences)

    scope_sentences = assessment_input["heading_scopes"][0]["units"][0]["sentences"]
    assert scope_sentences[0]["sentence_id"] == routed_sentences[0]["sentence_id"]
    assert scope_sentences[0]["text"] == routed_sentences[0]["text"]


def test_aggregate_evidence_runtime_prepare_requires_output_dir(tmp_path: Path) -> None:
    refs = _run_route_to_prepare(tmp_path)
    with pytest.raises(TypeError):
        run_prepare(
            **installed_prepare_phase_kwargs(),
            routed_aggregate_bundle_path=refs["aggregate_bundle"],
            routing_manifest_path=refs["route_result"].routing_manifest_path,
            coverage_bundle_path=refs["paths"]["coverage"],
            block_manifest_path=refs["paths"]["block_manifest"],
            doc_meta_bundle_path=refs["paths"]["doc_meta_bundle"],
            analysis_bundle_path=refs["paths"]["analysis"],
            evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        )
