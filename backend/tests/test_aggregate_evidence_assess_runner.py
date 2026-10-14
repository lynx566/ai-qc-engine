from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    build_assessment_runtime_context_envelope,
    build_assessment_runtime_context_id,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    ASSESSMENT_INPUT_SCHEMA_VERSION,
    EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
    EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
    SCOPE_ASSESSMENTS_FILENAME,
    build_mock_scope_assessment,
)
from artifacts.evidence_source_preparation.schema import (
    EVIDENCE_SOURCE_PREPARATION_STAGE,
)
from llm.providers.base import LLMRawResult
from steps.filter import extract_zones_from_bundle, to_public_filter_payload
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.assessment.prompts.clinical_safety_aggregate_heading_scope_assessment_zh import (
    DEFAULT_AGGREGATE_HEADING_SCOPE_ASSESSMENT_INSTRUCTIONS,
    PROMPT_NAME,
    PROMPT_VERSION,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
    attach_assessment_evidence_to_heading_scopes,
    build_heading_scopes_from_aggregate_units,
    build_unit_provenance_map,
)
from plugins.clinical_trial_doc.filter_profiles.ib.clinical_safety_zh import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
)
from runtime.assessment_registry import DEFAULT_ASSESSMENT_PROFILE
from runtime.run_ids import format_run_timestamp
from runtime.run_summaries import build_aggregate_evidence_assess_run_summary
from scripts.stage_runners.evidence_source_preparation.aggregate_evidence import assess_runner
from tests.filter_test_helpers import resolved_filter_job

_FORBIDDEN_TAG_OUTPUT_SUBSTRINGS = (
    "normalized_text",
    "span_map",
    "source_ref",
    "pre_llm_review_bundle",
    "subject_scope",
    "qc_role",
)

from tests.clinical_program_fixtures import canonical_clinical_program_fields

LINEAGE_FILE_HASH = (
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)


def _compact_assessment_artifacts(bundle: dict) -> tuple[dict, dict]:
    units = [
        dict(unit)
        for unit in (bundle.get("units") or [])
        if isinstance(unit, dict)
    ]
    llm_input_bundle_id = str(bundle.get("llm_input_bundle_id") or "llm_input_aggregate_test")
    runtime_context_id = build_assessment_runtime_context_id(
        llm_input_bundle_id=llm_input_bundle_id,
    )
    compact = {
        key: value
        for key, value in bundle.items()
        if key
        not in {
            "units",
            "route_stats",
            "source_routed_unit_bundle_ref",
            "source_routing_manifest_ref",
            "tag_profile_ref",
        }
    }
    heading_scopes = build_heading_scopes_from_aggregate_units(units)
    attach_assessment_evidence_to_heading_scopes(heading_scopes, units)
    compact.update(
        {
            "schema_version": ASSESSMENT_INPUT_SCHEMA_VERSION,
            "stage": EVIDENCE_SOURCE_PREPARATION_STAGE,
            "phase": EVIDENCE_SOURCE_PREPARATION_PREPARE_PHASE,
            "source_stage": "route",
            "llm_input_bundle_id": llm_input_bundle_id,
            "heading_scopes": heading_scopes,
            "runtime_context_ref": {"runtime_context_id": runtime_context_id},
            "assessment_profile_ref": "clinical_safety_aggregate_heading_scope_assessment_zh",
        }
    )
    runtime_context = build_assessment_runtime_context_envelope(
        llm_input_bundle_id=llm_input_bundle_id,
        runtime_context_id=runtime_context_id,
        doc_id=str(bundle.get("doc_id") or "doc_test"),
        file_hash=str(bundle.get("file_hash") or "sha256:test"),
        route_stats=dict(bundle.get("route_stats") or {"unit_count": len(units)}),
        unit_provenance=build_unit_provenance_map(units),
        source_routed_unit_bundle_ref={
            "routed_unit_bundle_id": "routed_units_aggregate_test",
            "path": "routed_units_aggregate.json",
        },
        source_routing_manifest_ref={
            "routing_manifest_id": "route_routing_test",
            "path": "routing_manifest.json",
        },
        coverage_bundle_ref=dict(bundle.get("coverage_bundle_ref") or {}),
        block_manifest_ref=dict(bundle.get("block_manifest_ref") or {}),
        doc_meta_ref=dict(bundle.get("doc_meta_ref") or {}),
    )
    compact["runtime_context_ref"]["runtime_context_id"] = runtime_context["runtime_context_id"]
    return compact, runtime_context


def _as_assessment_input(bundle: dict) -> dict:
    compact, _runtime = _compact_assessment_artifacts(bundle)
    return compact


def _minimal_llm_input_bundle() -> dict:
    bundle = {
        "llm_input_bundle_id": "llm_input_coverage_filter_test_zone",
        "route": "aggregate",
        "doc_id": "doc_test",
        "file_hash": LINEAGE_FILE_HASH,
        "zone_key": "ib_clinical_safety_zh",
        "tag_profile_ref": "clinical_safety_aggregate_finding_zh",
        "coverage_bundle_ref": {"coverage_bundle_id": "coverage_test"},
        "block_manifest_ref": {"block_manifest_id": "block_manifest_test"},
        "doc_meta_ref": {"doc_meta_bundle_id": "doc_meta_test"},
        "doc_meta": {
            "doc_type": "IB",
            "study_drug": "StudyDrug_001",
        },
        "units": [
            {
                "unit_id": "TU0001",
                "unit_kind": "text_unit",
                "route": "aggregate",
                "route_basis": "clinical_safety_default_text",
                "source_stage": "filter",
                "source_zone_key": "ib_clinical_safety_zh",
                "heading_path": ["六、临床安全性"],
                "sentences": [
                    {
                        "sentence_id": "S0001",
                        "text": "masked safety text for TU0001",
                        "source_block_id": "C0007",
                    }
                ],
                "source_block_ids": ["C0007"],
                "context_block_ids": [],
                "all_source_block_ids": ["C0007"],
                "candidate_block_kinds": ["paragraph"],
                "text_refs": [
                    {
                        "analysis_bundle_id": "prepare_analysis_test",
                        "block_id": "C0007",
                    }
                ],
                "route_matched_terms": [],
                "source_component_ids": [],
                "overview_decompose_bundle_id": None,
            }
        ],
        "route_stats": {"unit_count": 1},
        "instructions": DEFAULT_AGGREGATE_HEADING_SCOPE_ASSESSMENT_INSTRUCTIONS,
        "expected_schema": {},
    }
    return bundle


def _canonical_api_llm_input_bundle() -> dict:
    bundle = _minimal_llm_input_bundle()
    bundle["route"] = "aggregate"
    for unit in bundle.get("units") or []:
        if isinstance(unit, dict):
            unit.setdefault("unit_kind", "text_unit")
            unit.setdefault("route", "aggregate")
    return bundle


def _write_llm_input_bundle_file(
    directory: Path,
    *,
    llm_input_bundle: dict | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    bundle = llm_input_bundle if llm_input_bundle is not None else _minimal_llm_input_bundle()
    assessment_bundle, runtime_context = _compact_assessment_artifacts(bundle)
    path = directory / "assessment_input.json"
    path.write_text(
        json.dumps(assessment_bundle, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    runtime_path = directory / "assessment_runtime_context.json"
    runtime_path.write_text(
        json.dumps(runtime_context, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _mock_git_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence import (
        operations,
    )

    monkeypatch.setattr(
        operations,
        "snapshot_git_provenance_before_run",
        lambda **_: {"git_commit": "abc", "git_dirty": False},
    )


def _sample_analysis_bundle() -> dict:
    return {
        "analysis_bundle_id": "prepare_analysis_ib_001",
        "doc_id": "ib_001",
        "file_hash": LINEAGE_FILE_HASH,
        **canonical_clinical_program_fields(),
        "file_name": "ib_001.docx",
        "source_type": "docx",
        "content_blocks": [
            {
                "block_id": "h1",
                "kind": "heading",
                "order": 1,
                "text": "<<SPONSOR>> 5.2.1 临床安全性",
                "analysis_text": "<<SPONSOR>> 5.2.1 临床安全性",
                "meta": {
                    "heading_level": 3,
                    "heading_text_stripped": "临床安全性",
                },
            },
            {
                "block_id": "p1",
                "kind": "paragraph",
                "order": 2,
                "text": "masked safety paragraph",
                "analysis_text": "masked safety paragraph",
            },
        ],
    }


def _sample_doc_meta_bundle() -> dict:
    return {
        "doc_meta_bundle_id": "doc_meta_ib_001",
        "doc_id": "ib_001",
        "file_hash": LINEAGE_FILE_HASH,
        "summary": {"doc_type": "IB", "study_drug": "StudyDrug_001"},
        "doc_type": {"value": "IB"},
        "fields": {"study_drug": {"value": "StudyDrug_001"}},
    }


def _sample_public_filter_payload() -> dict:
    bundle = {
        "doc_id": "ib_001",
        "file_name": "ib_001.docx",
        "source_type": "docx",
        "content_blocks": [
            {
                "block_id": "h1",
                "kind": "heading",
                "text": "<<SPONSOR>> 5.2.1 临床安全性",
                "meta": {
                    "heading_level": 3,
                    "heading_text_stripped": "临床安全性",
                },
            },
            {
                "block_id": "p1",
                "kind": "paragraph",
                "text": "masked safety paragraph",
            },
        ],
    }
    return to_public_filter_payload(
        extract_zones_from_bundle(
            bundle,
            resolved_filter_job(IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH),
        )
    )


# --- Formal assessment_input → assess run summary ---


def test_build_aggregate_evidence_assess_run_summary_reads_stats(tmp_path: Path) -> None:
    from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.scope_assessments import (
        build_scope_assessments_envelope,
    )

    llm_input_bundle = _minimal_llm_input_bundle()
    compact_input = _as_assessment_input(llm_input_bundle)
    _, runtime_context = _compact_assessment_artifacts(llm_input_bundle)
    scope_assessments = build_scope_assessments_envelope(
        assessment_input=compact_input,
        assessment_runtime_context=runtime_context,
        canonical_scope_assessments=[
            {
                **build_mock_scope_assessment(compact_input["heading_scopes"][0]["scope_id"]),
                "heading_path": compact_input["heading_scopes"][0]["heading_path"],
                "source_unit_ids": ["TU0001"],
                "safety_role": "primary_safety_finding",
                "route_qc": {
                    "route_mismatch": True,
                    "suggested_route": "case",
                    "reason": "individual subject narrative",
                },
                "post_llm_validation_flags": [],
            }
        ],
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
        prompt_name=PROMPT_NAME,
        prompt_version=PROMPT_VERSION,
        llm_mode="mock",
        llm_profile=None,
    )
    llm_input_path = tmp_path / "assessment_input.json"
    scope_path = tmp_path / SCOPE_ASSESSMENTS_FILENAME
    llm_input_path.write_text(json.dumps(compact_input), encoding="utf-8")
    scope_path.write_text(json.dumps(scope_assessments), encoding="utf-8")

    summary = build_aggregate_evidence_assess_run_summary(
        run_id="tag_test_run",
        assessment_input=compact_input,
        assessment_input_path=llm_input_path,
        scope_assessments_path=scope_path,
        scope_assessments=scope_assessments,
        scope_assessment_review_path=None,
        scope_assessment_review=None,
        assessment_profile_name="clinical_safety_aggregate_heading_scope_assessment_zh",
        llm_mode="mock",
        zone_key="ib_clinical_safety_zh",
        phase=EVIDENCE_SOURCE_PREPARATION_ASSESS_PHASE,
        completed_operation="aggregate_evidence.assess_heading_scopes",
        paths_base=tmp_path,
    )

    assert summary["stats"]["scope_assessment_count"] == 1
    assert summary["stats"]["input_unit_count"] == 1
    assert summary["stats"]["primary_safety_finding_scope_count"] == 1
    assert summary["stats"]["route_mismatch_scope_count"] == 1
    assert "tagged_item_count" not in summary["stats"]
    assert "file_name" not in summary
    assert summary["outputs"]["scope_assessments"] == SCOPE_ASSESSMENTS_FILENAME


def test_aggregate_evidence_assess_runner_llm_input_bundle_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--assessment-profile",
            "clinical_safety_aggregate_finding_zh",
            "--llm",
            "mock",
            "--out",
            str(out_dir),
        ],
    )
    assess_runner.main()

    captured = capsys.readouterr()
    assert "deprecated assessment profile alias" in captured.err

    scope_output = json.loads(
        (out_dir / SCOPE_ASSESSMENTS_FILENAME).read_text(encoding="utf-8")
    )
    summary = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))

    assert scope_output["stage"] == EVIDENCE_SOURCE_PREPARATION_STAGE
    assert scope_output["phase"] == "assess"
    assert "comparison_type" not in scope_output
    assert scope_output["artifact_type"] == "scope_assessments"
    assert scope_output["assessment_profile_name"] == "clinical_safety_aggregate_heading_scope_assessment_zh"
    assert scope_output["prompt_name"] == PROMPT_NAME
    assert scope_output["prompt_version"] == PROMPT_VERSION
    assert "file_name" not in scope_output
    assert summary["stage"] == EVIDENCE_SOURCE_PREPARATION_STAGE
    assert "file_name" not in summary
    assert summary["inputs"]["assessment_input"].endswith("assessment_input.json")
    assert "pre_llm_review_state" not in summary["inputs"]
    assert "tag_prepare_dir" not in summary["inputs"]
    assert summary["outputs"]["scope_assessments"] == SCOPE_ASSESSMENTS_FILENAME
    assert summary["outputs"]["scope_assessment_review"] == "scope_assessment_review.json"
    assert scope_output["source_assessment_input_ref"]["path"] == "assessment_input.json"
    assert "review_gate" not in summary
    assert "llm_input_preview" not in summary["outputs"]
    assert summary["stats"]["scope_assessment_count"] == scope_output["scope_assessment_count"]
    assert summary["stats"]["input_unit_count"] == 1
    assert "tagged_item_count" not in summary["stats"]
    assert not (out_dir / "tag_output.json").exists()
    assert not (out_dir / "aggregate_assessments.json").exists()
    assert (out_dir / "scope_assessment_review.json").is_file()

    index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    assert index["step"] == "evidence_source_preparation_assess"
    assert index["document_count"] == 1
    entry = index["documents"][0]
    assert entry["doc_id"] == "doc_test"
    assert entry["task_key"] == "clinical_safety"
    assert entry["outputs"]["scope_assessments"] == SCOPE_ASSESSMENTS_FILENAME
    assert entry["outputs"]["scope_assessment_review"] == "scope_assessment_review.json"
    artifact = json.loads((out_dir / SCOPE_ASSESSMENTS_FILENAME).read_text(encoding="utf-8"))
    assert entry["doc_id"] == artifact["doc_id"]
    assert entry["file_hash"] == artifact["file_hash"]
    assert (out_dir / "index.json").read_text(encoding="utf-8").count('"step"') == 1


def test_aggregate_evidence_assess_runner_accepts_deprecated_scope_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--assessment-profile",
            "clinical_safety_scope_annotation_zh",
            "--llm",
            "mock",
            "--out",
            str(out_dir),
        ],
    )
    assess_runner.main()

    captured = capsys.readouterr()
    assert "deprecated assessment profile alias" in captured.err
    assert "deprecated ambiguous profile name" in captured.err

    scope_output = json.loads(
        (out_dir / SCOPE_ASSESSMENTS_FILENAME).read_text(encoding="utf-8")
    )
    assert scope_output["assessment_profile_name"] == (
        "clinical_safety_aggregate_heading_scope_assessment_zh"
    )
    assert scope_output["prompt_name"] == PROMPT_NAME
    assert scope_output["prompt_version"] == PROMPT_VERSION


def test_aggregate_evidence_assess_runner_resolves_tag_profile_from_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--llm",
            "mock",
            "--out",
            str(out_dir),
        ],
    )
    assess_runner.main()

    scope_output = json.loads(
        (out_dir / SCOPE_ASSESSMENTS_FILENAME).read_text(encoding="utf-8")
    )
    assert scope_output["assessment_profile_name"] == DEFAULT_ASSESSMENT_PROFILE


def test_aggregate_evidence_assess_runner_tag_profile_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--assessment-profile",
            "clinical_safety_aggregate_finding_zh",
            "--llm",
            "mock",
            "--out",
            str(out_dir),
        ],
    )
    assess_runner.main()

    assert (out_dir / SCOPE_ASSESSMENTS_FILENAME).is_file()
    assert not (out_dir / "aggregate_assessments.json").exists()
    assert not (out_dir / "tag_output.json").exists()




def test_aggregate_evidence_assess_runner_requires_assessment_input() -> None:
    with pytest.raises(SystemExit):
        assess_runner.parse_args([])


def test_aggregate_evidence_assess_runner_rejects_retired_review_state_flag() -> None:
    with pytest.raises(SystemExit):
        assess_runner.parse_args(
            [
                "--assessment-input",
                "assessment_input.json",
                "--pre-llm-review-state",
                "pre_llm_review_state.json",
                "--llm",
                "mock",
            ]
        )


def _api_fake_provider_json() -> str:
    item = build_mock_scope_assessment("S0001")
    item["safety_role"] = "primary_safety_finding"
    item["product_context_role"] = "target_study_drug"
    return json.dumps({"scope_assessments": [item]}, ensure_ascii=False)


class _ApiFakeProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="deepseek",
            model="deepseek-v4-flash",
            raw_text=_api_fake_provider_json(),
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            request_id="fake-req",
            finish_reason="stop",
            model_alias="deepseek_v4_flash",
            thinking=False,
        )


def test_aggregate_evidence_assess_runner_mock_does_not_write_debug_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--llm",
            "mock",
            "--out",
            str(out_dir),
        ],
    )
    assess_runner.main()

    assert (out_dir / SCOPE_ASSESSMENTS_FILENAME).is_file()
    assert not (out_dir / "aggregate_assessments.json").exists()
    assert not (out_dir / "tag_output.json").exists()
    assert not (out_dir / "debug").exists()
    summary = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert "llm_execution" not in summary


def test_aggregate_evidence_assess_runner_api_writes_debug_artifacts_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.llm_execution_selection as llm_execution_selection_module

    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        llm_execution_selection_module,
        "build_api_provider",
        lambda *_args, **_kwargs: _ApiFakeProvider(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--llm",
            "api",
            "--llm-profile",
            "deepseek_v4_flash",
            "--out",
            str(out_dir),
        ],
    )
    assess_runner.main()

    captured = capsys.readouterr()
    assert "provider=deepseek" in captured.out
    assert "profile=deepseek_v4_flash" in captured.out
    assert "model=deepseek-v4-flash" in captured.out
    assert "thinking=false" in captured.out
    assert "response_format=json_object" in captured.out
    assert "seed=unset" in captured.out
    assert "max_tokens=10000" in captured.out

    debug_dir = out_dir / "debug"
    assert debug_dir.is_dir()
    assert (debug_dir / "llm_messages.json").is_file()
    assert (debug_dir / "prompt.txt").is_file()
    assert (debug_dir / "raw_text.txt").is_file()
    assert (debug_dir / "parse_error.txt").read_text(encoding="utf-8") == ""
    assert (debug_dir / "run_metadata.json").is_file()

    tag_output = json.loads((out_dir / SCOPE_ASSESSMENTS_FILENAME).read_text(encoding="utf-8"))
    summary = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))
    selection = summary["llm_execution"]["execution_selection"]
    assert selection == {
        "requested_profile": "deepseek_v4_flash",
        "requested_thinking": None,
        "canonical_profile": "deepseek_v4_flash",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "thinking": False,
        "response_format": "json_object",
        "max_tokens": 10000,
        "seed": None,
    }
    assert "messages" not in tag_output
    assert "llm_raw_result" not in tag_output
    assert "llm_prompt" not in tag_output
    assert tag_output["prompt_name"] == PROMPT_NAME
    assert tag_output["prompt_version"] == PROMPT_VERSION
    assert tag_output["prompt_name"] == summary["llm_execution"]["prompt_name"]
    assert tag_output["prompt_version"] == summary["llm_execution"]["prompt_version"]
    assert summary["llm_execution"]["llm_provider"] == "deepseek"
    assert summary["llm_execution"]["llm_model"] == "deepseek-v4-flash"
    assert summary["llm_execution"]["llm"] == {
        "provider": "deepseek",
        "model_alias": "deepseek_v4_flash",
        "model": "deepseek-v4-flash",
        "thinking": False,
    }
    assert summary["llm_execution"]["usage"] == {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }
    assert summary["llm_execution"]["cost_estimate"]["pricing_source"] == (
        "PROFILE_PRICE_TABLE.deepseek_v4_flash"
    )
    assert summary["llm_execution"]["cost_estimate"]["estimated_cost"] == pytest.approx(
        (10 * 1.0 + 5 * 2.0) / 1_000_000
    )
    assert summary["llm_execution"]["prompt_name"] == PROMPT_NAME
    assert summary["status"] == "success"
    assert summary["api_result_usable"] is True
    assert summary["fallback_used"] is False
    assert summary["fallback_reason"] is None
    assert summary["fallback_source"] is None
    assert summary["llm_execution"]["provider_request"]["max_tokens"] == 10000
    assert (
        summary["llm_execution"]["provider_request"]["model_alias"]
        == "deepseek_v4_flash"
    )
    run_metadata = json.loads((debug_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert run_metadata["provider_request"]["max_tokens"] == 10000
    assert tag_output["api_result"]["api_result_usable"] is True
    assert tag_output["api_result"]["fallback_used"] is False
    assert len(summary["llm_invocations"]) == 1
    invocation = summary["llm_invocations"][0]
    assert invocation["status"] == "success"
    assert invocation["attempt_index"] == 1
    assert invocation["request_id"] == "fake-req"
    assert invocation["usage"] == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }


def test_aggregate_evidence_assess_runner_api_no_llm_debug_artifacts_skips_debug_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.llm_execution_selection as llm_execution_selection_module

    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        llm_execution_selection_module,
        "build_api_provider",
        lambda *_args, **_kwargs: _ApiFakeProvider(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--llm",
            "api",
            "--llm-profile",
            "deepseek_v4_flash",
            "--no-llm-debug-artifacts",
            "--out",
            str(out_dir),
        ],
    )
    assess_runner.main()

    assert (out_dir / SCOPE_ASSESSMENTS_FILENAME).is_file()
    assert not (out_dir / "aggregate_assessments.json").exists()
    assert not (out_dir / "tag_output.json").exists()
    assert not (out_dir / "debug").exists()


def test_aggregate_evidence_assess_runner_api_bare_array_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.llm_execution_selection as llm_execution_selection_module

    class _BareArrayProvider:
        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            bare_array = json.loads(_api_fake_provider_json())["scope_assessments"]
            return LLMRawResult(
                provider_name="deepseek",
                model="deepseek-v4-flash",
                raw_text=json.dumps(bare_array, ensure_ascii=False),
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                request_id="fake-req",
                finish_reason="stop",
                model_alias="deepseek_v4_flash",
                thinking=False,
            )

    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(
        input_dir,
        llm_input_bundle=_canonical_api_llm_input_bundle(),
    )

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        llm_execution_selection_module,
        "build_api_provider",
        lambda *_args, **_kwargs: _BareArrayProvider(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--llm",
            "api",
            "--llm-profile",
            "deepseek_v4_flash",
            "--out",
            str(out_dir),
        ],
    )
    with pytest.raises(SystemExit):
        assess_runner.main()

    debug_dir = out_dir / "debug"
    assert (debug_dir / "parse_error.txt").read_text(encoding="utf-8")
    run_metadata = json.loads(
        (debug_dir / "run_metadata.json").read_text(encoding="utf-8")
    )
    assert "response_normalization" not in run_metadata
    assert run_metadata["failure_reason"] == "api_schema_validation_error"


def test_aggregate_evidence_assess_runner_api_parse_error_writes_debug_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.llm_execution_selection as llm_execution_selection_module

    class _BadJsonProvider:
        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            return LLMRawResult(
                provider_name="deepseek",
                model="deepseek-v4-flash",
                raw_text="not json {{{",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                request_id="fake-req",
                finish_reason="stop",
                model_alias="deepseek_v4_flash",
                thinking=False,
            )

    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        llm_execution_selection_module,
        "build_api_provider",
        lambda *_args, **_kwargs: _BadJsonProvider(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--llm",
            "api",
            "--llm-profile",
            "deepseek_v4_flash",
            "--out",
            str(out_dir),
        ],
    )
    with pytest.raises(SystemExit):
        assess_runner.main()

    debug_dir = out_dir / "debug"
    assert (debug_dir / "raw_text.txt").read_text(encoding="utf-8") == "not json {{{"
    parse_error = (debug_dir / "parse_error.txt").read_text(encoding="utf-8")
    assert parse_error
    assert not (out_dir / "tag_output.json").exists()
    summary = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["api_result_usable"] is False
    assert summary["fallback_used"] is False
    assert summary["fallback_reason"] is None
    assert summary["fallback_source"] is None
    assert summary["llm_execution"]["parse_error"] == parse_error
    assert summary["llm_execution"]["api_result"]["api_result_usable"] is False
    assert [
        invocation["attempt_index"]
        for invocation in summary["llm_invocations"]
    ] == [1, 2]
    assert [
        invocation["status"]
        for invocation in summary["llm_invocations"]
    ] == ["success", "success"]


def test_aggregate_evidence_assess_runner_api_parse_error_with_explicit_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deterministic post-patch artifact path for completed_with_api_fallback (parse error)."""
    import runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.llm_execution_selection as llm_execution_selection_module

    class _BadJsonProvider:
        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            return LLMRawResult(
                provider_name="deepseek",
                model="deepseek-v4-flash",
                raw_text="not json {{{",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                request_id="fake-req",
                finish_reason="stop",
                model_alias="deepseek_v4_flash",
                thinking=False,
            )

    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        llm_execution_selection_module,
        "build_api_provider",
        lambda *_args, **_kwargs: _BadJsonProvider(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--llm",
            "api",
            "--llm-profile",
            "deepseek_v4_flash",
            "--allow-api-parse-fallback",
            "--out",
            str(out_dir),
        ],
    )
    assess_runner.main()

    scope_output = json.loads((out_dir / SCOPE_ASSESSMENTS_FILENAME).read_text(encoding="utf-8"))
    assert scope_output["api_result"]["fallback_used"] is True
    assert scope_output["api_result"]["fallback_reason"] == "api_parse_error"
    assert scope_output["api_result"]["fallback_source"] == "mock_scope_assessments"
    assert scope_output["api_result"]["api_result_usable"] is False
    summary = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed_with_api_fallback"
    assert summary["api_result_usable"] is False
    assert summary["fallback_used"] is True
    assert summary["fallback_reason"] == "api_parse_error"
    assert summary["fallback_source"] == "mock_scope_assessments"
    assert summary["llm_execution"]["api_result"]["fallback_used"] is True
    assert summary["llm_execution"]["api_result"]["api_result_usable"] is False


def test_aggregate_evidence_assess_runner_api_finish_reason_length_with_explicit_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deterministic post-patch artifact path for completed_with_api_fallback (length)."""
    import runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.llm_execution_selection as llm_execution_selection_module

    class _TruncatedProvider:
        def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
            return LLMRawResult(
                provider_name="deepseek",
                model="deepseek-v4-flash",
                raw_text='{"scope_assessments":[{"scope_id":"HS0001","study_context":{',
                usage={
                    "prompt_tokens": 100,
                    "completion_tokens": 8192,
                    "total_tokens": 8292,
                },
                request_id="fake-req",
                finish_reason="length",
                model_alias="deepseek_v4_flash",
                thinking=False,
            )

    input_dir = tmp_path / "tag_prepare_in"
    out_dir = tmp_path / "tag_out"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        llm_execution_selection_module,
        "build_api_provider",
        lambda *_args, **_kwargs: _TruncatedProvider(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--llm",
            "api",
            "--llm-profile",
            "deepseek_v4_flash",
            "--allow-api-parse-fallback",
            "--out",
            str(out_dir),
        ],
    )
    assess_runner.main()

    scope_output = json.loads((out_dir / SCOPE_ASSESSMENTS_FILENAME).read_text(encoding="utf-8"))
    summary = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))
    run_metadata = json.loads((out_dir / "debug" / "run_metadata.json").read_text(encoding="utf-8"))

    assert summary["status"] == "completed_with_api_fallback"
    assert summary["api_result_usable"] is False
    assert summary["fallback_used"] is True
    assert summary["fallback_reason"] == "api_finish_reason_length"
    assert summary["fallback_source"] == "mock_scope_assessments"
    assert summary["llm_execution"]["provider_request"]["max_tokens"] == 10000
    assert scope_output["api_result"]["api_result_usable"] is False
    assert scope_output["api_result"]["fallback_used"] is True
    assert scope_output["api_result"]["fallback_reason"] == "api_finish_reason_length"
    assert scope_output["api_result"]["fallback_source"] == "mock_scope_assessments"
    assert run_metadata["provider_request"]["max_tokens"] == 10000
    assert run_metadata["performance"]["finish_reason"] == "length"


def test_aggregate_evidence_assess_runner_requires_explicit_llm_backend() -> None:
    with pytest.raises(SystemExit):
        assess_runner.parse_args(
            [
                "--assessment-input",
                "runs/prepare/x/assessment_input.json",
            ]
        )


def test_aggregate_evidence_assess_runner_explicit_mock_accepted() -> None:
    args = assess_runner.parse_args(
        [
            "--assessment-input",
            "runs/prepare/x/assessment_input.json",
            "--llm",
            "mock",
        ]
    )
    assert args.llm == "mock"
    assert args.llm_profile is None


def test_aggregate_evidence_assess_runner_api_requires_explicit_profile() -> None:
    with pytest.raises(SystemExit, match="API execution requires explicit --llm-profile"):
        assess_runner.parse_args(
            [
                "--assessment-input",
                "runs/prepare/x/assessment_input.json",
                "--llm",
                "api",
            ]
        )


def test_aggregate_evidence_assess_runner_profile_without_backend_rejected() -> None:
    with pytest.raises(SystemExit):
        assess_runner.parse_args(
            [
                "--assessment-input",
                "runs/prepare/x/assessment_input.json",
                "--llm-profile",
                "qwen3_7_plus_2026_05_26",
                "--no-thinking",
            ]
        )


def test_aggregate_evidence_assess_runner_api_accepts_explicit_profile() -> None:
    args = assess_runner.parse_args(
        [
            "--assessment-input",
            "runs/prepare/x/assessment_input.json",
            "--llm",
            "api",
            "--llm-profile",
            "qwen3_7_plus_2026_05_26",
            "--no-thinking",
        ]
    )
    assert args.llm == "api"
    assert args.llm_profile == "qwen3_7_plus_2026_05_26"
    assert args.thinking is False


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("--thinking", True), ("--no-thinking", False)],
)
def test_aggregate_evidence_assess_runner_parses_tri_state_thinking(
    flag: str,
    expected: bool,
) -> None:
    args = assess_runner.parse_args(
        [
            "--assessment-input",
            "runs/prepare/x/assessment_input.json",
            "--llm",
            "api",
            "--llm-profile",
            "deepseek_v4_flash",
            flag,
        ]
    )

    assert args.thinking is expected


def test_aggregate_evidence_assess_runner_api_unspecified_thinking_remains_none() -> None:
    args = assess_runner.parse_args(
        [
            "--assessment-input",
            "runs/prepare/x/assessment_input.json",
            "--llm",
            "api",
            "--llm-profile",
            "qwen3_7_plus_2026_05_26",
        ]
    )

    assert args.thinking is None


def test_aggregate_evidence_assess_runner_rejects_retired_mode_bearing_profile() -> None:
    from llm.model_registry import RetiredLLMProfileError

    with pytest.raises(RetiredLLMProfileError, match="deepseek_reasoning is retired"):
        assess_runner.parse_args(
            [
                "--assessment-input",
                "runs/tag_prepare/x/llm_input_aggregate.json",
                "--llm",
                "api",
                "--llm-profile",
                "deepseek_reasoning",
            ]
        )


def test_aggregate_evidence_assess_runner_default_output_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "prepare_in"
    llm_input_path = _write_llm_input_bundle_file(input_dir)

    _mock_git_provenance(monkeypatch)
    monkeypatch.setattr(assess_runner, "PROJECT_ROOT", tmp_path)
    fixed_stamp = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.operations.utc_run_stamp",
        lambda: fixed_stamp,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assess_runner.py",
            "--assessment-input",
            str(llm_input_path),
            "--llm",
            "mock",
        ],
    )
    assess_runner.main()

    captured = capsys.readouterr()
    assert "route=aggregate" in captured.out
    assert "evidence_form_id=aggregate_evidence" in captured.out
    assert "comparison_type=" not in captured.out

    expected_run_id = format_run_timestamp(fixed_stamp)
    expected_out = (
        tmp_path
        / "runs"
        / "evidence_source_preparation"
        / "assess"
        / expected_run_id
        / "doc_test"
        / "clinical_safety"
        / "aggregate_evidence"
    )
    assert expected_out.is_dir()
    assert (expected_out / SCOPE_ASSESSMENTS_FILENAME).is_file()
    assert "aggregate" not in expected_out.parts[-1:]
